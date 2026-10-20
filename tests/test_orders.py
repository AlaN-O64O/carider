"""Тесты модуля «Заказы»: бизнес-правила, экраны и API."""

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from carider import create_app
from carider.orders import services
from carider.orders.errors import (
    DestinationNotFoundError,
    InvalidDestinationError,
    RoutingServiceError,
)


class QuoteRulesTest(unittest.TestCase):
    def test_quote_matches_prototype(self):
        """Расчёт до ул. Ауэзова, 42 совпадает с вайрфреймом Э-02."""
        quote = services.calculate_quote("ул. Ауэзова, 42")
        self.assertEqual(quote.price_tg, 1850)
        self.assertEqual(quote.duration_min, 14)

    def test_free_cancel_within_one_minute(self):
        """БП-05: отмена бесплатна в течение 1 минуты, позже — со штрафом."""
        created = datetime(2026, 10, 19, 12, 0, 0)
        in_time = created + timedelta(seconds=59)
        on_limit = created + timedelta(seconds=60)
        too_late = created + timedelta(seconds=61)
        self.assertTrue(services.is_free_cancel(created, in_time))
        self.assertTrue(services.is_free_cancel(created, on_limit))
        self.assertFalse(services.is_free_cancel(created, too_late))

    def test_empty_destination_rejected(self):
        with self.assertRaises(InvalidDestinationError):
            services.calculate_quote("   ")

    def test_too_long_destination_rejected(self):
        with self.assertRaises(InvalidDestinationError):
            services.calculate_quote("а" * 251)

    def test_unknown_destination_not_found(self):
        with self.assertRaises(DestinationNotFoundError):
            services.calculate_quote("несуществующая улица, 1")


class ScreensAndApiTest(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def page(self, response):
        return response.get_data(as_text=True)

    def test_destination_screen_opens(self):
        """Э-01 открывается."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Куда едем?", self.page(response))

    def test_quote_screen_shows_price(self):
        """Э-02 показывает цену и условия отмены (БП-02)."""
        response = self.client.get("/quote", query_string={"destination": "аэропорт"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("4 050 тг", self.page(response))
        self.assertIn("Условия отмены", self.page(response))

    def test_quote_screen_unknown_address(self):
        """Адрес не найден: остаёмся на Э-01 и показываем сообщение."""
        response = self.client.get("/quote", query_string={"destination": "нигде"})
        self.assertEqual(response.status_code, 404)
        self.assertIn("Такой адрес не нашли", self.page(response))

    def test_api_quote_ok(self):
        payload = {"destination": "ул. Ауэзова, 42"}
        response = self.client.post("/api/quotes/", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["price_tg"], 1850)

    def test_api_quote_empty_destination(self):
        response = self.client.post("/api/quotes/", json={"destination": ""})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"]["code"], "INVALID_DESTINATION")

    def test_api_quote_unknown_destination(self):
        response = self.client.post("/api/quotes/", json={"destination": "нигде"})
        self.assertEqual(response.status_code, 404)

    def test_api_quote_connection_error(self):
        """Исключение 4а UC-01: нет связи при расчёте — 503, заказ не создан."""
        failure = RoutingServiceError("нет связи")
        with patch("carider.orders.repository.find_place", side_effect=failure):
            payload = {"destination": "аэропорт"}
            response = self.client.post("/api/quotes/", json=payload)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"]["code"], "SERVICE_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
