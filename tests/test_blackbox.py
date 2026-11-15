"""Тесты «чёрного ящика» для UC-01: построены по требованиям, а не по коду."""

import math
from datetime import timedelta

from carider.accounts.errors import ClientBlockedError, ClientNotFoundError
from carider.dispatch import services as dispatch
from carider.dispatch.errors import NoDriversError
from carider.orders import repository, services
from carider.orders.errors import (
    DestinationNotFoundError,
    InvalidDestinationError,
    OrderStateError,
    PriceChangedError,
)

from .frozen import (
    DEST,
    NOW,
    PHONE,
    PHONE_2,
    PHONE_BLOCKED,
    PRICE,
    FrozenApiTestCase,
    FrozenTimeTestCase,
)


class DestinationClassesTest(FrozenTimeTestCase):
    """Параметр «пункт назначения» (словарь данных: 1–250 символов)."""

    def test_length_classes_and_bounds(self):
        """Классы длины: 0, пробелы, 250 (граница), 251 (за границей)."""
        cases = [
            ("", InvalidDestinationError),
            ("   ", InvalidDestinationError),
            ("а" * 250, DestinationNotFoundError),  # длина верна, адреса нет
            ("а" * 251, InvalidDestinationError),
        ]
        for text, error in cases:
            with self.subTest(length=len(text.strip())):
                with self.assertRaises(error):
                    services.calculate_quote(self.conn, text)

    def test_known_address_is_found_in_any_case(self):
        """Допустимый класс: известный адрес в другом регистре и с пробелами."""
        quote = services.calculate_quote(self.conn, "  аЭРОПОРТ ")
        self.assertEqual((quote.destination, quote.price_tg), ("Аэропорт", 4050))


class DestinationApiTest(FrozenApiTestCase):
    """Параметр «пункт назначения» через API: отсутствует или не строка."""

    def test_missing_or_null_destination_is_400(self):
        """Недопустимые классы: нет поля, null, число. Дефект Д-5."""
        for body in ({}, {"destination": None}, {"destination": 123}):
            with self.subTest(body=body):
                response = self.client.post("/api/quotes/", json=body)
                self.assertEqual(response.status_code, 400)
                code = response.get_json()["error"]["code"]
                self.assertEqual(code, "INVALID_DESTINATION")


    def test_destination_in_order_must_be_a_string(self):
        """Недопустимый класс для заказа: null вместо адреса — 400. Дефект Д-5."""
        response = self.post_order(destination=None)
        self.assertEqual(response.status_code, 400)

    def test_body_must_be_a_json_object(self):
        """Недопустимые классы тела запроса: массив и строка — 400. Дефект Д-8."""
        for body in ([1, 2], "текст"):
            with self.subTest(body=body):
                response = self.client.post("/api/quotes/", json=body)
                self.assertEqual(response.status_code, 400)


class PhoneFormatTest(FrozenApiTestCase):
    """Формат телефона: +7 и ровно 10 цифр (ASCII)."""

    def test_valid_phone_is_201(self):
        """Допустимый класс: +7 и 10 цифр."""
        self.assertEqual(self.post_order().status_code, 201)

    def test_invalid_phones_are_400(self):
        """Недопустимые классы: короче, длиннее, через 8, с буквой, пустой,
        с переводом строки на конце, с неевропейскими цифрами. Дефект Д-4."""
        cases = {
            "короче на 1": "+7701000000",
            "длиннее на 1": "+770100000012",
            "через 8": "87010000001",
            "с буквой": "+7701000000a",
            "пустой": "",
            "перевод строки на конце": PHONE + "\n",
            "арабские цифры": "+7" + "٠١٠٠٠٠٠٠٠١",
        }
        for name, phone in cases.items():
            with self.subTest(name):
                response = self.post_order(phone=phone)
                self.assertEqual(response.status_code, 400)
                code = response.get_json()["error"]["code"]
                self.assertEqual(code, "INVALID_REQUEST")


