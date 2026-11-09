"""Исключения модуля «Заказы»: каждое соответствует исходу сценария UC-01."""

from carider.errors import CariderError


class InvalidDestinationError(CariderError):
    """Пункт назначения пуст или длиннее 250 символов (словарь данных ЛР №4)."""

    http_status = 400
    code = "INVALID_DESTINATION"
    message = "Неверный пункт назначения."


class DestinationNotFoundError(CariderError):
    """Пункт назначения не найден (критерий приёмки US-03)."""

    http_status = 404
    code = "DESTINATION_NOT_FOUND"
    message = "Такой адрес не нашли. Проверьте написание или добавьте номер дома"


class RoutingServiceError(CariderError):
    """Исключение 4а UC-01: нет связи при расчёте цены, заказ не создаётся."""

    http_status = 503
    code = "SERVICE_UNAVAILABLE"
    message = "Ошибка соединения. Не удалось рассчитать стоимость."


class PriceChangedError(CariderError):
    """БП-02: клиент подтверждает именно ту цену, которую видел."""

    http_status = 409
    code = "PRICE_CHANGED"
    message = "Цена изменилась. Проверьте новую стоимость и подтвердите заказ."


class OrderNotFoundError(CariderError):
    http_status = 404
    code = "ORDER_NOT_FOUND"
    message = "Заказ не найден."


class OrderStateError(CariderError):
    """Действие недоступно в текущем состоянии заказа."""

    http_status = 409
    code = "ORDER_STATE"
    message = "Это действие недоступно: заказ уже в другом состоянии."


class DriverBusyError(CariderError):
    """Т-5: таксиста уже занял другой заказ (сработало ограничение СУБД)."""

    http_status = 409
    code = "DRIVER_BUSY"
    message = "Таксист уже занят другим заказом."
