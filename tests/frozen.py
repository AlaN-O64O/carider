"""Помощники тестов ЛР №8: общее «сейчас» и заглушка часов."""

import os
import tempfile
import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from carider import create_app, db, wiring

# «Сейчас» для всех тестов «чёрного ящика»: вторник 10.11.2026, 12:30 UTC.
NOW = datetime(2026, 11, 10, 12, 30, tzinfo=UTC)
PHONE = "+77010000001"  # клиент из фикстуры demo
PHONE_2 = "+77010000002"
PHONE_BLOCKED = "+77010000003"
DEST = "ул. Ауэзова, 42"  # 7 км: 1 850 тг, 14 мин
PRICE = 1850


class FrozenTimeTestCase(unittest.TestCase):
    """База для тестов слоя логики: чистая БД и часы, остановленные на NOW.

    Заглушка подменяет orders.services.now_utc(): это единственное место,
    откуда проект берёт текущее время, поэтому все тесты живут в одном «сейчас».
    """

    def setUp(self):
        self.conn = db.get_connection(":memory:")
        db.migrate(self.conn)
        db.load_fixture(self.conn, "demo")
        wiring.connect_modules()
        self.addCleanup(self.conn.close)
        patcher = self.clock(NOW)
        patcher.start()
        self.addCleanup(patcher.stop)

    def clock(self, moment):
        """Заглушка часов: now_utc() вернёт moment."""
        return patch("carider.orders.services.now_utc", return_value=moment)

    def busy_all(self, except_id=None):
        """Сделать всех таксистов занятыми (кроме одного, если указан)."""
        self.conn.execute(
            "UPDATE drivers SET status = 'busy' WHERE id IS NOT ?", (except_id,)
        )
        self.conn.commit()

    def status_of(self, table, row_id):
        row = self.conn.execute(
            f"SELECT status FROM {table} WHERE id = ?", (row_id,)
        ).fetchone()
        return row["status"]


class FrozenApiTestCase(unittest.TestCase):
    """База для тестов через HTTP: Flask-приложение, файловая БД, часы на NOW."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = os.path.join(folder.name, "test.sqlite3")
        conn = db.get_connection(self.path)
        db.migrate(conn)
        db.load_fixture(conn, "demo")
        conn.close()
        app = create_app({"DATABASE": self.path, "TESTING": True})
        self.client = app.test_client()
        patcher = self.clock(NOW)
        patcher.start()
        self.addCleanup(patcher.stop)

    def clock(self, moment):
        return patch("carider.orders.services.now_utc", return_value=moment)

    def run_sql(self, sql, params=()):
        """Выполнить SQL прямо в базе приложения (подготовка данных теста)."""
        conn = db.get_connection(self.path)
        conn.execute(sql, params)
        conn.commit()
        conn.close()

    def busy_all(self):
        self.run_sql("UPDATE drivers SET status = 'busy'")

    def order_payload(self, **changes):
        payload = {"destination": DEST, "price_tg": PRICE, "phone": PHONE}
        payload.update(changes)
        return payload

    def post_order(self, **changes):
        return self.client.post("/api/orders/", json=self.order_payload(**changes))
