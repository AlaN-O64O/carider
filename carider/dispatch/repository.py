"""Слой доступа к данным модуля «Подбор водителя»."""

from .models import DriverPosition


def get_position(conn, driver_id):
    """Положение таксиста или None, если оно неизвестно."""
    row = conn.execute(
        "SELECT * FROM driver_positions WHERE driver_id = ?", (driver_id,)
    ).fetchone()
    return DriverPosition(**dict(row)) if row else None
