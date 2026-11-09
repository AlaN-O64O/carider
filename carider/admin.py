"""Админ-панель: просмотр таблиц базы данных (только чтение).

Доступ по логину admin и паролю из переменной CARIDER_ADMIN_PASSWORD
(для разработки по умолчанию — admin).
"""

import secrets

from flask import Blueprint, Response, abort, current_app, render_template, request

from carider.db import get_db

bp = Blueprint("admin", __name__, url_prefix="/admin")

# Таблица -> (название раздела, столбцы). Здесь «регистрируются» модели.
REGISTRY = {
    "clients": (
        "Клиенты",
        ["id", "phone", "consent_pd", "registered_at", "is_blocked"],
    ),
    "drivers": (
        "Таксисты",
        ["id", "full_name", "phone", "car_model", "plate", "status"],
    ),
    "orders": (
        "Заказы",
        [
            "id",
            "client_id",
            "driver_id",
            "destination",
            "price_tg",
            "status",
            "created_at",
            "penalty",
        ],
    ),
    "places": ("Адреса", ["id", "name", "distance_km"]),
    "driver_positions": (
        "Положения таксистов",
        ["driver_id", "lat", "lon", "updated_at"],
    ),
}


@bp.before_request
def require_password():
    """HTTP Basic: без верного пароля — 401."""
    auth = request.authorization
    password = current_app.config["ADMIN_PASSWORD"]
    if (
        auth is None
        or auth.username != "admin"
        or not secrets.compare_digest(auth.password or "", password)
    ):
        return Response(
            "Нужен вход.",
            401,
            {"WWW-Authenticate": 'Basic realm="CaRider admin"'},
        )
    return None


@bp.get("/")
def index():
    sections = [(slug, title) for slug, (title, _cols) in REGISTRY.items()]
    return render_template("admin_index.html", sections=sections)


@bp.get("/<table>/")
def table_view(table):
    if table not in REGISTRY:
        abort(404)
    title, columns = REGISTRY[table]
    rows = get_db().execute(
        f"SELECT {', '.join(columns)} FROM {table} ORDER BY 1 DESC LIMIT 200"
    )
    return render_template(
        "admin_table.html", title=title, columns=columns, rows=rows.fetchall()
    )
