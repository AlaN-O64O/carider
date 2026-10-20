"""Слой представления модуля «Заказы»: экраны Э-01, Э-02 и API расчёта."""

from flask import Blueprint, jsonify, render_template, request

from . import services
from .errors import (
    DestinationNotFoundError,
    InvalidDestinationError,
    OrderError,
    RoutingServiceError,
)

bp = Blueprint("orders", __name__, template_folder="templates")

_STATUS_BY_ERROR = {
    InvalidDestinationError: 400,
    DestinationNotFoundError: 404,
    RoutingServiceError: 503,
}


def _status_for(error: OrderError) -> int:
    return _STATUS_BY_ERROR.get(type(error), 400)


@bp.app_template_filter("tg")
def format_tg(value: int) -> str:
    """Сумма с пробелом между разрядами: 1850 -> «1 850»."""
    return f"{value:,}".replace(",", " ")


@bp.get("/")
def destination_screen():
    """Э-01 «Куда едем?»."""
    return render_template(
        "orders/destination.html",
        hints=services.list_destination_hints(),
        destination="",
        error=None,
    )


@bp.get("/quote")
def quote_screen():
    """Э-02 «Стоимость и условия»."""
    destination = request.args.get("destination", "")
    try:
        quote = services.calculate_quote(destination)
    except RoutingServiceError as error:
        page = render_template("orders/quote.html", quote=None, error=error.message)
        return page, 503
    except OrderError as error:
        page = render_template(
            "orders/destination.html",
            hints=services.list_destination_hints(),
            destination=destination,
            error=error.message,
        )
        return page, _status_for(error)
    return render_template("orders/quote.html", quote=quote, error=None)


@bp.post("/api/quotes/")
def api_create_quote():
    """POST /api/quotes/ — расчёт стоимости поездки."""
    data = request.get_json(silent=True) or {}
    try:
        quote = services.calculate_quote(str(data.get("destination", "")))
    except OrderError as error:
        body = {"error": {"code": error.code, "message": error.message}}
        return jsonify(body), _status_for(error)
    return jsonify(
        {
            "pickup": quote.pickup,
            "destination": quote.destination,
            "price_tg": quote.price_tg,
            "duration_min": quote.duration_min,
            "free_cancel_seconds": quote.free_cancel_seconds,
        }
    )