class PriceClassesTest(FrozenApiTestCase):
    """БП-02: клиент подтверждает цену, равную расчётной (1850 тг)."""

    def test_price_must_equal_quote(self):
        """Граница: 1850 — заказ создан; 1849 и 1851 — 409 PRICE_CHANGED."""
        self.assertEqual(self.post_order(price_tg=PRICE).status_code, 201)
        for price in (PRICE - 1, PRICE + 1):
            with self.subTest(price=price):
                response = self.post_order(price_tg=price)
                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.get_json()["error"]["code"], "PRICE_CHANGED")

    def test_price_must_be_a_positive_integer(self):
        """Формат: 0, отрицательное, текст и дробное число — 400. Дефект Д-6."""
        for price in (0, -5, "abc", 1850.5):
            with self.subTest(price=price):
                self.assertEqual(self.post_order(price_tg=price).status_code, 400)


class CancelFeeTest(FrozenTimeTestCase):
    """БП-05: бесплатная отмена — первая минута после создания заказа."""

    def test_fee_boundary_at_one_minute(self):
        """Границы 0, 59, 60 с — бесплатно; 61 и 300 с — со штрафом."""
        cases = [(0, False), (59, False), (60, False), (61, True), (300, True)]
        for seconds, penalty in cases:
            with self.subTest(seconds=seconds):
                order = services.create_order(self.conn, PHONE, DEST, PRICE)
                with self.clock(NOW + timedelta(seconds=seconds)):
                    cancelled = services.cancel_order(self.conn, order.id)
                self.assertEqual(cancelled.penalty, penalty)

    def test_free_cancel_countdown(self):
        """Отсчёт на экране: 60 с в начале, 25 с через 35 с, 0 после минуты."""
        order = services.create_order(self.conn, PHONE, DEST, PRICE)
        for seconds, left in ((0, 60), (35, 25), (60, 0), (90, 0)):
            with self.subTest(seconds=seconds):
                moment = NOW + timedelta(seconds=seconds)
                self.assertEqual(services.free_cancel_left(order, moment), left)


class SearchTimeoutTest(FrozenTimeTestCase):
    """БП-01 и исключение 5а: свободных машин нет — ответ через 15 секунд."""

    def test_timeout_bounds_with_moving_clock(self):
        """14 с — поиск идёт; 15 и 16 с — «Свободных машин нет»."""
        self.busy_all()
        order = services.create_order(self.conn, PHONE, DEST, PRICE)
        with self.clock(NOW + timedelta(seconds=14)):
            self.assertIsNone(dispatch.find_driver(self.conn, order.id))
        for seconds in (15, 16):
            with self.subTest(seconds=seconds):
                with self.clock(NOW + timedelta(seconds=seconds)):
                    with self.assertRaises(NoDriversError):
                        dispatch.find_driver(self.conn, order.id)


class SearchRadiusTest(FrozenTimeTestCase):
    """Радиус поиска ближайшего таксиста — 5 км."""

    def place_only_driver(self, km):
        """Оставить свободным одного таксиста на расстоянии km к северу."""
        self.busy_all(except_id=1)
        lat, lon = repository.PICKUP_POINT
        north = lat + math.degrees(km / 6371)
        self.conn.execute(
            "UPDATE driver_positions SET lat = ?, lon = ? WHERE driver_id = 1",
            (north, lon),
        )
        self.conn.commit()

    def test_radius_bounds(self):
        """4,99 км — таксист назначен; 5,01 км — не назначен."""
        self.place_only_driver(4.99)
        near = services.create_order(self.conn, PHONE, DEST, PRICE)
        self.assertEqual(dispatch.find_driver(self.conn, near.id).name, "Ерлан Т.")
        services.cancel_order(self.conn, near.id)
        self.place_only_driver(5.01)
        far = services.create_order(self.conn, PHONE, DEST, PRICE)
        with self.clock(NOW + timedelta(seconds=15)):
            with self.assertRaises(NoDriversError):
                dispatch.find_driver(self.conn, far.id)


