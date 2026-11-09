"""Слой доступа к данным модуля «Аккаунты»."""

from .models import Client, Driver


def _client(row):
    return Client(
        id=row["id"],
        phone=row["phone"],
        consent_pd=bool(row["consent_pd"]),
        registered_at=row["registered_at"],
        is_blocked=bool(row["is_blocked"]),
    )


def _driver(row):
    return Driver(**dict(row))


def get_client_by_phone(conn, phone):
    """Найти клиента по телефону или вернуть None."""
    row = conn.execute("SELECT * FROM clients WHERE phone = ?", (phone,)).fetchone()
    return _client(row) if row else None


def get_driver(conn, driver_id):
    """Найти таксиста по номеру или вернуть None."""
    row = conn.execute("SELECT * FROM drivers WHERE id = ?", (driver_id,)).fetchone()
    return _driver(row) if row else None


def list_drivers_by_status(conn, status):
    """Все таксисты с данным статусом занятости."""
    rows = conn.execute("SELECT * FROM drivers WHERE status = ?", (status,))
    return [_driver(row) for row in rows]


def set_driver_status(conn, driver_id, status):
    """Сменить статус занятости (коммит — на вызывающем)."""
    conn.execute("UPDATE drivers SET status = ? WHERE id = ?", (status, driver_id))
