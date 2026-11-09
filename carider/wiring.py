"""Корень композиции: связывает модули через события."""

from carider import events
from carider.dispatch import services as dispatch


def connect_modules():
    """Подписать dispatch на создание заказа."""
    events.subscribe("order_created", dispatch.on_order_created)
