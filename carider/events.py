"""Простая шина событий.

Модуль публикует событие и не знает, кто на него подписан. Так orders
запускает поиск таксиста, не импортируя dispatch: в таблице модулей
(ЛР №6) между ними нет прямой зависимости.
"""

from collections import defaultdict

_handlers = defaultdict(set)


def subscribe(event, handler):
    """Подписать функцию на событие (повторная подписка безвредна)."""
    _handlers[event].add(handler)


def publish(event, **payload):
    """Вызвать всех подписчиков события."""
    for handler in list(_handlers[event]):
        handler(**payload)
