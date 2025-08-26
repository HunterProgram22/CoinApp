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
    "NEON_DATABASE_URL": None,
    "COINAPP_DB_PATH": DEFAULT_DB_PATH,
}

# SQL constants
PRAGMA_FOREIGN_KEYS = "PRAGMA foreign_keys=ON;"
LASTROWID_QUERY = "SELECT last_insert_rowid()"


# Replace the existing configuration with:
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
        self.neon_url = get_secret("NEON_DATABASE_URL")
        self.db_path = Path(get_secret("COINAPP_DB_PATH", DEFAULT_DB_PATH))
        self.is_cloud = bool(self.neon_url)  # Use Neon if URL exists, otherwise local SQLite

    @property
    def connection_string(self):
        """Get SQLAlchemy connection string for cloud database."""
        if not self.is_cloud:
            raise ValueError("Connection string only available for cloud configuration")
        return self.neon_url

    def ensure_local_db_path(self):  # This method name was missing
        """Ensure local database directory exists."""
        if not self.is_cloud:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
