-- Модуль dispatch: последнее известное положение таксиста.

CREATE TABLE driver_positions (
    driver_id  INTEGER PRIMARY KEY REFERENCES drivers (id),
    lat        REAL NOT NULL CHECK (lat BETWEEN -90 AND 90),
    lon        REAL NOT NULL CHECK (lon BETWEEN -180 AND 180),
    updated_at TEXT NOT NULL
);
