
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

    class RowLike:
        """Duck-typed like sqlite3.Row: supports row['col'] and row[0], and dict(row)."""
        def __init__(self, mapping):
            self._map = dict(mapping)
            self._keys = list(self._map.keys())
            self._vals = [self._map[k] for k in self._keys]
        def __getitem__(self, key):
            if isinstance(key, int):
                return self._vals[key]
            return self._map[key]
        def keys(self):
            return self._keys
        def items(self):
            return self._map.items()
        def get(self, k, default=None):
            return self._map.get(k, default)
        def __iter__(self):
            return iter(self._keys)
        def __len__(self):
            return len(self._map)

    class _SAResultWrapper:
        def __init__(self, sa_result, conn):
            self._result = sa_result
            self._conn = conn
            self._lastrowid = None  # set by _SAConnWrapper.execute for INSERTs
        def fetchall(self):
            return [RowLike(m) for m in self._result.mappings().all()]
        def fetchone(self):
            m = self._result.mappings().first()
            return RowLike(m) if m is not None else None
        @property
        def lastrowid(self):
            if self._lastrowid is not None:
                return self._lastrowid
            try:
                return self._result.lastrowid  # may exist on SQLite backends
            except Exception:
                return None

    class _SAConnWrapper:
        """Minimal sqlite3-like wrapper so existing code keeps working.
        IMPORTANT: now manages an explicit transaction and commits on success.
        """
        def __init__(self, engine):
            self._engine = engine
            self._conn = None
            self._trans = None
            self.row_factory = None  # compatibility

        def __enter__(self):
            self._conn = self._engine.connect()
            # Explicit transaction: commit on successful __exit__, rollback on error
            self._trans = self._conn.begin()
            # Enforce FK behavior
            self._conn.exec_driver_sql("PRAGMA foreign_keys=ON;")
            return self

        def __exit__(self, exc_type, exc, tb):
            try:
                if self._trans is not None:
                    if exc_type is None:
                        self._trans.commit()
                    else:
                        self._trans.rollback()
            finally:
                if self._conn is not None:
                    self._conn.close()
                    self._conn = None
                self._trans = None

        def execute(self, sql: str, params=()):
            res = self._conn.exec_driver_sql(sql, params)
            wrap = _SAResultWrapper(res, self._conn)
            # Best-effort lastrowid for INSERTs
            try:
                is_insert = sql.lstrip().upper().startswith("INSERT")
            except Exception:
                is_insert = False
            if is_insert:
                lid = None
                try:
                    lid = res.lastrowid
                except Exception:
                    lid = None
                if lid is None:
                    try:
                        lid = self._conn.exec_driver_sql("SELECT last_insert_rowid()").scalar()
                    except Exception:
                        lid = None
                wrap._lastrowid = lid
            return wrap

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
