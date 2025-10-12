# db_turso.py - Turso Database Connection (HTTP Mode)
"""Database connection module with Turso support using HTTP."""

import os
from pathlib import Path
from typing import Optional
import libsql_client

try:
    import streamlit as st

    HAS_STREAMLIT = True
except ImportError:
    st = None
    HAS_STREAMLIT = False

# Database configuration
DEFAULT_DB_PATH = "data/coinapp.sqlite"
DB_TYPE = "turso"


def get_secret(name: str, default=None):
    """Get configuration value from environment or Streamlit secrets."""
    # Try environment first
    val = os.environ.get(name)
    if val is not None:
        return val

    # Try Streamlit secrets if available
    if HAS_STREAMLIT and st is not None:
        try:
            if name in st.secrets:
                return st.secrets[name]
            if hasattr(st.secrets, name):
                return getattr(st.secrets, name)
        except (KeyError, AttributeError, FileNotFoundError):
            pass
        except Exception as e:
            print(f"Warning: Error reading secret '{name}': {e}")

    return default


def get_turso_config():
    """Get Turso database configuration from secrets."""
    url = get_secret("TURSO_DATABASE_URL")
    token = get_secret("TURSO_AUTH_TOKEN")

    # Convert WebSocket URL to HTTP if needed
    if url:
        # Replace wss:// or ws:// with https:// or http://
        if url.startswith("libsql://"):
            # libsql:// should work as-is, but we'll convert to https:// for HTTP mode
            url = url.replace("libsql://", "https://")
        elif url.startswith("wss://"):
            url = url.replace("wss://", "https://")
        elif url.startswith("ws://"):
            url = url.replace("ws://", "http://")

        print(f"✓ Turso URL (HTTP mode): {url[:40]}...")
    else:
        print("✗ TURSO_DATABASE_URL not found")

    if token:
        print(f"✓ Found TURSO_AUTH_TOKEN: {token[:20]}...")
    else:
        print("✗ TURSO_AUTH_TOKEN not found")

    return {'url': url, 'auth_token': token}


