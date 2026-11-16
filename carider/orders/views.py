"""Слой представления модуля «Заказы»: экраны Э-01, Э-02, Э-05 и API."""

from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from carider.db import get_db
from carider.errors import CariderError

from . import forms, services
from .errors import (
    DestinationNotFoundError,
    InvalidDestinationError,
    OrderStateError,
    RoutingServiceError,
)
from .models import OrderStatus

bp = Blueprint("orders", __name__, template_folder="templates")


@bp.app_template_filter("tg")
def format_tg(value):
    """Сумма с пробелом между разрядами: 1850 -> «1 850»."""
    return f"{value:,}".replace(",", " ")


def _destination_page(destination, error=None, status=200):
    page = render_template(
        "orders/destination.html",
        hints=services.list_destination_hints(get_db()),
        destination=destination,
        error=error,
    )
    return page, status


def _quote_page(destination, form_error=None, form_status=200):
    """Э-02 с расчётом; при ошибке — особое состояние экрана из ЛР №5."""
    try:
        quote = services.calculate_quote(get_db(), destination)
    except RoutingServiceError as error:  # исключение 4а
        page = render_template("orders/quote.html", quote=None, error=error.message)
        return page, error.http_status
    except (InvalidDestinationError, DestinationNotFoundError) as error:
        return _destination_page(destination, error.message, error.http_status)
    page = render_template(
        "orders/quote.html", quote=quote, error=None, form_error=form_error
    )
    return page, form_status


@bp.get("/")
def destination_screen():
    """Э-01 «Куда едем?»."""
    return _destination_page("")


@bp.get("/quote")
def quote_screen():
    """Э-02 «Стоимость и условия»."""
    return _quote_page(request.args.get("destination", ""))


@bp.post("/order")
def create_order_screen():
    """Кнопка «Заказать» на Э-02: шаги 3–4 UC-01."""
    data = {
        "destination": request.form.get("destination", ""),
        "price_tg": request.form.get("price_tg"),
        "phone": current_app.config["DEMO_CLIENT_PHONE"],  # вход по SMS — позже
    }
    clean, errors = forms.validate_order_payload(data)
    if request.form.get("consent") != "on":
        errors["consent"] = "Отметьте согласие, чтобы заказать."
    if errors:
        message = next(iter(errors.values()))
        return _quote_page(clean["destination"], message, 400)
    try:
        order = services.create_order(get_db(), **clean)
    except CariderError as error:  # БП-02, клиент не найден или заблокирован
        return _quote_page(clean["destination"], error.message, error.http_status)
    return redirect(url_for("dispatch.search_screen", order_id=order.id))


@bp.post("/orders/<int:order_id>/cancel")
def cancel_screen(order_id):
    """Кнопка «Отменить заказ» на Э-03 и Э-04."""
    services.cancel_order(get_db(), order_id)
    return redirect(url_for("orders.cancelled_screen", order_id=order_id))


@bp.get("/orders/<int:order_id>/cancelled")
def cancelled_screen(order_id):
    """Э-05 «Заказ отменён»: только для отменённого заказа."""
    order = services.get_order(get_db(), order_id)
    if order.status != OrderStatus.CANCELLED:
        raise OrderStateError()
    return render_template("orders/cancelled.html", order=order)


@bp.post("/api/quotes/")
def api_create_quote():
    """Операция 1: POST /api/quotes/ — расчёт стоимости."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    destination = data.get("destination")
    if not isinstance(destination, str):
        destination = ""
    quote = services.calculate_quote(get_db(), destination)
    return jsonify(
        {
            "pickup": quote.pickup,
            "destination": quote.destination,
            "price_tg": quote.price_tg,
            "duration_min": quote.duration_min,
            "free_cancel_seconds": quote.free_cancel_seconds,
        }
    )


@bp.post("/api/orders/")
def api_create_order():
    """Операция 2: POST /api/orders/ — подтвердить заказ."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        body = {"error": {"code": "INVALID_REQUEST", "message": "Тело — не JSON."}}
        return jsonify(body), 400
    clean, errors = forms.validate_order_payload(data)
    if errors:
        body = {
            "error": {
                "code": "INVALID_REQUEST",
                "message": "Неверный формат данных.",
                "fields": errors,
            }
        }
        return jsonify(body), 400
    order = services.create_order(get_db(), **clean)
    return (
        jsonify(
            {
                "order_id": order.id,
                "status": order.status_label,
                "created_at": order.created_at.isoformat(),
            }
        ),
        201,
    )


@bp.post("/api/orders/<int:order_id>/cancel/")
def api_cancel_order(order_id):
    """Операция 5: POST /api/orders/{id}/cancel/ — отменить заказ."""
    order = services.cancel_order(get_db(), order_id)
    return jsonify({"status": order.status_label, "penalty": order.penalty})
