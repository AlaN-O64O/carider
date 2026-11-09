"""Слой доступа к данным модуля «Заказы»."""

from datetime import datetime

from .models import Order, Place

# Положение клиента. В реальной системе его присылает телефон (геолокация),
# поэтому это заглушка внешней системы, а не данные из БД.
PICKUP_ADDRESS = "ул. Абая, 15"
PICKUP_POINT = (51.1280, 71.4300)


def _normalize(text):
    return " ".join(text.lower().split())


def _time(value):
    return datetime.fromisoformat(value) if value else None


def _order(row):
    return Order(
        id=row["id"],
        client_id=row["client_id"],
        driver_id=row["driver_id"],
        pickup=row["pickup"],
        pickup_lat=row["pickup_lat"],
        pickup_lon=row["pickup_lon"],
        destination=row["destination"],
        price_tg=row["price_tg"],
        status=row["status"],
        created_at=_time(row["created_at"]),
        search_started_at=_time(row["search_started_at"]),
        cancelled_at=_time(row["cancelled_at"]),
        penalty=bool(row["penalty"]),
    )


def find_place(conn, text):
    """Найти адрес без учёта регистра и лишних пробелов или вернуть None.

    Сравнение делается в Python: функция lower() в SQLite не понимает
    кириллицу.
    """
    wanted = _normalize(text)
    for row in conn.execute("SELECT * FROM places"):
        if _normalize(row["name"]) == wanted:
            return Place(**dict(row))
    return None


def list_place_names(conn):
    """Названия адресов для подсказок на экране Э-01."""
    return [row["name"] for row in conn.execute("SELECT name FROM places ORDER BY id")]


def insert_order(conn, client_id, destination, price_tg, created_at):
    """Создать заказ в состоянии «Создан» (коммит — на вызывающем)."""
    lat, lon = PICKUP_POINT
    cursor = conn.execute(
        "INSERT INTO orders (client_id, pickup, pickup_lat, pickup_lon, "
        "destination, price_tg, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            client_id,
            PICKUP_ADDRESS,
            lat,
            lon,
            destination,
            price_tg,
            created_at.isoformat(),
        ),
    )
    return get_order(conn, cursor.lastrowid)


def get_order(conn, order_id):
    """Заказ по номеру или None."""
    row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    return _order(row) if row else None


def assign_driver(conn, order_id, driver_id):
    """Назначить таксиста. Второй активный заказ того же таксиста — IntegrityError."""
    conn.execute(
        "UPDATE orders SET driver_id = ?, status = 'assigned' WHERE id = ?",
        (driver_id, order_id),
    )


def set_search_started(conn, order_id, started_at):
    conn.execute(
        "UPDATE orders SET search_started_at = ? WHERE id = ?",
        (started_at.isoformat(), order_id),
    )


def mark_cancelled(conn, order_id, cancelled_at, penalty):
    conn.execute(
        "UPDATE orders SET status = 'cancelled', cancelled_at = ?, penalty = ? "
        "WHERE id = ?",
        (cancelled_at.isoformat(), int(penalty), order_id),
    )
