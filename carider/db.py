"""Подключение к SQLite, миграции и загрузка демонстрационных данных."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import click
from flask import current_app, g

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def get_connection(path):
    """Открыть соединение с базой; строки читаются как словари."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate(conn):
    """Применить новые миграции по порядку имён; вернуть список применённых.

    Применённые миграции записываются в таблицу schema_migrations, поэтому
    повторный запуск ничего не меняет.
    """
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    done = {row["name"] for row in conn.execute("SELECT name FROM schema_migrations")}
    applied = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.name in done:
            continue
        sql = path.read_text(encoding="utf-8")
        try:
            conn.executescript(f"BEGIN;\n{sql}\nCOMMIT;")
        except sqlite3.Error:
            conn.rollback()  # миграция применяется целиком или не применяется
            raise
        conn.execute(
            "INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)",
            (path.name, datetime.now(UTC).isoformat()),
        )
        conn.commit()
        applied.append(path.name)
    return applied


def load_fixture(conn, name="demo"):
    """Загрузить фикстуру: JSON вида {"таблица": [{"поле": значение}, ...]}.

    Повторная загрузка безопасна: существующие строки пропускаются.
    Возвращает число добавленных строк.
    """
    path = FIXTURES_DIR / f"{name}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    added = 0
    for table, rows in data.items():  # имена таблиц берутся из нашего файла
        for row in rows:
            columns = ", ".join(row)
            marks = ", ".join("?" for _ in row)
            cursor = conn.execute(
                f"INSERT OR IGNORE INTO {table} ({columns}) VALUES ({marks})",
                list(row.values()),
            )
            added += cursor.rowcount
    conn.commit()
    return added


def get_db():
    """Соединение на время одного запроса Flask."""
    if "db" not in g:
        g.db = get_connection(current_app.config["DATABASE"])
    return g.db


def close_db(_error=None):
    """Закрыть соединение в конце запроса."""
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_app(app):
    """Подключить базу и команды `flask migrate`, `flask loaddata` к приложению."""
    app.teardown_appcontext(close_db)

    @app.cli.command("migrate")
    def migrate_command():
        """Создать таблицы: применить миграции."""
        conn = get_connection(app.config["DATABASE"])
        applied = migrate(conn)
        conn.close()
        for name in applied:
            click.echo(f"  применена {name}")
        click.echo(f"Готово: применено миграций — {len(applied)}.")

    @app.cli.command("loaddata")
    @click.argument("name", default="demo")
    def loaddata_command(name):
        """Загрузить демонстрационные данные (по умолчанию demo)."""
        conn = get_connection(app.config["DATABASE"])
        added = load_fixture(conn, name)
        conn.close()
        click.echo(f"Добавлено объектов: {added}.")
