# type_sets_helpers.py
"""Helper functions for type set operations."""
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from db_operations import execute_query_all, execute_query_single, execute_insert, execute_update, \
    execute_delete
from db import get_conn


# ---------------------------------
# Schema Check Functions
# ---------------------------------
def check_type_set_schema() -> Dict[str, bool]:
    """Check if type set tables and views exist."""
    with get_conn() as cx:
        return {
            'type_set': bool(cx.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='type_set'"
            ).fetchone()),
            'type_set_member': bool(cx.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='type_set_member'"
            ).fetchone()),
            'type_set_assignment': bool(cx.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='type_set_assignment'"
            ).fetchone()),
            'specimen': bool(cx.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='specimen'"
            ).fetchone()),
            'v_type_set_progress': bool(cx.execute(
                "SELECT 1 FROM sqlite_master WHERE type='view' AND name='v_type_set_progress'"
            ).fetchone()),
            'v_type_set_progress_assign': bool(cx.execute(
                "SELECT 1 FROM sqlite_master WHERE type='view' AND name='v_type_set_progress_assign'"
            ).fetchone())
        }


# ---------------------------------
# Type Set CRUD Operations
# ---------------------------------
def get_all_type_sets() -> List[Dict[str, Any]]:
    """Get all type sets."""
    schema = check_type_set_schema()
    if not schema['type_set']:
        return []

    query = "SELECT id, name, COALESCE(description,'') AS description FROM type_set ORDER BY name"
    return execute_query_all(query)


def create_type_set(name: str, description: Optional[str] = None) -> int:
    """Create a new type set."""
    if not name:
        raise ValueError("Set name is required")

    schema = check_type_set_schema()
    if not schema['type_set']:
        raise RuntimeError("Missing table 'type_set'. Please add type set tables to your schema.")

    query = "INSERT INTO type_set(name, description) VALUES (?, ?)"
    return execute_insert(query, (name, description))


def update_type_set(set_id: int, name: str, description: Optional[str] = None) -> int:
    """Update an existing type set."""
    if not name:
        raise ValueError("Set name is required")

    query = "UPDATE type_set SET name=?, description=? WHERE id=?"
    return execute_update(query, (name, description, set_id))


def delete_type_set(set_id: int) -> int:
    """Delete a type set and all its members."""
    # Delete members first (due to foreign key)
    execute_delete("DELETE FROM type_set_member WHERE set_id=?", (set_id,))
    execute_delete("DELETE FROM type_set_assignment WHERE set_id=?", (set_id,))
    return execute_delete("DELETE FROM type_set WHERE id=?", (set_id,))


# ---------------------------------
# Type Set Member Operations
# ---------------------------------
def get_type_set_members(set_id: int) -> List[Dict[str, Any]]:
    """Get all members of a type set."""
    schema = check_type_set_schema()
    if not schema['type_set_member']:
        return []

    query = """
        SELECT m.coin_type_id, cm.series, ct.year, ct.mint_mark, 
               COALESCE(ct.variety,'') AS variety, ct.is_proof
        FROM type_set_member m
        JOIN coin_type ct ON ct.id = m.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        WHERE m.set_id=?
        ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety
    """
    return execute_query_all(query, (set_id,))


def add_type_set_members(set_id: int, coin_type_ids: List[int]) -> int:
    """Add coin types to a type set."""
    if not coin_type_ids:
        return 0

    schema = check_type_set_schema()
    if not schema['type_set_member']:
        raise RuntimeError("Missing table 'type_set_member'.")

    count = 0
    for coin_type_id in coin_type_ids:
        try:
            execute_insert(
                "INSERT OR IGNORE INTO type_set_member(set_id, coin_type_id) VALUES (?, ?)",
                (set_id, coin_type_id)
            )
            count += 1
        except Exception:
            pass  # Ignore duplicates
    return count


def remove_type_set_members(set_id: int, coin_type_ids: List[int]) -> int:
    """Remove coin types from a type set."""
    if not coin_type_ids:
        return 0

    count = 0
    for coin_type_id in coin_type_ids:
        rows = execute_delete(
            "DELETE FROM type_set_member WHERE set_id=? AND coin_type_id=?",
            (set_id, coin_type_id)
        )
        count += rows
    return count


# ---------------------------------
# Type Set Progress
# ---------------------------------
def get_type_set_progress(set_id: int) -> Tuple[Optional[str], pd.DataFrame]:
    """Get progress data for a type set."""
    schema = check_type_set_schema()

    # Choose the best available view
    if schema['v_type_set_progress_assign']:
        view_name = 'v_type_set_progress_assign'
    elif schema['v_type_set_progress']:
        view_name = 'v_type_set_progress'
    else:
        return None, pd.DataFrame()

    query = f"""
        SELECT * FROM {view_name}
        WHERE set_id=?
        ORDER BY series, year, mint_mark, variety
    """

    rows = execute_query_all(query, (set_id,))
    return view_name, pd.DataFrame(rows)


