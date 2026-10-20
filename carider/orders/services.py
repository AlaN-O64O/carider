"""Слой бизнес-логики модуля «Заказы»: правила БП-xx живут здесь."""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from . import repository
from .errors import DestinationNotFoundError, InvalidDestinationError

MAX_DESTINATION_LENGTH = 250  # Словарь данных: «Пункт назначения», до 250 символов.
BASE_FARE_TG = 450  # Стоимость посадки, тг.
PRICE_PER_KM_TG = 200  # Тариф за километр, тг.
AVERAGE_SPEED_KMH = 30  # Средняя скорость по городу для оценки времени в пути.
FREE_CANCEL = timedelta(minutes=1)  # БП-05: бесплатная отмена в течение 1 минуты.


@dataclass(frozen=True)
class Quote:
    """Расчёт поездки, который клиент видит до подтверждения (БП-02)."""

    pickup: str
    destination: str
    distance_km: float
    price_tg: int
    duration_min: int
    free_cancel_seconds: int


def calculate_quote(destination: str) -> Quote:
    """Рассчитать стоимость и длительность поездки (шаги 1–2 UC-01)."""
    text = destination.strip()
    if not text:
        raise InvalidDestinationError("Укажите, куда поедем: начните вводить адрес")
    if len(text) > MAX_DESTINATION_LENGTH:
        raise InvalidDestinationError(
            "Адрес слишком длинный: максимум 250 символов. Сократите его"
        )

    place = repository.find_place(text)
    if place is None:
        raise DestinationNotFoundError(
            "Такой адрес не нашли. Проверьте написание или добавьте номер дома"
        )

    distance = place["distance_km"]
    price = round((BASE_FARE_TG + PRICE_PER_KM_TG * distance) / 10) * 10
    duration = math.ceil(distance / AVERAGE_SPEED_KMH * 60)
    return Quote(
        pickup=repository.PICKUP_ADDRESS,
        destination=place["name"],
        distance_km=distance,
        price_tg=price,
        duration_min=duration,
        free_cancel_seconds=int(FREE_CANCEL.total_seconds()),
    )


def is_free_cancel(created_at: datetime, now: datetime) -> bool:
    """БП-05: отмена бесплатна в течение 1 минуты после создания заказа."""
    return now - created_at <= FREE_CANCEL


def list_destination_hints() -> list[str]:
    """Подсказки адресов для экрана Э-01."""
    return repository.list_place_names()
