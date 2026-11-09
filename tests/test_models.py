"""Модели и таблицы: классы соответствуют миграциям и словарю данных."""

import unittest
from dataclasses import fields

from carider import db
from carider.accounts.models import Client, Driver
from carider.dispatch.models import DriverPosition
from carider.orders.models import Order, Place

from .helpers import make_conn

MODELS = {
    "clients": Client,
    "drivers": Driver,
    "orders": Order,
    "places": Place,
    "driver_positions": DriverPosition,
}


class ModelsTest(unittest.TestCase):
    def setUp(self):
        self.conn = make_conn()
        self.addCleanup(self.conn.close)

    def test_model_fields_match_table_columns(self):
        """У каждой модели поля совпадают со столбцами таблицы после миграций."""
        for table, model in MODELS.items():
            info = self.conn.execute(f"PRAGMA table_info({table})")
            columns = {row["name"] for row in info}
            names = {f.name for f in fields(model)}
            self.assertEqual(names, columns, table)

    def test_every_model_has_russian_names_and_str(self):
        """У каждой модели есть verbose_name и __str__."""
        for model in MODELS.values():
            self.assertTrue(model.verbose_name)
            self.assertTrue(model.verbose_name_plural)
            self.assertIn("__str__", vars(model))

    def test_migrations_are_applied_once(self):
        """Повторный запуск migrate ничего не меняет."""
        self.assertEqual(db.migrate(self.conn), [])

    def test_fixture_is_loaded_and_safe_to_repeat(self):
        """Фикстура demo даёт 18 объектов; повторная загрузка ничего не добавляет."""
        total = sum(
            self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in MODELS
        )
        self.assertEqual(total, 18)
        self.assertEqual(db.load_fixture(self.conn, "demo"), 0)

    def test_driver_short_name_hides_surname(self):
        """Клиент видит «Ерлан Т.», а не полное ФИО (БП-06)."""
        driver = Driver(1, "Ерлан Темиров", "+77020000001", "Toyota", "1", "free")
        self.assertEqual(driver.short_name, "Ерлан Т.")
        self.assertEqual(driver.status_label, "Свободен")
