# db.py — hybrid connector: Neon PostgreSQL in cloud, SQLite locally
"""Database connection and initialization module."""

from db_config import DatabaseConfig
from db_adapters import SQLAlchemyConnectionWrapper, SQLiteConnectionWrapper
from schema_sql import SCHEMA_SQL

# Global configuration
_config = DatabaseConfig()

# Global engine for cloud connections
_engine = None

if _config.is_cloud:
    from sqlalchemy import create_engine

    _engine = create_engine(
        _config.neon_url,
        pool_pre_ping=True,
        future=True,
    )


def get_conn():
    """Get a database connection using the appropriate adapter."""
    if _config.is_cloud:
        return SQLAlchemyConnectionWrapper(_engine)
    else:
        _config.ensure_local_db_path()
        return SQLiteConnectionWrapper(_config.db_path)


def init_db():
    """Initialize database schema."""
    if _config.is_cloud:
        _init_cloud_schema()
    else:
        _init_sqlite_schema()


def _init_cloud_schema():
    """Initialize schema for cloud PostgreSQL database."""
    with _engine.begin() as conn:
        # PostgreSQL doesn't support executescript, so split and execute individually
        statements = SCHEMA_SQL.strip().split(';')
        for statement in statements:
            if statement.strip():
                conn.exec_driver_sql(statement.strip())


def _init_sqlite_schema():
    """Initialize schema for SQLite database."""
    with get_conn() as conn:
        conn.executescript(SCHEMA_SQL)


# Legacy compatibility exports (if needed by existing code)
IS_CLOUD = _config.is_cloud  # Updated from IS_TURSO
DB_PATH = _config.db_path