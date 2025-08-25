# db_config.py
"""Database configuration and environment management."""

import os
from pathlib import Path

try:
    import streamlit as st
except ImportError:
    st = None

# Database configuration constants
DEFAULT_DB_PATH = "data/coinapp.sqlite"
DEFAULT_ENV_VARS = {
    "TURSO_DATABASE_URL": None,
    "TURSO_AUTH_TOKEN": None,
    "COINAPP_DB_PATH": DEFAULT_DB_PATH,
}

# SQL constants
PRAGMA_FOREIGN_KEYS = "PRAGMA foreign_keys=ON;"
LASTROWID_QUERY = "SELECT last_insert_rowid()"


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


class DatabaseConfig:
    """Database configuration manager."""
    
    def __init__(self):
        self.turso_url = get_secret("TURSO_DATABASE_URL")
        self.turso_token = get_secret("TURSO_AUTH_TOKEN") 
        self.db_path = Path(get_secret("COINAPP_DB_PATH", DEFAULT_DB_PATH))
        self.is_turso = bool(self.turso_url and self.turso_token)
    
    @property
    def connection_string(self):
        """Get SQLAlchemy connection string for Turso."""
        if not self.is_turso:
            raise ValueError("Connection string only available for Turso configuration")
        return f"sqlite+{self.turso_url}?secure=true"
    
    @property
    def connect_args(self):
        """Get connection arguments for Turso."""
        if not self.is_turso:
            raise ValueError("Connect args only available for Turso configuration")
        return {"auth_token": self.turso_token}
    
    def ensure_local_db_path(self):
        """Ensure local database directory exists."""
        if not self.is_turso:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
