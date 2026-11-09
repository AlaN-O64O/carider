-- Модуль orders: сущность «Заказ» и справочник адресов.

-- Справочник адресов заменяет заглушку из ЛР №6. Позже его заменит
-- сервис геокодирования.
CREATE TABLE places (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    distance_km REAL NOT NULL CHECK (distance_km > 0)
);

CREATE TABLE orders (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id         INTEGER NOT NULL REFERENCES clients (id),
    driver_id         INTEGER REFERENCES drivers (id),
    pickup            TEXT    NOT NULL,
    pickup_lat        REAL    NOT NULL,
    pickup_lon        REAL    NOT NULL,
    destination       TEXT    NOT NULL CHECK (length(destination) <= 250),
    price_tg          INTEGER NOT NULL CHECK (price_tg > 0),
    status            TEXT    NOT NULL DEFAULT 'created'
                      CHECK (status IN
                          ('created', 'assigned', 'in_progress',
                           'completed', 'cancelled')),
    created_at        TEXT    NOT NULL,
    search_started_at TEXT,
    cancelled_at      TEXT,
    penalty           INTEGER NOT NULL DEFAULT 0 CHECK (penalty IN (0, 1))
);

-- Т-5: один таксист не может выполнять два заказа одновременно.
-- Если два запроса одновременно возьмут одного таксиста, второй упадёт
-- с IntegrityError на уровне СУБД.
CREATE UNIQUE INDEX one_active_order_per_driver
    ON orders (driver_id)
    WHERE driver_id IS NOT NULL AND status IN ('assigned', 'in_progress');
