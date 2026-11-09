"""Слой данных модуля «Аккаунты»: сущности «Клиент» и «Таксист» (ЛР №4)."""

from dataclasses import dataclass

DRIVER_STATUS_LABELS = {
    "free": "Свободен",
    "busy": "Занят",
    "on_shift": "На смене",
}


@dataclass(frozen=True)
class Client:
    """Клиент: таблица clients."""

    verbose_name = "клиент"
    verbose_name_plural = "клиенты"

    id: int
    phone: str
    consent_pd: bool
    registered_at: str
    is_blocked: bool

    def __str__(self):
        return self.phone


@dataclass(frozen=True)
class Driver:
    """Таксист: таблица drivers."""

    verbose_name = "таксист"
    verbose_name_plural = "таксисты"

    id: int
    full_name: str
    phone: str
    car_model: str
    plate: str
    status: str

    def __str__(self):
        return self.full_name

    @property
    def short_name(self):
        """«Ерлан Темиров» -> «Ерлан Т.»: клиент не видит фамилию целиком."""
        parts = self.full_name.split()
        if len(parts) < 2:
            return self.full_name
        return f"{parts[0]} {parts[-1][0]}."

    @property
    def status_label(self):
        return DRIVER_STATUS_LABELS[self.status]
