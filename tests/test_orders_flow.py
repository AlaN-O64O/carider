"""Шаги 3–6 UC-01, БП-01, БП-02, БП-05, Т-5: слой логики без браузера."""

import sqlite3
import unittest
from datetime import UTC, datetime, timedelta

from carider.accounts.errors import ClientBlockedError, ClientNotFoundError
from carider.dispatch import services as dispatch
from carider.dispatch.errors import NoDriversError
from carider.orders import repository, services
from carider.orders.errors import (
    DriverBusyError,
    OrderStateError,
    PriceChangedError,
)

from .helpers import (
    DEST,
    PHONE,
    PHONE_2,
    PHONE_BLOCKED,
    T0,
    make_conn,
    set_all_drivers_busy,
)


class OrderFlowTest(unittest.TestCase):
    def setUp(self):
        self.conn = make_conn()
        self.addCleanup(self.conn.close)

    def order(self, phone=PHONE, price=1850, now=T0):
        return services.create_order(self.conn, phone, DEST, price, now=now)

    def driver_status(self, driver_id):
        row = self.conn.execute(
            "SELECT status FROM drivers WHERE id = ?", (driver_id,)
        ).fetchone()
        return row["status"]

    def test_main_flow_assigns_nearest_free_driver(self):
        """Основной поток, шаги 3–6: заказ создан, назначен ближайший таксист."""
        created = self.order()
        self.assertEqual(created.status, "created")
        offer = dispatch.find_driver(self.conn, created.id, now=T0)
        self.assertEqual(offer.name, "Ерлан Т.")  # 1,7 км; занятый Нурлан ближе
        self.assertEqual(offer.plate, "482 BKA 01")
        self.assertEqual(offer.eta_min, 4)
        self.assertEqual(services.get_order(self.conn, created.id).status, "assigned")
        self.assertEqual(self.driver_status(1), "busy")

    def test_price_must_match_quote(self):
        """БП-02: подтверждается та цена, которую клиент видел."""
        with self.assertRaises(PriceChangedError):
            self.order(price=1800)

    def test_blocked_client_cannot_order(self):
        """Клиент с «Статус блокировки = true» не может заказать."""
        with self.assertRaises(ClientBlockedError):
            self.order(phone=PHONE_BLOCKED)

    def test_unknown_client_is_unauthorized(self):
        """Предусловие UC-01: клиент должен быть зарегистрирован."""
        with self.assertRaises(ClientNotFoundError):
            self.order(phone="+77019999999")

    def test_no_drivers_boundary_at_15_seconds(self):
        """Исключение 5а, БП-01: на 14 с поиск идёт, на 15 с — «Свободных машин нет»."""
        set_all_drivers_busy(self.conn)
        created = self.order()
        self.assertIsNone(
            dispatch.find_driver(self.conn, created.id, now=T0 + timedelta(seconds=14))
        )
        with self.assertRaises(NoDriversError):
            dispatch.find_driver(self.conn, created.id, now=T0 + timedelta(seconds=15))

    def test_driver_outside_radius_is_not_assigned(self):
        """Талгат свободен, но в 12 км (радиус 5 км): исключение 5а."""
        set_all_drivers_busy(self.conn, except_id=5)
        created = self.order()
        with self.assertRaises(NoDriversError):
            dispatch.find_driver(self.conn, created.id, now=T0 + timedelta(seconds=15))

    def test_search_without_explicit_now_compares_aware_datetimes(self):
        """Регрессия Д-2: время по умолчанию имеет часовой пояс, TypeError нет."""
        set_all_drivers_busy(self.conn)
        created = self.order(now=datetime.now(UTC) - timedelta(seconds=20))
        with self.assertRaises(NoDriversError):
            dispatch.find_driver(self.conn, created.id)

    def test_repeat_search_restarts_timer_and_finds_freed_driver(self):
        """Исключение 5а: «Повторить поиск» перезапускает отсчёт и ищет снова."""
        set_all_drivers_busy(self.conn)
        created = self.order()
        late = T0 + timedelta(seconds=15)
        with self.assertRaises(NoDriversError):
            dispatch.find_driver(self.conn, created.id, now=late)
        self.conn.execute("UPDATE drivers SET status = 'free' WHERE id = 2")
        self.conn.commit()
        dispatch.repeat_search(self.conn, created.id, now=late)
        offer = dispatch.find_driver(self.conn, created.id, now=late)
        self.assertEqual(offer.name, "Айдос М.")

    def test_free_cancel_boundary_one_minute(self):
        """БП-05: на 60-й секунде отмена бесплатна, на 61-й — со штрафом."""
        first = self.order(phone=PHONE)
        second = self.order(phone=PHONE_2)
        free = services.cancel_order(self.conn, first.id, T0 + timedelta(seconds=60))
        paid = services.cancel_order(self.conn, second.id, T0 + timedelta(seconds=61))
        self.assertFalse(free.penalty)
        self.assertTrue(paid.penalty)

    def test_cancel_frees_the_driver(self):
        """Отмена назначенного заказа освобождает таксиста."""
        created = self.order()
        self.assertEqual(self.driver_status(1), "busy")
        services.cancel_order(self.conn, created.id, T0 + timedelta(seconds=5))
        self.assertEqual(self.driver_status(1), "free")

    def test_cancelled_order_cannot_be_cancelled_again(self):
        """Повторная отмена: OrderStateError (409)."""
        created = self.order()
        services.cancel_order(self.conn, created.id, T0)
        with self.assertRaises(OrderStateError):
            services.cancel_order(self.conn, created.id, T0)

    def test_second_order_gets_next_driver(self):
        """Два заказа подряд получают разных таксистов (Т-5)."""
        first = self.order(phone=PHONE)
        second = self.order(phone=PHONE_2)
        a = dispatch.find_driver(self.conn, first.id, now=T0)
        b = dispatch.find_driver(self.conn, second.id, now=T0)
        self.assertEqual((a.name, b.name), ("Ерлан Т.", "Айдос М."))

    def test_dispatch_skips_driver_taken_by_race(self):
        """Т-5: статус таксиста устарел (гонка), СУБД не даёт назначить его снова."""
        self.order(phone=PHONE)  # Ерлан занят
        self.conn.execute("UPDATE drivers SET status = 'free' WHERE id = 1")
        self.conn.commit()  # устаревший статус, как при гонке двух запросов
        second = self.order(phone=PHONE_2)
        offer = dispatch.find_driver(self.conn, second.id, now=T0)
        self.assertEqual(offer.name, "Айдос М.")

    def test_database_forbids_two_active_orders_for_one_driver(self):
        """Ограничение СУБД one_active_order_per_driver: IntegrityError."""
        self.order(phone=PHONE)  # у Ерлана активный заказ
        second = repository.insert_order(self.conn, 2, DEST, 1850, T0)
        with self.assertRaises(sqlite3.IntegrityError):
            repository.assign_driver(self.conn, second.id, 1)

    def test_service_turns_integrity_error_into_driver_busy(self):
        """services.assign_driver превращает IntegrityError в DriverBusyError."""
        self.order(phone=PHONE)  # заказ 1 у Ерлана
        second = repository.insert_order(self.conn, 2, DEST, 1850, T0)
        self.conn.commit()
        with self.assertRaises(DriverBusyError):
            services.assign_driver(self.conn, second.id, 1)


if __name__ == "__main__":
    unittest.main()
