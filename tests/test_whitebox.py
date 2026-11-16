"""Тесты «белого ящика»: базисные пути dispatch.find_driver() и составные условия."""

from datetime import timedelta

from carider.dispatch import services as dispatch
from carider.dispatch.errors import NoDriversError
from carider.orders import repository, services
from carider.orders.errors import OrderStateError

from .frozen import DEST, NOW, PHONE, PRICE, FrozenTimeTestCase


class FindDriverPathsTest(FrozenTimeTestCase):
    """Пять базисных путей функции find_driver(): V(G) = 5."""

    def test_path_1_already_assigned(self):
        """П1: P1 «да» — заказ уже назначен, вернуть таксиста."""
        order = services.create_order(self.conn, PHONE, DEST, PRICE)
        offer = dispatch.find_driver(self.conn, order.id)
        self.assertEqual(offer.plate, "482 BKA 01")

    def test_path_2_cancelled_order(self):
        """П2: P1 «нет», P2 «да» — заказ отменён, OrderStateError."""
        order = services.create_order(self.conn, PHONE, DEST, PRICE)
        services.cancel_order(self.conn, order.id)
        with self.assertRaises(OrderStateError):
            dispatch.find_driver(self.conn, order.id)

    def test_path_3_driver_found_while_polling(self):
        """П3: P3 «да» — таксист освободился между созданием и опросом."""
        self.busy_all()
        order = services.create_order(self.conn, PHONE, DEST, PRICE)
        self.conn.execute("UPDATE drivers SET status = 'free' WHERE id = 2")
        self.conn.commit()
        offer = dispatch.find_driver(self.conn, order.id)
        self.assertEqual(offer.name, "Айдос М.")
        self.assertEqual(self.status_of("orders", order.id), "assigned")

    def test_path_4_timeout(self):
        """П4: P4 «да» — 15 секунд без таксиста, NoDriversError."""
        self.busy_all()
        order = services.create_order(self.conn, PHONE, DEST, PRICE)
        with self.clock(NOW + timedelta(seconds=15)):
            with self.assertRaises(NoDriversError):
                dispatch.find_driver(self.conn, order.id)

    def test_path_5_search_continues(self):
        """П5: P4 «нет» — поиск идёт, ответ None (в API — 202)."""
        self.busy_all()
        order = services.create_order(self.conn, PHONE, DEST, PRICE)
        self.assertIsNone(dispatch.find_driver(self.conn, order.id))


class CompositeConditionTest(FrozenTimeTestCase):
    """Составное условие `order.search_started_at or order.created_at`."""

    def test_both_parts_true_and_false(self):
        """Часть «время начала поиска» и истинна, и ложна; ответ одинаков."""
        self.busy_all()
        searched = services.create_order(self.conn, PHONE, DEST, PRICE)
        # заказ без запущенного поиска: search_started_at пусто, берётся created_at
        silent = repository.insert_order(self.conn, 1, DEST, PRICE, NOW)
        self.conn.commit()
        late = NOW + timedelta(seconds=15)
        for order_id in (searched.id, silent.id):
            with self.subTest(order_id=order_id), self.clock(late):
                with self.assertRaises(NoDriversError):
                    dispatch.find_driver(self.conn, order_id)


class MissingPositionTest(FrozenTimeTestCase):
    """Ветви «положение таксиста неизвестно»."""

    def test_driver_without_position_is_skipped(self):
        """Свободный таксист без положения не участвует в поиске."""
        self.conn.execute("DELETE FROM driver_positions WHERE driver_id = 1")
        self.conn.commit()
        order = services.create_order(self.conn, PHONE, DEST, PRICE)
        self.assertEqual(dispatch.find_driver(self.conn, order.id).name, "Айдос М.")

    def test_offer_without_position_has_no_eta(self):
        """Если положение пропало после назначения, время подъезда не показывается."""
        order = services.create_order(self.conn, PHONE, DEST, PRICE)
        self.conn.execute("DELETE FROM driver_positions WHERE driver_id = 1")
        self.conn.commit()
        self.assertIsNone(dispatch.find_driver(self.conn, order.id).eta_min)
