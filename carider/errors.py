"""Общий базовый класс исключений UC-01 (общий для всех модулей)."""


class CariderError(Exception):
    """Запланированный исход сценария, а не сбой программы.

    Наследники задают код ответа API (http_status), машинный код (code)
    и текст для экрана (message). Слой представления ловит этот класс
    один раз и не знает, какие наследники существуют (полиморфизм).
    """

    http_status = 400
    code = "ERROR"
    message = "Операция невозможна."

    def __init__(self, message: str | None = None):
        super().__init__(message or self.message)
        self.message = message or self.message
