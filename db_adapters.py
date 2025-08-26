# db_adapters.pDTreeToggle
"""Database adapter classes for unified interface."""

import sqlite3
from typing import Any, Dict, List, Optional, Union

from db_config import PRAGMA_FOREIGN_KEYS, LASTROWID_QUERY


class RowLike:
    """Duck-typed sqlite3.Row replacement for SQLAlchemy results."""
    
    def __init__(self, mapping: Dict[str, Any]):
        self._map = dict(mapping)
        self._keys = list(self._map.keys())
        self._vals = [self._map[k] for k in self._keys]
    
    def __getitem__(self, key: Union[int, str]) -> Any:
        if isinstance(key, int):
            return self._vals[key]
        return self._map[key]
    
    def __iter__(self):
        return iter(self._keys)
    
    def __len__(self) -> int:
        return len(self._map)
    
    def keys(self) -> List[str]:
        return self._keys
    
    def items(self):
        return self._map.items()
    
    def get(self, key: str, default: Any = None) -> Any:
        return self._map.get(key, default)


class SQLAlchemyResultWrapper:
    """Wrapper to make SQLAlchemy results behave like sqlite3 results."""
    
    def __init__(self, sa_result, conn):
        self._result = sa_result
        self._conn = conn
        self._lastrowid = None
    
    def fetchall(self) -> List[RowLike]:
        """Fetch all rows as RowLike objects."""
        return [RowLike(mapping) for mapping in self._result.mappings().all()]
    
    def fetchone(self) -> Optional[RowLike]:
        """Fetch one row as RowLike object."""
        mapping = self._result.mappings().first()
        return RowLike(mapping) if mapping is not None else None
    
    @property
    def lastrowid(self) -> Optional[int]:
        """Get last inserted row ID."""
        if self._lastrowid is not None:
            return self._lastrowid
        
        try:
            return self._result.lastrowid
        except Exception:
            return None


class SQLAlchemyConnectionWrapper:
    """SQLite-compatible wrapper for SQLAlchemy connections."""
    
    def __init__(self, engine):
        self._engine = engine
        self._conn = None
        self._trans = None
        self.row_factory = None  # Compatibility attribute
    
    def __enter__(self):
        self._conn = self._engine.connect()
        self._trans = self._conn.begin()
        self._enable_foreign_keys()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
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
    
    def _enable_foreign_keys(self):
        """Enable foreign key constraints."""
        self._conn.exec_driver_sql(PRAGMA_FOREIGN_KEYS)
    
    def _is_insert_query(self, sql: str) -> bool:
        """Check if SQL query is an INSERT statement."""
        try:
            return sql.lstrip().upper().startswith("INSERT")
        except Exception:
            return False
    
    def _get_lastrowid(self) -> Optional[int]:
        """Get the last inserted row ID."""
        try:
            return self._conn.exec_driver_sql(LASTROWID_QUERY).scalar()
        except Exception:
            return None
    
    def execute(self, sql: str, params=()) -> SQLAlchemyResultWrapper:
        """Execute SQL query with parameters."""
        # Ensure params is a tuple, not a list
        if isinstance(params, list):
            params = tuple(params)

        result = self._conn.exec_driver_sql(sql, params)
        wrapper = SQLAlchemyResultWrapper(result, self._conn)
        
        # Handle lastrowid for INSERT statements
        if self._is_insert_query(sql):
            try:
                wrapper._lastrowid = result.lastrowid or self._get_lastrowid()
            except Exception:
                wrapper._lastrowid = None
        
        return wrapper


class SQLiteConnectionWrapper:
    """Standard SQLite connection with consistent interface."""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self._conn = None
    
    def __enter__(self):
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(PRAGMA_FOREIGN_KEYS)
        return self._conn
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._conn:
            self._conn.close()
