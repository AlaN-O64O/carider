-- Модуль accounts: сущности «Клиент» и «Таксист» (словарь данных ЛР №4).

CREATE TABLE clients (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    phone         TEXT    NOT NULL UNIQUE,
    consent_pd    INTEGER NOT NULL CHECK (consent_pd = 1),
    registered_at TEXT    NOT NULL,
    is_blocked    INTEGER NOT NULL DEFAULT 0 CHECK (is_blocked IN (0, 1))
);

-- «Госномер и марка авто» разделены на два столбца, чтобы проверять
-- госномер по шаблону РК отдельно от марки.
CREATE TABLE drivers (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT    NOT NULL CHECK (length(full_name) <= 150),
    phone     TEXT    NOT NULL UNIQUE,
    car_model TEXT    NOT NULL,
    plate     TEXT    NOT NULL UNIQUE,
    status    TEXT    NOT NULL DEFAULT 'on_shift'
              CHECK (status IN ('free', 'busy', 'on_shift'))
);
