from __future__ import annotations

import os
import sqlite3
from decimal import Decimal
from contextlib import contextmanager
from pathlib import Path
from typing import Any

DB_PATH = Path(os.getenv("MM_WORKHUB_DB", Path(__file__).parent / "data" / "workhub.db"))

SQLITE_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ams_ticket TEXT NOT NULL UNIQUE,
    jira_ticket TEXT,
    description TEXT,
    date_created TEXT,
    priority TEXT,
    pic TEXT,
    status TEXT,
    object_status TEXT,
    action_status TEXT,
    latest_transport TEXT,
    last_update_date TEXT,
    last_update_time TEXT,
    ticket_type TEXT,
    mandays_chargeable REAL,
    last_checked TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ticket_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    update_date TEXT,
    update_text TEXT NOT NULL,
    source_order INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ticket_stages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    stage_name TEXT NOT NULL,
    stage_order INTEGER NOT NULL,
    completed INTEGER NOT NULL DEFAULT 0,
    UNIQUE(ticket_id, stage_name),
    FOREIGN KEY(ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS timesheets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    activity TEXT NOT NULL,
    reference TEXT,
    hours REAL NOT NULL DEFAULT 1,
    category TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_updates_ticket ON ticket_updates(ticket_id);
CREATE INDEX IF NOT EXISTS idx_timesheets_date ON timesheets(work_date);
"""

POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id BIGSERIAL PRIMARY KEY,
    ams_ticket TEXT NOT NULL UNIQUE,
    jira_ticket TEXT,
    description TEXT,
    date_created TEXT,
    priority TEXT,
    pic TEXT,
    status TEXT,
    object_status TEXT,
    action_status TEXT,
    latest_transport TEXT,
    last_update_date TEXT,
    last_update_time TEXT,
    ticket_type TEXT,
    mandays_chargeable DOUBLE PRECISION,
    last_checked TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ticket_updates (
    id BIGSERIAL PRIMARY KEY,
    ticket_id BIGINT NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    update_date TEXT,
    update_text TEXT NOT NULL,
    source_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ticket_stages (
    id BIGSERIAL PRIMARY KEY,
    ticket_id BIGINT NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    stage_name TEXT NOT NULL,
    stage_order INTEGER NOT NULL,
    completed INTEGER NOT NULL DEFAULT 0,
    UNIQUE(ticket_id, stage_name)
);

CREATE TABLE IF NOT EXISTS timesheets (
    id BIGSERIAL PRIMARY KEY,
    work_date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    activity TEXT NOT NULL,
    reference TEXT,
    hours DOUBLE PRECISION NOT NULL DEFAULT 1,
    category TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_updates_ticket ON ticket_updates(ticket_id);
CREATE INDEX IF NOT EXISTS idx_timesheets_date ON timesheets(work_date);
"""


def _streamlit_database_config() -> dict[str, Any] | None:
    try:
        import streamlit as st

        if "database" in st.secrets:
            section = st.secrets["database"]
            return {k: section[k] for k in section}
        if "DATABASE_URL" in st.secrets:
            return {"url": st.secrets["DATABASE_URL"]}
    except Exception:
        return None
    return None


def _database_config() -> dict[str, Any] | None:
    url = os.getenv("DATABASE_URL") or os.getenv("MM_WORKHUB_DATABASE_URL")
    if url:
        return {"url": url}
    return _streamlit_database_config()


def backend_name() -> str:
    return "postgres" if _database_config() else "sqlite"


def _translate(query: str) -> str:
    # The app uses SQLite-style '?' placeholders. psycopg2 uses '%s'.
    return query.replace("?", "%s")


class CompatConnection:
    def __init__(self, raw, backend: str):
        self.raw = raw
        self.backend = backend

    def execute(self, query: str, params: tuple = ()):
        if self.backend == "sqlite":
            return self.raw.execute(query, params)
        cur = self.raw.cursor()
        cur.execute(_translate(query), params)
        return cur

    def executescript(self, script: str) -> None:
        if self.backend == "sqlite":
            self.raw.executescript(script)
            return
        cur = self.raw.cursor()
        try:
            for statement in script.split(";"):
                statement = statement.strip()
                if statement:
                    cur.execute(statement)
        finally:
            cur.close()


@contextmanager
def connect():
    config = _database_config()
    if config:
        import psycopg2

        if config.get("url"):
            raw = psycopg2.connect(config["url"], sslmode=config.get("sslmode", "require"))
        else:
            raw = psycopg2.connect(
                host=config.get("host"),
                port=int(config.get("port", 5432)),
                dbname=config.get("dbname", "postgres"),
                user=config.get("user"),
                password=config.get("password"),
                sslmode=config.get("sslmode", "require"),
                connect_timeout=int(config.get("connect_timeout", 10)),
            )
        conn = CompatConnection(raw, "postgres")
    else:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        raw = sqlite3.connect(DB_PATH)
        raw.row_factory = sqlite3.Row
        raw.execute("PRAGMA foreign_keys = ON")
        conn = CompatConnection(raw, "sqlite")

    try:
        yield conn
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()


def init_db() -> None:
    schema = POSTGRES_SCHEMA if backend_name() == "postgres" else SQLITE_SCHEMA
    with connect() as conn:
        conn.executescript(schema)


def _normalize_value(value: Any) -> Any:
    # PostgreSQL returns NUMERIC/AVG results as Decimal. Pandas treats a
    # Series of Decimals as object dtype, so numeric operations such as
    # Series.round() fail. Convert database Decimal values to regular floats
    # at the boundary so SQLite and PostgreSQL behave consistently.
    if isinstance(value, Decimal):
        return float(value)
    return value


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _normalize_value(value) for key, value in row.items()}


def fetch_all(query: str, params: tuple = ()):
    with connect() as conn:
        if conn.backend == "sqlite":
            return [dict(r) for r in conn.execute(query, params).fetchall()]

        from psycopg2.extras import RealDictCursor

        cur = conn.raw.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(_translate(query), params)
            return [_normalize_row(dict(r)) for r in cur.fetchall()]
        finally:
            cur.close()


def fetch_one(query: str, params: tuple = ()):
    rows = fetch_all(query, params)
    return rows[0] if rows else None


def execute(query: str, params: tuple = ()) -> int | None:
    with connect() as conn:
        cur = conn.execute(query, params)
        try:
            if conn.backend == "sqlite":
                return cur.lastrowid
            return None
        finally:
            if conn.backend == "postgres":
                cur.close()


def reset_db() -> None:
    with connect() as conn:
        conn.executescript("""
        DELETE FROM ticket_updates;
        DELETE FROM ticket_stages;
        DELETE FROM timesheets;
        DELETE FROM tickets;
        """)
