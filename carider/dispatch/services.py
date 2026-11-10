"""Слой бизнес-логики модуля «Подбор водителя»: шаги 5–6 UC-01, БП-01."""

import math
from dataclasses import dataclass
from datetime import timedelta

from carider.accounts import services as accounts
from carider.orders import services as orders
from carider.orders.errors import DriverBusyError, OrderStateError
from carider.orders.models import OrderStatus

from . import repository
from .errors import NoDriversError

SEARCH_TIMEOUT = timedelta(seconds=15)  # БП-01 и исключение 5а: поиск до 15 с.
SEARCH_RADIUS_KM = 5.0  # Радиус поиска ближайшего таксиста.
DRIVER_SPEED_KMH = 30  # Скорость, по которой оценивается время подъезда.
EARTH_RADIUS_KM = 6371


@dataclass(frozen=True)
class DriverOffer:
    """Назначенный таксист в том виде, в котором его видит клиент (Э-04)."""

    name: str
    car: str
    plate: str
    eta_min: int | None


def haversine_km(lat1, lon1, lat2, lon2):
    """Расстояние между двумя точками на земле, км."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * (
        math.sin(d_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def nearest_free_drivers(conn, lat, lon):
    """Свободные таксисты в радиусе поиска: ближайший первым."""
    found = []
    for driver in accounts.list_free_drivers(conn):
        position = repository.get_position(conn, driver.id)
        if position is None:
            continue
        distance = haversine_km(lat, lon, position.lat, position.lon)
        if distance <= SEARCH_RADIUS_KM:
            found.append((distance, driver))
    return sorted(found, key=lambda item: item[0])


def _try_assign(conn, order):
    """Назначить ближайшего свободного таксиста. True — получилось."""
    for _distance, driver in nearest_free_drivers(
        conn, order.pickup_lat, order.pickup_lon
    ):
        try:
            orders.assign_driver(conn, order.id, driver.id)
        except DriverBusyError:
            continue  # Т-5: таксиста только что занял другой заказ, берём следующего
        return True
    return False


def _offer(conn, order):
    driver = accounts.get_driver(conn, order.driver_id)
    position = repository.get_position(conn, driver.id)
    eta = None
    if position is not None:
        distance = haversine_km(
            order.pickup_lat, order.pickup_lon, position.lat, position.lon
        )
        eta = max(1, math.ceil(distance / DRIVER_SPEED_KMH * 60))
    return DriverOffer(
        name=driver.short_name,
        car=driver.car_model,
        plate=driver.plate,
        eta_min=eta,
    )


def on_order_created(*, conn, order, now):
    """Шаг 4 UC-01: заказ создан, запускаем автоматический поиск таксиста."""
    orders.mark_search_started(conn, order.id, now)
    _try_assign(conn, order)


def find_driver(conn, order_id, now=None):
    """Шаги 5–6 UC-01: результат поиска таксиста.

    Возвращает DriverOffer, если таксист назначен, и None, если поиск ещё
    идёт. Исключение 5а: если за SEARCH_TIMEOUT никто не найден — NoDriversError.
    """
    now = now or orders.now_utc()
    order = orders.get_order(conn, order_id)
    if order.status == OrderStatus.ASSIGNED:
        return _offer(conn, order)
    if order.status != OrderStatus.CREATED:
        raise OrderStateError()
    if _try_assign(conn, order):
        return _offer(conn, orders.get_order(conn, order_id))
    started = order.search_started_at or order.created_at
    if now - started >= SEARCH_TIMEOUT:
        raise NoDriversError()
    return None


def repeat_search(conn, order_id, now=None):
    """Исключение 5а: клиент выбрал «Повторить поиск»."""
    now = now or orders.now_utc()
    order = orders.get_order(conn, order_id)
    if order.status != OrderStatus.CREATED:
        raise OrderStateError()
    orders.mark_search_started(conn, order.id, now)
    _try_assign(conn, order)
