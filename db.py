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
    from schema_postgresql import SCHEMA_SQL as POSTGRESQL_SCHEMA

    # Get raw psycopg2 connection instead of SQLAlchemy wrapper
    raw_conn = _engine.raw_connection()
    try:
        with raw_conn.cursor() as cursor:
            cursor.execute(POSTGRESQL_SCHEMA)
        raw_conn.commit()
    finally:
        raw_conn.close()


def _init_sqlite_schema():
    """Initialize schema for SQLite database."""
    from schema_sql import SCHEMA_SQL as SQLITE_SCHEMA
    with get_conn() as conn:
        conn.executescript(SQLITE_SCHEMA)


# Legacy compatibility exports (if needed by existing code)
IS_CLOUD = _config.is_cloud  # Updated from IS_TURSO
DB_PATH = _config.db_path