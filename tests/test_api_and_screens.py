"""Тесты через HTTP: исключения UC-01 превращаются в коды API и особые экраны."""

import base64
import unittest
from datetime import timedelta
from unittest.mock import patch

from carider import db
from carider.orders.errors import RoutingServiceError

from .helpers import DEST, PHONE, PHONE_2, PHONE_BLOCKED, make_app_client


def busy_drivers(path):
    """Сделать всех таксистов занятыми в базе по указанному пути."""
    conn = db.get_connection(path)
    conn.execute("UPDATE drivers SET status = 'busy'")
    conn.commit()
    conn.close()


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.app, self.client, self.path = make_app_client(self)

    def order(self, phone=PHONE, price=1850):
        payload = {"destination": DEST, "price_tg": price, "phone": phone}
        return self.client.post("/api/orders/", json=payload)

    def test_quote_ok(self):
        """Операция 1, основной поток: 200 и цена как на прототипе."""
        response = self.client.post("/api/quotes/", json={"destination": DEST})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["price_tg"], 1850)

    def test_quote_error_codes(self):
        """Операция 1: 400 для пустого адреса, 404 для неизвестного."""
        empty = self.client.post("/api/quotes/", json={"destination": ""})
        self.assertEqual(empty.status_code, 400)
        self.assertEqual(empty.get_json()["error"]["code"], "INVALID_DESTINATION")
        unknown = self.client.post("/api/quotes/", json={"destination": "нигде"})
        self.assertEqual(unknown.status_code, 404)

    def test_quote_connection_error_is_503(self):
        """Исключение 4а UC-01: нет связи при расчёте — 503, заказ не создаётся."""
        failure = RoutingServiceError()
        with patch("carider.orders.repository.find_place", side_effect=failure):
            response = self.client.post("/api/quotes/", json={"destination": DEST})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"]["code"], "SERVICE_UNAVAILABLE")

    def test_create_order_and_get_driver(self):
        """Операции 2 и 3, основной поток: 201, затем 200 с таксистом."""
        created = self.order()
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.get_json()["status"], "Создан")
        order_id = created.get_json()["order_id"]
        result = self.client.get(f"/api/orders/{order_id}/driver/")
        self.assertEqual(result.status_code, 200)
        driver = result.get_json()["driver"]
        self.assertEqual(driver["name"], "Ерлан Т.")
        self.assertEqual(driver["eta_min"], 4)

    def test_create_order_error_codes(self):
        """Операция 2: 400 формат, 401, 403, 409 (БП-02)."""
        bad_phone = self.order(phone="8701")
        self.assertEqual(bad_phone.status_code, 400)
        self.assertIn("phone", bad_phone.get_json()["error"]["fields"])
        self.assertEqual(self.order(phone="+77019999999").status_code, 401)
        self.assertEqual(self.order(phone=PHONE_BLOCKED).status_code, 403)
        changed = self.order(price=1800)
        self.assertEqual(changed.status_code, 409)
        self.assertEqual(changed.get_json()["error"]["code"], "PRICE_CHANGED")

    def test_no_drivers_is_409_then_repeat_search(self):
        """Исключение 5а: 202 пока ищем, 409 по таймауту, потом повтор поиска."""
        busy_drivers(self.path)
        order_id = self.order().get_json()["order_id"]
        url = f"/api/orders/{order_id}/driver/"
        self.assertEqual(self.client.get(url).status_code, 202)
        with patch("carider.dispatch.services.SEARCH_TIMEOUT", timedelta(0)):
            late = self.client.get(url)
        self.assertEqual(late.status_code, 409)
        self.assertEqual(late.get_json()["error"]["code"], "NO_DRIVERS")
        repeat = self.client.post(f"/api/orders/{order_id}/search/")
        self.assertEqual(repeat.status_code, 202)

    def test_cancel_and_state_errors(self):
        """Операция 5: 200 без штрафа, повторная отмена — 409, неизвестный — 404."""
        order_id = self.order().get_json()["order_id"]
        cancelled = self.client.post(f"/api/orders/{order_id}/cancel/")
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.get_json(), {"status": "Отменён", "penalty": False})
        again = self.client.post(f"/api/orders/{order_id}/cancel/")
        self.assertEqual(again.status_code, 409)
        self.assertEqual(self.client.get("/api/orders/999/driver/").status_code, 404)


