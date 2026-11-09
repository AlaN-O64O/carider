"""Общие помощники слоя представления."""

from flask import jsonify, render_template, request


def handle_error(error):
    """Превратить любое исключение UC-01 в ответ: JSON для API, страницу для экрана.

    Нужен только базовый класс: код и текст берутся у наследника (полиморфизм).
    """
    if request.path.startswith("/api/"):
        body = {"error": {"code": error.code, "message": error.message}}
        return jsonify(body), error.http_status
    page = render_template("error.html", message=error.message)
    return page, error.http_status


def duration_text(seconds):
    """90 -> «01:30»."""
    return f"{seconds // 60:02d}:{seconds % 60:02d}"
