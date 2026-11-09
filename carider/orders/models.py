"""Слой данных модуля «Заказы»: сущность «Заказ» и справочник адресов."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class OrderStatus(StrEnum):
    """Состояния заказа из словаря данных ЛР №4."""

    CREATED = "created"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


STATUS_LABELS = {
    OrderStatus.CREATED: "Создан",
    OrderStatus.ASSIGNED: "Назначен",
    OrderStatus.IN_PROGRESS: "Выполняется",
    OrderStatus.COMPLETED: "Завершён",
    OrderStatus.CANCELLED: "Отменён",
}


@dataclass(frozen=True)
class Place:
    """Известный адрес: таблица places."""

    verbose_name = "адрес"
    verbose_name_plural = "адреса"

    id: int
    name: str
    distance_km: float

    def __str__(self):
        return self.name


@dataclass(frozen=True)
class Order:
    """Заказ: таблица orders."""

    verbose_name = "заказ"
    verbose_name_plural = "заказы"

    id: int
    client_id: int
    driver_id: int | None
    pickup: str
    pickup_lat: float
    pickup_lon: float
    destination: str
    price_tg: int
    status: str
    created_at: datetime
    search_started_at: datetime | None
    cancelled_at: datetime | None
    penalty: bool

    def __str__(self):
        return f"Заказ № {self.id}"

    @property
    def status_label(self):
        return STATUS_LABELS[OrderStatus(self.status)]