class ScreensTest(unittest.TestCase):
    def setUp(self):
        self.app, self.client, self.path = make_app_client(self)

    def text(self, response):
        return response.get_data(as_text=True)

    def order_form(self, **extra):
        data = {"destination": DEST, "price_tg": "1850", "consent": "on"}
        data.update(extra)
        return data

    def test_main_flow_on_screens(self):
        """Э-01 → Э-02 → Э-03 → Э-04: клиент заказывает и видит таксиста."""
        self.assertIn("Куда едем?", self.text(self.client.get("/")))
        quote = self.client.get("/quote", query_string={"destination": DEST})
        self.assertIn("Заказать за 1 850 тг", self.text(quote))
        done = self.client.post("/order", data=self.order_form(), follow_redirects=True)
        self.assertEqual(done.status_code, 200)
        self.assertIn("Ерлан Т.", self.text(done))
        self.assertIn("Подъедет через 4 мин", self.text(done))

    def test_consent_is_required(self):
        """Э-02: без отметки согласия заказ не создаётся (формат ввода — 400)."""
        data = self.order_form()
        del data["consent"]
        response = self.client.post("/order", data=data)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Отметьте согласие", self.text(response))

    def test_unknown_address_shows_message_on_first_screen(self):
        """Особое состояние Э-01: адрес не найден."""
        response = self.client.get("/quote", query_string={"destination": "нигде"})
        self.assertEqual(response.status_code, 404)
        self.assertIn("Такой адрес не нашли", self.text(response))
        self.assertIn("Куда едем?", self.text(response))

    def test_connection_error_screen(self):
        """Особое состояние Э-02 (исключение 4а): «Ошибка соединения» и «Повторить»."""
        failure = RoutingServiceError()
        with patch("carider.orders.repository.find_place", side_effect=failure):
            response = self.client.get("/quote", query_string={"destination": DEST})
        self.assertEqual(response.status_code, 503)
        self.assertIn("Ошибка соединения", self.text(response))
        self.assertIn("Повторить", self.text(response))

    def test_no_drivers_screen_and_cancel(self):
        """Особое состояние Э-03 (5а): «Свободных машин нет», затем отмена → Э-05."""
        busy_drivers(self.path)
        with patch("carider.dispatch.services.SEARCH_TIMEOUT", timedelta(0)):
            page = self.client.post(
                "/order", data=self.order_form(), follow_redirects=True
            )
        self.assertIn("Свободных машин нет", self.text(page))
        self.assertIn("Повторить поиск", self.text(page))
        cancelled = self.client.post("/orders/1/cancel", follow_redirects=True)
        self.assertIn("отменён", self.text(cancelled))
        self.assertIn("Штраф не взят", self.text(cancelled))

    def test_admin_requires_password(self):
        """Админ-панель закрыта паролем; с паролем видны таблицы."""
        self.assertEqual(self.client.get("/admin/").status_code, 401)
        token = base64.b64encode(b"admin:admin").decode()
        headers = {"Authorization": f"Basic {token}"}
        index = self.client.get("/admin/", headers=headers)
        self.assertIn("Клиенты", self.text(index))
        clients = self.client.get("/admin/clients/", headers=headers)
        self.assertIn(PHONE, self.text(clients))
        self.assertIn(PHONE_2, self.text(clients))

    def test_commands_migrate_and_loaddata(self):
        """Команды flask migrate и flask loaddata работают."""
        runner = self.app.test_cli_runner()
        self.assertIn("применено миграций — 0", runner.invoke(args=["migrate"]).output)
        self.assertIn("Добавлено объектов: 0", runner.invoke(args=["loaddata"]).output)


if __name__ == "__main__":
    unittest.main()
