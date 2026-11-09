"""Исключения модуля «Подбор водителя»."""

from carider.errors import CariderError


class NoDriversError(CariderError):
    """Исключение 5а UC-01: за 15 секунд не нашлось свободного таксиста."""

    http_status = 409
    code = "NO_DRIVERS"
    message = "Свободных машин нет"