class TursoConnection:
    """Wrapper to make Turso client work like sqlite3.Connection."""

    def __init__(self, client):
        self.client = client
        self._row_factory = None

    @property
    def row_factory(self):
        return self._row_factory

    @row_factory.setter
    def row_factory(self, factory):
        self._row_factory = factory

    def execute(self, sql: str, params=None):
        """Execute a SQL statement."""
        if params is None:
            params = []

        # Convert tuple to list
        if isinstance(params, tuple):
            params = list(params)

        try:
            result = self.client.execute(sql, params)
            return TursoCursor(result, self._row_factory)
        except Exception as e:
            raise Exception(f"Turso execute error: {e}")

    def executescript(self, sql_script: str):
        """Execute multiple SQL statements."""
        statements = [s.strip() for s in sql_script.split(';') if s.strip()]
        for statement in statements:
            if statement:
                self.client.execute(statement)
        return self

    def executemany(self, sql: str, params_list):
        """Execute SQL multiple times."""
        results = []
        for params in params_list:
            if isinstance(params, tuple):
                params = list(params)
            result = self.client.execute(sql, params)
            results.append(result)
        return TursoCursor(results[-1] if results else None, self._row_factory)

    def commit(self):
        """Commit (no-op for Turso)."""
        pass

    def close(self):
        """Close connection."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.commit()
        return False


class TursoCursor:
    """Wrapper to make Turso results work like sqlite3.Cursor."""

    def __init__(self, result, row_factory):
        self.result = result
        self.row_factory = row_factory
        self._rows = None
        self._current_index = 0

        if result:
            # Convert Turso result to list
            self._rows = []
            if hasattr(result, 'rows') and result.rows:
                columns = result.columns if hasattr(result, 'columns') else []
                for row_data in result.rows:
                    if self.row_factory:
                        self._rows.append(TursoRow(columns, row_data))
                    else:
                        self._rows.append(tuple(row_data))

    @property
    def rowcount(self):
        """Return number of affected rows."""
        if self.result and hasattr(self.result, 'rows_affected'):
            return self.result.rows_affected
        return -1

    @property
    def lastrowid(self):
        """Return last inserted row ID."""
        if self.result and hasattr(self.result, 'last_insert_rowid'):
            return self.result.last_insert_rowid
        return None

    def fetchone(self):
        """Fetch one row."""
        if self._rows and self._current_index < len(self._rows):
            row = self._rows[self._current_index]
            self._current_index += 1
            return row
        return None

    def fetchall(self):
        """Fetch all rows."""
        if self._rows:
            remaining = self._rows[self._current_index:]
            self._current_index = len(self._rows)
            return remaining
        return []

    def fetchmany(self, size=1):
        """Fetch multiple rows."""
        if self._rows:
            end_index = min(self._current_index + size, len(self._rows))
            result = self._rows[self._current_index:end_index]
            self._current_index = end_index
            return result
        return []


class TursoRow:
    """Row object mimicking sqlite3.Row."""

    def __init__(self, columns, values):
        self.columns = columns
        self.values = values
        self._dict = dict(zip(columns, values)) if columns else {}

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.values[key]
        return self._dict[key]

    def __contains__(self, key):
        return key in self._dict

    def keys(self):
        return self._dict.keys()

    def __iter__(self):
        return iter(self._dict.items())

    def __len__(self):
        return len(self.values)


def get_conn():
    """Get a database connection (Turso or SQLite)."""
    db_type = get_secret("DB_TYPE", DB_TYPE)

    print(f"DB_TYPE: {db_type}")

    if db_type == "turso":
        config = get_turso_config()

        if not config['url'] or not config['auth_token']:
            error_msg = "Turso credentials not found. Check secrets.toml:\n"
            error_msg += "  DB_TYPE = \"turso\"\n"
            error_msg += "  TURSO_DATABASE_URL = \"libsql://...\"\n"
            error_msg += "  TURSO_AUTH_TOKEN = \"your-token\"\n"
            raise ValueError(error_msg)

        try:
            print(f"Connecting to Turso via HTTP: {config['url'][:50]}...")

            # Create client using HTTP mode (sync)
            # The key is to use the converted HTTPS URL
            client = libsql_client.create_client_sync(
                url=config['url'],
                auth_token=config['auth_token']
            )

            conn = TursoConnection(client)
            conn.row_factory = True

            print("✓ Turso connection created")

            # Test the connection
            try:
                test_result = conn.execute("SELECT 1 as test")
                test_row = test_result.fetchone()
                print(f"✓ Test query successful: {test_row}")
            except Exception as e:
                print(f"⚠ Test query failed: {e}")
                raise

            return conn

        except Exception as e:
            print(f"✗ Connection failed: {type(e).__name__}: {e}")
            raise Exception(f"Failed to connect to Turso: {e}")

    else:
        # Use local SQLite
        print("Using SQLite")
        import sqlite3
        db_path = Path(get_secret("COINAPP_DB_PATH", DEFAULT_DB_PATH))
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn


def init_db():
    """Initialize database schema."""
    from .schema_sql import SCHEMA_SQL

    db_type = get_secret("DB_TYPE", DB_TYPE)

    if db_type == "turso":
        print("For Turso, run schema scripts manually:")
        print("1. turso db shell cointracker-db < turso_schema.sql")
        print("2. turso db shell cointracker-db < turso_views.sql")
        return

    with get_conn() as conn:
        conn.executescript(SCHEMA_SQL)


def create_backup_data():
    """Create backup data."""
    db_type = get_secret("DB_TYPE", DB_TYPE)

    if db_type == "turso":
        raise NotImplementedError(
            "Use Turso CLI: turso db shell <db-name> .dump"
        )

    import io
    db_path = Path(get_secret("COINAPP_DB_PATH", DEFAULT_DB_PATH))
    bio = io.BytesIO()
    with open(db_path, "rb") as f:
        bio.write(f.read())
    bio.seek(0)
    return bio


def get_backup_filename():
    """Generate backup filename."""
    from datetime import datetime
    return f"coinapp-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.sqlite"
