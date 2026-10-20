"""Ошибки модуля «Заказы». Каждая соответствует исключению сценария UC-01."""


class OrderError(Exception):
    """Базовая ошибка модуля; несёт код и сообщение для клиента."""

    code = "ORDER_ERROR"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class InvalidDestinationError(OrderError):
    """Пункт назначения пуст или длиннее 250 символов (словарь данных ЛР №4)."""

    code = "INVALID_DESTINATION"


class DestinationNotFoundError(OrderError):
    """Пункт назначения не найден (критерий приёмки US-03)."""

    code = "DESTINATION_NOT_FOUND"


class RoutingServiceError(OrderError):
    """Нет связи с сервисом расчёта маршрута (исключение 4а UC-01)."""

    code = "SERVICE_UNAVAILABLE"
