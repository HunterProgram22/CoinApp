# ========== database_executor.py ==========
"""Database executor wrapper - Adapter pattern for existing db_operations"""
from db_operations import execute_query_all, execute_query_single


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