class OrderDecisionTableTest(FrozenApiTestCase):
    """Таблица решений для «Заказать»: порядок проверок задаёт код ответа.

    Порядок: формат → клиент → адрес → цена → поиск таксиста.
    """

    def test_r1_bad_format_is_400(self):
        """Правило R1: формат неверен — 400, остальное не проверяется."""
        response = self.post_order(phone="8701", price_tg="abc")
        self.assertEqual(response.status_code, 400)

    def test_r2_unknown_client_is_401(self):
        """Правило R2: клиент не найден — 401."""
        self.assertEqual(self.post_order(phone="+77019999999").status_code, 401)

    def test_r3_blocked_client_is_403(self):
        """Правило R3: клиент заблокирован — 403."""
        self.assertEqual(self.post_order(phone=PHONE_BLOCKED).status_code, 403)

    def test_r4_unknown_address_is_404(self):
        """Правило R4: адрес не найден — 404."""
        self.assertEqual(self.post_order(destination="нигде").status_code, 404)

    def test_r5_changed_price_is_409(self):
        """Правило R5: цена не совпала с расчётной — 409."""
        self.assertEqual(self.post_order(price_tg=PRICE + 10).status_code, 409)

    def test_r6_no_drivers_gives_201_then_409(self):
        """Правило R6: всё верно, таксистов нет — 201, через 15 с 409."""
        self.busy_all()
        created = self.post_order()
        self.assertEqual(created.status_code, 201)
        url = f"/api/orders/{created.get_json()['order_id']}/driver/"
        self.assertEqual(self.client.get(url).status_code, 202)
        with self.clock(NOW + timedelta(seconds=15)):
            late = self.client.get(url)
        self.assertEqual(late.status_code, 409)
        self.assertEqual(late.get_json()["error"]["code"], "NO_DRIVERS")

    def test_r7_all_conditions_met_gives_201_then_200(self):
        """Правило R7: всё верно, таксист есть — 201, затем 200 «Назначен»."""
        created = self.post_order()
        self.assertEqual(created.status_code, 201)
        url = f"/api/orders/{created.get_json()['order_id']}/driver/"
        found = self.client.get(url)
        self.assertEqual(found.status_code, 200)
        self.assertEqual(found.get_json()["status"], "Назначен")

    def test_r8_blocked_client_and_wrong_price_gives_403(self):
        """Правило R8 (два нарушения): клиент проверяется раньше цены — 403."""
        response = self.post_order(phone=PHONE_BLOCKED, price_tg=PRICE + 10)
        self.assertEqual(response.status_code, 403)

    def test_r9_unknown_address_and_wrong_price_gives_404(self):
        """Правило R9 (два нарушения): адрес проверяется раньше цены — 404."""
        response = self.post_order(destination="нигде", price_tg=PRICE + 10)
        self.assertEqual(response.status_code, 404)


