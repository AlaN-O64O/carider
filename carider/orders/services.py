"""Слой бизнес-логики модуля «Заказы»: шаги 1–4 UC-01, правила БП-02 и БП-05."""

import math
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from carider import events
from carider.accounts import services as accounts

from . import repository
from .errors import (
    DestinationNotFoundError,
    DriverBusyError,
    InvalidDestinationError,
    OrderNotFoundError,
    OrderStateError,
    PriceChangedError,
)
from .models import OrderStatus

MAX_DESTINATION_LENGTH = 250  # Словарь данных: «Пункт назначения», до 250 символов.
BASE_FARE_TG = 450  # Стоимость посадки, тг.
PRICE_PER_KM_TG = 200  # Тариф за километр, тг.
AVERAGE_SPEED_KMH = 30  # Средняя скорость по городу для оценки времени в пути.
FREE_CANCEL = timedelta(minutes=1)  # БП-05: бесплатная отмена — 1 минута.


@dataclass(frozen=True)
class Quote:
    """Расчёт поездки, который клиент видит до подтверждения (БП-02)."""

    pickup: str
    destination: str
    distance_km: float
    price_tg: int
    duration_min: int
    free_cancel_seconds: int


def now_utc():
    """Текущее время с часовым поясом UTC (единый источник времени)."""
    return datetime.now()


def calculate_quote(conn, destination):
    """Шаги 1–2 UC-01: рассчитать стоимость и длительность поездки."""
    text = destination.strip()
    if not text:
        raise InvalidDestinationError("Укажите, куда поедем: начните вводить адрес")
    if len(text) > MAX_DESTINATION_LENGTH:
        raise InvalidDestinationError(
            "Адрес слишком длинный: максимум 250 символов. Сократите его"
        )

    place = repository.find_place(conn, text)
    if place is None:
        raise DestinationNotFoundError()

    price = round((BASE_FARE_TG + PRICE_PER_KM_TG * place.distance_km) / 10) * 10
    duration = math.ceil(place.distance_km / AVERAGE_SPEED_KMH * 60)
    return Quote(
        pickup=repository.PICKUP_ADDRESS,
        destination=place.name,
        distance_km=place.distance_km,
        price_tg=price,
        duration_min=duration,
        free_cancel_seconds=int(FREE_CANCEL.total_seconds()),
    )


def create_order(conn, phone, destination, price_tg, now=None):
    """Шаги 3–4 UC-01: клиент подтвердил цену, система создаёт заказ.

    БП-02: подтверждается та цена, которую клиент видел. Поиск таксиста
    запускает событие «заказ создан» (его слушает модуль dispatch). Ответ
    описывает момент создания: результат поиска клиент получит отдельно.
    """
    now = now or now_utc()
    client = accounts.get_active_client(conn, phone)
    quote = calculate_quote(conn, destination)
    if price_tg != quote.price_tg:
        raise PriceChangedError()
    with conn:
        order = repository.insert_order(
            conn, client.id, quote.destination, quote.price_tg, now
        )
    events.publish("order_created", conn=conn, order=order, now=now)
    return order


def get_order(conn, order_id):
    """Заказ по номеру или исключение OrderNotFoundError."""
    order = repository.get_order(conn, order_id)
    if order is None:
        raise OrderNotFoundError()
    return order


def is_free_cancel(created_at, now):
    """БП-05: отмена бесплатна в течение 1 минуты после создания заказа."""
    return now - created_at <= FREE_CANCEL


def free_cancel_left(order, now):
    """Сколько секунд осталось на бесплатную отмену (не меньше нуля)."""
    left = FREE_CANCEL - (now - order.created_at)
    return max(0, math.ceil(left.total_seconds()))


def cancel_order(conn, order_id, now=None):
    """Отмена заказа клиентом (БП-05); освобождает таксиста."""
    now = now or now_utc()
    order = get_order(conn, order_id)
    if order.status not in (OrderStatus.CREATED, OrderStatus.ASSIGNED):
        raise OrderStateError()
    penalty = not is_free_cancel(order.created_at, now)
    with conn:
        repository.mark_cancelled(conn, order.id, now, penalty)
        if order.driver_id is not None:
            accounts.mark_driver_free(conn, order.driver_id)
    return get_order(conn, order_id)


def assign_driver(conn, order_id, driver_id):
    """Назначить таксиста на заказ (его вызывает модуль dispatch).

    Т-5: «сначала проверить, потом назначить» не защищает от гонки, поэтому
    защита — ограничение СУБД. Если таксиста успел занять другой заказ,
    UPDATE падает с IntegrityError, а мы превращаем его в DriverBusyError.
    """
    try:
        with conn:
            repository.assign_driver(conn, order_id, driver_id)
            accounts.mark_driver_busy(conn, driver_id)
    except sqlite3.IntegrityError:
        raise DriverBusyError() from None


def mark_search_started(conn, order_id, started_at):
    """Запомнить, когда начат (или повторён) поиск таксиста."""
    with conn:
        repository.set_search_started(conn, order_id, started_at)


def list_destination_hints(conn):
    """Подсказки адресов для экрана Э-01."""
    return repository.list_place_names(conn)
