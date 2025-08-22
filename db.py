
# db.py — hybrid connector: Turso (libSQL via SQLAlchemy) in deploy, SQLite locally
import os
import sqlite3
from pathlib import Path

try:
    import streamlit as st  # only for reading secrets if available
except Exception:
    st = None

from schema_sql import SCHEMA_SQL

def _get_secret(name: str, default=None):
    val = os.environ.get(name)
    if val is not None:
        return val
    if st is not None:
        try:
            return st.secrets.get(name, default)  # type: ignore[attr-defined]
        except Exception:
            return default
    return default

TURSO_DATABASE_URL = _get_secret("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = _get_secret("TURSO_AUTH_TOKEN")
IS_TURSO = bool(TURSO_DATABASE_URL and TURSO_AUTH_TOKEN)

DB_PATH = Path(os.environ.get("COINAPP_DB_PATH", "data/coinapp.sqlite"))

if IS_TURSO:
    # Turso / libSQL via SQLAlchemy
    from sqlalchemy import create_engine
    _ENGINE = create_engine(
        f"sqlite+{TURSO_DATABASE_URL}?secure=true",
        connect_args={"auth_token": TURSO_AUTH_TOKEN},
        pool_pre_ping=True,
        future=True,
    )

    class _SAResultWrapper:
        def __init__(self, result):
            self._result = result
        def fetchall(self):
            return list(self._result.mappings().all())
        def fetchone(self):
            row = self._result.mappings().first()
            return row

    class _SAConnWrapper:
        """Minimal sqlite3-like wrapper so existing code keeps working."""
        def __init__(self, engine):
            self._engine = engine
            self._conn = None
            self.row_factory = None  # compatibility

        def __enter__(self):
            self._conn = self._engine.connect()
            self._conn.exec_driver_sql("PRAGMA foreign_keys=ON;")
            return self

        def __exit__(self, exc_type, exc, tb):
            if self._conn is not None:
                self._conn.close()
                self._conn = None

        def execute(self, sql: str, params=()):
            # Keep using qmark-style '?' params
            res = self._conn.exec_driver_sql(sql, params)
            return _SAResultWrapper(res)

    def get_conn():
        return _SAConnWrapper(_ENGINE)

    def init_db():
        # Use raw DBAPI connection so we can run executescript on the whole schema.
        with _ENGINE.begin() as conn:
            raw = conn.connection  # DBAPI connection
            cur = raw.cursor()
            cur.executescript(SCHEMA_SQL)
            cur.close()

else:
    # Local SQLite (unchanged behavior)
    def get_conn():
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_db():
        with get_conn() as cx:
            cx.executescript(SCHEMA_SQL)
