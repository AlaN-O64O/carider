"""CaRider — программный комплекс заказа такси (серверная часть)."""

from flask import Flask


def create_app() -> Flask:
    """Создать приложение Flask и подключить модули."""
    from .orders.views import bp as orders_bp

    app = Flask(__name__)
    app.json.ensure_ascii = False  # Кириллица в JSON без \u-последовательностей.
    app.register_blueprint(orders_bp)
    return app
