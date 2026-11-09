"""Слой бизнес-логики модуля «Аккаунты»."""

from . import repository
from .errors import ClientBlockedError, ClientNotFoundError


def get_active_client(conn, phone):
    """Предусловие UC-01: клиент зарегистрирован и не заблокирован.

    Пока клиента определяет номер телефона; вход по SMS-коду появится
    в следующей итерации.
    """
    client = repository.get_client_by_phone(conn, phone)
    if client is None:
        raise ClientNotFoundError()
    if client.is_blocked:
        raise ClientBlockedError()
    return client


def get_driver(conn, driver_id):
    """Таксист по номеру (или None)."""
    return repository.get_driver(conn, driver_id)


def list_free_drivers(conn):
    """Таксисты со статусом «Свободен»."""
    return repository.list_drivers_by_status(conn, "free")


def mark_driver_busy(conn, driver_id):
    """Статус «Занят» (коммит — на вызывающем)."""
    repository.set_driver_status(conn, driver_id, "busy")


def mark_driver_free(conn, driver_id):
    """Статус «Свободен» (коммит — на вызывающем)."""
    repository.set_driver_status(conn, driver_id, "free")
