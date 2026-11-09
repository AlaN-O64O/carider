"""Исключения модуля «Аккаунты»."""

from carider.errors import CariderError


class ClientNotFoundError(CariderError):
    """Предусловие UC-01 нарушено: клиент не найден."""

    http_status = 401
    code = "UNAUTHORIZED"
    message = "Клиент не найден. Войдите заново."


class ClientBlockedError(CariderError):
    """Клиент заблокирован (атрибут «Статус блокировки»)."""

    http_status = 403
    code = "CLIENT_BLOCKED"
    message = "Аккаунт заблокирован. Обратитесь в поддержку."
