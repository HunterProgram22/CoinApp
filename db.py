# db.py — SQLite everywhere
"""Database connection and initialization module."""

import os
import sqlite3
from pathlib import Path
from schema_sql import SCHEMA_SQL

try:
    import streamlit as st
except ImportError:
    st = None

# Database configuration
DEFAULT_DB_PATH = "data/coinapp.sqlite"


def get_secret(name: str, default=None):
    """Get configuration value from environment or Streamlit secrets."""
    # Try environment first
    val = os.environ.get(name)
    if val is not None:
        return val
    
    # Try Streamlit secrets if available
    if st is not None:
        try:
            return st.secrets.get(name, default)
        except Exception:
            pass
    
    return default


# Global configuration
DB_PATH = Path(get_secret("COINAPP_DB_PATH", DEFAULT_DB_PATH))


def get_conn():
    """Get a SQLite database connection."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    """Initialize database schema."""
    with get_conn() as conn:
        conn.executescript(SCHEMA_SQL)


def create_backup_data():
    """Create backup data as BytesIO for download."""
    import io
    bio = io.BytesIO()
    try:
        with open(DB_PATH, "rb") as f:
            bio.write(f.read())
        bio.seek(0)
        return bio
    except Exception as e:
        raise Exception(f"Backup creation failed: {e}")


def get_backup_filename():
    """Generate standardized backup filename."""
    from datetime import datetime
    return f"coinapp-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.sqlite"