def analyze_missing_coins(df: pd.DataFrame) -> pd.DataFrame:
    """Analyze which coins are missing from a type set."""
    if df.empty:
        return pd.DataFrame()

    # Look for columns that indicate ownership
    ownership_columns = ["on_hand", "have", "have_count", "have_qty",
                         "assigned_count", "owned", "has_any"]

    found_columns = [col for col in ownership_columns if col in df.columns]

    if not found_columns:
        return pd.DataFrame()

    # Use the first found column
    col = found_columns[0]

    # Convert to numeric and find rows with 0 or missing
    numeric_col = pd.to_numeric(df[col], errors="coerce")
    missing_mask = (numeric_col <= 0) | numeric_col.isna()

    return df[missing_mask].copy()


# ---------------------------------
# Specimen Assignment Operations
# ---------------------------------
def get_type_set_assignments(set_id: int) -> List[Dict[str, Any]]:
    """Get specimen assignments for a type set."""
    schema = check_type_set_schema()
    if not all([schema['type_set_assignment'], schema['specimen']]):
        return []

    query = """
        SELECT a.coin_type_id, s.code AS specimen_code,
               (s.sold_line_id IS NULL) AS on_hand
        FROM type_set_assignment a
        JOIN specimen s ON s.id = a.specimen_id
        WHERE a.set_id = ?
        ORDER BY a.coin_type_id, s.code
    """
    return execute_query_all(query, (set_id,))


def get_unassigned_specimens(coin_type_id: int, set_id: int) -> List[Dict[str, Any]]:
    """Get specimens available for assignment to a type set."""
    schema = check_type_set_schema()
    if not all([schema['specimen'], schema['type_set_assignment']]):
        return []

    query = """
        SELECT s.id, s.code
        FROM specimen s
        JOIN lot l ON l.id = s.lot_id
        WHERE l.coin_type_id = ?
          AND s.sold_line_id IS NULL
          AND NOT EXISTS (
            SELECT 1 FROM type_set_assignment a
            WHERE a.set_id = ? AND a.specimen_id = s.id
          )
        ORDER BY s.code
    """
    return execute_query_all(query, (coin_type_id, set_id))


def assign_specimen_to_set(set_id: int, coin_type_id: int, specimen_id: int) -> int:
    """Assign a specimen to a type set."""
    query = "INSERT INTO type_set_assignment(set_id, coin_type_id, specimen_id) VALUES (?,?,?)"
    return execute_insert(query, (set_id, coin_type_id, specimen_id))


def unassign_specimen_from_set(set_id: int, specimen_code: str) -> int:
    """Remove a specimen assignment from a type set."""
    # Get specimen ID from code
    specimen = execute_query_single("SELECT id FROM specimen WHERE code = ?", (specimen_code,))
    if not specimen:
        return 0

    return execute_delete(
        "DELETE FROM type_set_assignment WHERE set_id = ? AND specimen_id = ?",
        (set_id, specimen['id'])
    )


# ---------------------------------
# Catalog Search Functions
# ---------------------------------
def search_coin_types(
        series: Optional[List[str]] = None,
        year_range: Optional[Tuple[int, int]] = None,
        proof_filter: str = "Any"
) -> List[Dict[str, Any]]:
    """Search for coin types with filters."""
    conditions = []
    params = []

    if series:
        placeholders = ",".join("?" for _ in series)
        conditions.append(f"cm.series IN ({placeholders})")
        params.extend(series)

    if year_range:
        start, end = year_range
        conditions.append("ct.year BETWEEN ? AND ?")
        params.extend([start, end])

    if proof_filter == "Proofs only":
        conditions.append("ct.is_proof = 1")
    elif proof_filter == "Non-proof only":
        conditions.append("(ct.is_proof IS NULL OR ct.is_proof = 0)")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT ct.id, cm.series, ct.year, ct.mint_mark, 
               COALESCE(ct.variety,'') AS variety, ct.is_proof
        FROM coin_type ct
        JOIN coin_master cm ON cm.id = ct.master_id
        {where_clause}
        ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety
    """

    return execute_query_all(query, tuple(params))


def get_all_series() -> List[str]:
    """Get all unique series from coin masters."""
    query = "SELECT DISTINCT series FROM coin_master ORDER BY series"
    results = execute_query_all(query)
    return [r['series'] for r in results]


# ---------------------------------
# Formatting Functions
# ---------------------------------
def format_coin_type_label(coin_type: Dict[str, Any], include_id: bool = False) -> str:
    """Format a coin type for display."""
    label = f"{coin_type['series']} {coin_type['year']}"
    if coin_type.get('mint_mark'):
        label += f" {coin_type['mint_mark']}"
    if coin_type.get('variety'):
        label += f" • {coin_type['variety']}"
    if coin_type.get('is_proof'):
        label += " (Proof)"
    if include_id:
        label += f" (#{coin_type.get('coin_type_id', coin_type.get('id'))})"
    return label