class StatusTransitionTest(FrozenTimeTestCase):
    """Переходы состояний заказа: создан → назначен / отменён; назначен → отменён."""

    def test_created_to_assigned(self):
        """Разрешённый переход: создан → назначен (нашёлся таксист)."""
        order = services.create_order(self.conn, PHONE, DEST, PRICE)
        dispatch.find_driver(self.conn, order.id)
        self.assertEqual(self.status_of("orders", order.id), "assigned")

    def test_created_to_cancelled_without_driver(self):
        """Разрешённый переход: создан → отменён, таксист не назначался."""
        self.busy_all()
        order = services.create_order(self.conn, PHONE, DEST, PRICE)
        cancelled = services.cancel_order(self.conn, order.id)
        self.assertEqual((cancelled.status, cancelled.driver_id), ("cancelled", None))

    def test_assigned_to_cancelled_frees_driver(self):
        """Разрешённый переход: назначен → отменён, таксист снова свободен."""
        order = services.create_order(self.conn, PHONE, DEST, PRICE)
        services.cancel_order(self.conn, order.id)
        self.assertEqual(self.status_of("drivers", 1), "free")

    def test_cancelled_order_accepts_no_more_actions(self):
        """Запрещено: из «отменён» нельзя ни отменить, ни искать, ни опрашивать."""
        order = services.create_order(self.conn, PHONE, DEST, PRICE)
        services.cancel_order(self.conn, order.id)
        actions = {
            "отменить": services.cancel_order,
            "повторить поиск": dispatch.repeat_search,
            "результат поиска": dispatch.find_driver,
        }
        for name, action in actions.items():
            with self.subTest(name), self.assertRaises(OrderStateError):
                action(self.conn, order.id)

    def test_assigned_order_cannot_repeat_search(self):
        """Запрещено: назначен → «повторить поиск»."""
        order = services.create_order(self.conn, PHONE, DEST, PRICE)
        with self.assertRaises(OrderStateError):
            dispatch.repeat_search(self.conn, order.id)

    def test_running_and_completed_orders_cannot_be_cancelled(self):
        """Запрещено: выполняется и завершён → отмена (состояния ЛР №4)."""
        for status in ("in_progress", "completed"):
            with self.subTest(status):
                order = services.create_order(self.conn, PHONE, DEST, PRICE)
                self.conn.execute(
                    "UPDATE orders SET status = ? WHERE id = ?", (status, order.id)
                )
                self.conn.commit()
                with self.assertRaises(OrderStateError):
                    services.cancel_order(self.conn, order.id)
                self.conn.execute("DELETE FROM orders WHERE id = ?", (order.id,))
                self.conn.execute("UPDATE drivers SET status = 'free'")
                self.conn.commit()


class CancelledScreenTest(FrozenApiTestCase):
    """Экран Э-05 «Заказ отменён» показывается только после отмены."""

    def test_screen_is_not_available_for_active_order(self):
        """Заказ назначен, не отменён: открыть Э-05 нельзя (409). Дефект Д-7."""
        order_id = self.post_order().get_json()["order_id"]
        response = self.client.get(f"/orders/{order_id}/cancelled")
        self.assertEqual(response.status_code, 409)
        self.assertNotIn("отменён", response.get_data(as_text=True))

    def test_screen_after_cancel_shows_no_penalty(self):
        """Допустимый переход: после отмены в первую минуту — штрафа нет."""
        order_id = self.post_order().get_json()["order_id"]
        self.client.post(f"/orders/{order_id}/cancel")
        page = self.client.get(f"/orders/{order_id}/cancelled")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Штраф не взят", page.get_data(as_text=True))


class ClientRulesTest(FrozenTimeTestCase):
    """Предусловие UC-01: клиент зарегистрирован и не заблокирован."""

    def test_two_clients_get_different_drivers(self):
        """Два клиента подряд — два разных таксиста (один таксист — один заказ)."""
        first = services.create_order(self.conn, PHONE, DEST, PRICE)
        second = services.create_order(self.conn, PHONE_2, DEST, PRICE)
        a = dispatch.find_driver(self.conn, first.id)
        b = dispatch.find_driver(self.conn, second.id)
        self.assertNotEqual(a.plate, b.plate)

    def test_unknown_and_blocked_clients(self):
        """Незнакомый клиент и заблокированный не могут создать заказ."""
        with self.assertRaises(ClientNotFoundError):
            services.create_order(self.conn, "+77019999999", DEST, PRICE)
        with self.assertRaises(ClientBlockedError):
            services.create_order(self.conn, PHONE_BLOCKED, DEST, PRICE)
        with self.assertRaises(PriceChangedError):
            services.create_order(self.conn, PHONE, DEST, PRICE - 1)
