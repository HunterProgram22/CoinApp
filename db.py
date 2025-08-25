# db.py — hybrid connector: Turso (libSQL via SQLAlchemy) in deploy, SQLite locally
"""Database connection and initialization module."""

from db_config import DatabaseConfig
from db_adapters import SQLAlchemyConnectionWrapper, SQLiteConnectionWrapper
from schema_sql import SCHEMA_SQL

# Global configuration
_config = DatabaseConfig()

# Global engine for Turso connections
_engine = None

if _config.is_turso:
    from sqlalchemy import create_engine
    
    _engine = create_engine(
        _config.connection_string,
        connect_args=_config.connect_args,
        pool_pre_ping=True,
        future=True,
    )


def get_conn():
    """Get a database connection using the appropriate adapter."""
    if _config.is_turso:
        return SQLAlchemyConnectionWrapper(_engine)
    else:
        _config.ensure_local_db_path()
        return SQLiteConnectionWrapper(_config.db_path)


def init_db():
    """Initialize database schema."""
    if _config.is_turso:
        _init_turso_schema()
    else:
        _init_sqlite_schema()


def _init_turso_schema():
    """Initialize schema for Turso database."""
    with _engine.begin() as conn:
        raw_conn = conn.connection
        cursor = raw_conn.cursor()
        try:
            cursor.executescript(SCHEMA_SQL)
        finally:
            cursor.close()


def _init_sqlite_schema():
    """Initialize schema for SQLite database."""
    with get_conn() as conn:
        conn.executescript(SCHEMA_SQL)


# Legacy compatibility exports (if needed by existing code)
IS_TURSO = _config.is_turso
DB_PATH = _config.db_path
