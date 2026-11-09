"""Общие помощники тестов: чистая база с демонстрационными данными."""

import os
import tempfile
from datetime import UTC, datetime

from carider import create_app, db, wiring

T0 = datetime.now(UTC).replace(microsecond=0)  # «сейчас»; остальное — от него
PHONE = "+77010000001"  # клиент из фикстуры
PHONE_2 = "+77010000002"
PHONE_BLOCKED = "+77010000003"
DEST = "ул. Ауэзова, 42"  # 7 км: 1 850 тг, 14 мин


def make_conn():
    """База в памяти: миграции + фикстура demo + подписка модулей."""
    conn = db.get_connection(":memory:")
    db.migrate(conn)
    db.load_fixture(conn, "demo")
    wiring.connect_modules()
    return conn


def make_app_client(test_case):
    """Flask-приложение с файловой базой во временной папке."""
    folder = tempfile.TemporaryDirectory()
    test_case.addCleanup(folder.cleanup)
    path = os.path.join(folder.name, "test.sqlite3")
    conn = db.get_connection(path)
    db.migrate(conn)
    db.load_fixture(conn, "demo")
    conn.close()
    app = create_app({"DATABASE": path, "TESTING": True})
    return app, app.test_client(), path


def set_all_drivers_busy(conn, except_id=None):
    """Сделать всех таксистов занятыми (кроме одного, если указан)."""
    conn.execute("UPDATE drivers SET status = 'busy' WHERE id IS NOT ?", (except_id,))
    conn.commit()
