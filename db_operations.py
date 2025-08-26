# db_operations.py
"""Simplified database operation helpers for SQLite."""

from typing import List, Dict, Any, Optional
from db import get_conn


def execute_query_single(query: str, params=()) -> Optional[Dict[str, Any]]:
    """Execute query and return single row as dict, or None if no results."""
    with get_conn() as cx:
        result = cx.execute(query, params).fetchone()
        return dict(result) if result else None


def execute_query_all(query: str, params=()) -> List[Dict[str, Any]]:
    """Execute query and return all rows as list of dicts."""
    with get_conn() as cx:
        results = cx.execute(query, params).fetchall()
        return [dict(row) for row in results]


def execute_insert(query: str, params=()) -> Optional[int]:
    """Execute INSERT and return lastrowid."""
    with get_conn() as cx:
        cursor = cx.execute(query, params)
        return cursor.lastrowid


def execute_update(query: str, params=()) -> int:
    """Execute UPDATE and return number of affected rows."""
    with get_conn() as cx:
        cursor = cx.execute(query, params)
        return cursor.rowcount


def execute_delete(query: str, params=()) -> int:
    """Execute DELETE and return number of affected rows."""
    with get_conn() as cx:
        cursor = cx.execute(query, params)
        return cursor.rowcount


def upsert_record(table: str, search_fields: Dict[str, Any], update_fields: Dict[str, Any],
                  insert_fields: Optional[Dict[str, Any]] = None) -> int:
    """Generic upsert operation for SQLite."""
    if insert_fields is None:
        insert_fields = {**search_fields, **update_fields}
    
    # Build search query
    search_conditions = " AND ".join([f"{k} = ?" for k in search_fields.keys()])
    search_query = f"SELECT id FROM {table} WHERE {search_conditions}"
    search_params = list(search_fields.values())
    
    # Check if record exists
    existing = execute_query_single(search_query, search_params)
    
    if existing:
        # Update existing record
        if update_fields:
            update_assignments = ", ".join([f"{k} = COALESCE(?, {k})" for k in update_fields.keys()])
            update_query = f"UPDATE {table} SET {update_assignments} WHERE id = ?"
            update_params = list(update_fields.values()) + [existing['id']]
            execute_update(update_query, update_params)
        return existing['id']
    else:
        # Insert new record
        field_names = ", ".join(insert_fields.keys())
        placeholders = ", ".join(["?"] * len(insert_fields))
        insert_query = f"INSERT INTO {table}({field_names}) VALUES ({placeholders})"
        insert_params = list(insert_fields.values())
        return execute_insert(insert_query, insert_params)


# Helper functions
def find_or_create_party(name: str, kind: str = None, contact: str = None) -> Optional[int]:
    """Find existing party or create new one."""
    if not name:
        return None
    
    name = name.strip()
    existing = execute_query_single("SELECT id FROM party WHERE name = ?", (name,))
    
    if existing:
        return existing['id']
    
    return execute_insert(
        "INSERT INTO party(name, kind, contact) VALUES (?,?,?)",
        (name, kind, contact)
    )


def find_or_create_storage(name: str, category: str = None, description: str = None) -> Optional[int]:
    """Find existing storage location or create new one."""
    if not name:
        return None
    
    name = name.strip()
    existing = execute_query_single("SELECT id FROM storage_location WHERE name = ?", (name,))
    
    if existing:
        return existing['id']
    
    return execute_insert(
        "INSERT INTO storage_location(name, category, description) VALUES (?,?,?)",
        (name, category, description)
    )


def normalize_text_field(value: Any, nan_values: set = None) -> str:
    """Normalize text field, handling NaN-like values."""
    if nan_values is None:
        nan_values = {"nan", "none", "-", "—", ""}
    
    if value is None:
        return ""
    
    text = str(value).strip()
    return "" if text.lower() in nan_values else text


def normalize_for_upsert(value: Any, nan_values: set = None) -> Optional[str]:
    """Normalize value for upsert operations (empty becomes None)."""
    if nan_values is None:
        nan_values = {"nan", "none", "-", "—", ""}
    
    if value is None:
        return None
    
    text = str(value).strip()
    return None if text == '' or text.lower() in nan_values else text
