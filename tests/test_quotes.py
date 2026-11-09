"""Шаги 1–2 UC-01: расчёт стоимости (тесты ЛР №6, теперь с базой данных)."""

import unittest

from carider.orders import services
from carider.orders.errors import DestinationNotFoundError, InvalidDestinationError

from .helpers import DEST, make_conn


class QuoteRulesTest(unittest.TestCase):
    def setUp(self):
        self.conn = make_conn()
        self.addCleanup(self.conn.close)

    def test_quote_matches_prototype(self):
        """Расчёт до ул. Ауэзова, 42 совпадает с вайрфреймом Э-02."""
        quote = services.calculate_quote(self.conn, DEST)
        self.assertEqual(quote.price_tg, 1850)
        self.assertEqual(quote.duration_min, 14)

    def test_quote_ignores_case_and_spaces(self):
        """Адрес находится без учёта регистра и лишних пробелов."""
        quote = services.calculate_quote(self.conn, "  УЛ.  ауэзова, 42 ")
        self.assertEqual(quote.destination, DEST)

    def test_empty_destination_rejected(self):
        """Пустой пункт назначения: InvalidDestinationError (400)."""
        with self.assertRaises(InvalidDestinationError):
            services.calculate_quote(self.conn, "   ")

    def test_destination_length_boundary(self):
        """Граница 250 символов: 250 проходит проверку длины, 251 — нет."""
        with self.assertRaises(DestinationNotFoundError):  # длина ок, адреса нет
            services.calculate_quote(self.conn, "а" * 250)
        with self.assertRaises(InvalidDestinationError):
            services.calculate_quote(self.conn, "а" * 251)

    def test_unknown_destination_not_found(self):
        """Адрес не найден: DestinationNotFoundError (404)."""
        with self.assertRaises(DestinationNotFoundError):
            services.calculate_quote(self.conn, "несуществующая улица, 1")
