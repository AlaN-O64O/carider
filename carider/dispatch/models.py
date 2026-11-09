"""Слой данных модуля «Подбор водителя»: положение таксиста."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DriverPosition:
    """Последнее известное положение таксиста: таблица driver_positions."""

    verbose_name = "положение таксиста"
    verbose_name_plural = "положения таксистов"

    driver_id: int
    lat: float
    lon: float
    updated_at: str

    def __str__(self):
        return f"таксист {self.driver_id}: {self.lat:.4f}, {self.lon:.4f}"
