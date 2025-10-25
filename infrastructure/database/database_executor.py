# ========== database_executor.py ==========
"""Database executor wrapper - Adapter pattern for existing db_operations"""
from infrastructure.database.db_operations import execute_query_all, execute_query_single


class DatabaseExecutor:
    """Wrapper for database operations - allows for easy substitution"""

    def execute_query_all(self, query: str, params=None):
        """Execute query returning all results"""
        # Only pass params if they're not None
        if params is None:
            return execute_query_all(query)
        return execute_query_all(query, params)

    def execute_query_single(self, query: str, params=None):
        """Execute query returning single result"""
        # Only pass params if they're not None
        if params is None:
            return execute_query_single(query)
        return execute_query_single(query, params)

    def execute_query(self, query: str, params=None):
        """Execute query without returning results (for DELETE, etc)"""
        from infrastructure.database.db import get_conn
        with get_conn() as conn:
            if params is None:
                conn.execute(query)
            else:
                conn.execute(query, params)

    def execute_many(self, query: str, params_list):
        """Execute query with multiple parameter sets (for bulk inserts)"""
        from infrastructure.database.db import get_conn
        with get_conn() as conn:
            conn.executemany(query, params_list)
