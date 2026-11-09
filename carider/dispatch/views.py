"""Слой представления модуля «Подбор водителя»: экраны Э-03, Э-04 и API."""

from flask import Blueprint, jsonify, redirect, render_template, url_for

from carider.db import get_db
from carider.orders import services as orders
from carider.orders.models import OrderStatus
from carider.web import duration_text

from . import services
from .errors import NoDriversError

bp = Blueprint("dispatch", __name__, template_folder="templates")


def _free_cancel_text(order):
    return duration_text(orders.free_cancel_left(order, orders.now_utc()))


@bp.get("/orders/<int:order_id>/search")
def search_screen(order_id):
    """Э-03 «Поиск водителя»; особое состояние — «Свободных машин нет» (5а)."""
    conn = get_db()
    no_drivers = False
    try:
        offer = services.find_driver(conn, order_id)
    except NoDriversError:
        offer, no_drivers = None, True
    if offer is not None:
        return redirect(url_for("dispatch.driver_screen", order_id=order_id))
    order = orders.get_order(conn, order_id)
    return render_template(
        "dispatch/search.html",
        order=order,
        no_drivers=no_drivers,
        left_text=_free_cancel_text(order),
    )


@bp.post("/orders/<int:order_id>/search")
def repeat_search_screen(order_id):
    """Кнопка «Повторить поиск» (исключение 5а)."""
    services.repeat_search(get_db(), order_id)
    return redirect(url_for("dispatch.search_screen", order_id=order_id))


@bp.get("/orders/<int:order_id>/driver")
def driver_screen(order_id):
    """Э-04 «Водитель найден»: шаг 6 UC-01."""
    conn = get_db()
    order = orders.get_order(conn, order_id)
    if order.status != OrderStatus.ASSIGNED:
        return redirect(url_for("dispatch.search_screen", order_id=order_id))
    offer = services.find_driver(conn, order_id)
    return render_template(
        "dispatch/driver.html",
        order=order,
        offer=offer,
        left_text=_free_cancel_text(order),
    )


@bp.get("/api/orders/<int:order_id>/driver/")
def api_driver(order_id):
    """Операция 3: GET /api/orders/{id}/driver/ — результат поиска таксиста."""
    offer = services.find_driver(get_db(), order_id)
    if offer is None:
        return jsonify({"status": "Создан"}), 202
    return jsonify(
        {
            "status": "Назначен",
            "driver": {
                "name": offer.name,
                "car": offer.car,
                "plate": offer.plate,
                "eta_min": offer.eta_min,
            },
        }
    )


@bp.post("/api/orders/<int:order_id>/search/")
def api_repeat_search(order_id):
    """Операция 4: POST /api/orders/{id}/search/ — повторить поиск."""
    services.repeat_search(get_db(), order_id)
    return jsonify({"status": "Создан"}), 202
