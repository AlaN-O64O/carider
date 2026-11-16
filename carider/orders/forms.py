"""Проверка формата ввода (слой представления). Бизнес-правил здесь нет."""

import re

PHONE_RE = re.compile(r"\+7[0-9]{10}")


def validate_order_payload(data):
    """Проверить формат полей заказа.

    Возвращает пару: очищенные данные и словарь ошибок по полям.
    """
    errors = {}
    phone = str(data.get("phone", ""))
    if not PHONE_RE.fullmatch(phone):
        errors["phone"] = "Введите номер в формате +77011234567."

    price = 0
    try:
        price = int(data.get("price_tg"))
    except (TypeError, ValueError):
        errors["price_tg"] = "Цена должна быть целым числом."
    else:
        if price <= 0:
            errors["price_tg"] = "Цена должна быть больше нуля."

    clean = {
        "destination": str(data.get("destination", "")),
        "phone": phone,
        "price_tg": price,
    }
    return clean, errors
