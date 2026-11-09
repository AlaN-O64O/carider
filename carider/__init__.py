"""CaRider — программный комплекс заказа такси (серверная часть)."""

import os
from pathlib import Path

from flask import Flask


def create_app(config=None):
    """Создать приложение Flask, подключить базу, модули и обработку ошибок."""
    from . import admin, db, wiring
    from .dispatch.views import bp as dispatch_bp
    from .errors import CariderError
    from .orders.views import bp as orders_bp
    from .web import handle_error

    app = Flask(__name__)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.config.from_mapping(
        DATABASE=str(Path(app.instance_path) / "carider.sqlite3"),
        ADMIN_PASSWORD=os.environ.get("CARIDER_ADMIN_PASSWORD", "admin"),
        DEMO_CLIENT_PHONE="+77010000001",  # пока нет входа по SMS (модуль accounts)
    )
    if config:
        app.config.update(config)
    app.json.ensure_ascii = False  # Кириллица в JSON без \u-последовательностей.

    db.init_app(app)
    wiring.connect_modules()
    app.register_blueprint(orders_bp)
    app.register_blueprint(dispatch_bp)
    app.register_blueprint(admin.bp)
    app.register_error_handler(CariderError, handle_error)
    return app
