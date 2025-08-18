# db.py
import sqlite3
from pathlib import Path
from schema_sql import SCHEMA_SQL

DB_PATH = Path("data/coinapp.sqlite")


def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    with get_conn() as cx:
        cx.executescript(SCHEMA_SQL)
