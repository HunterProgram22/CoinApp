# type_sets_helpers.py - Updated to use new schema
"""Helper functions for type set operations using new database schema."""
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from db_operations import execute_query_all, execute_query_single, execute_insert, execute_update, \
    execute_delete
from db import get_conn


# ---------------------------------
# Type Set CRUD Operations
# ---------------------------------
def get_all_type_sets() -> List[Dict[str, Any]]:
    """Get all type sets with summary information."""
    query = """
        SELECT 
            s.set_id,
            s.name,
            s.description,
            s.total_coins,
            s.coins_owned,
            s.coins_meeting_requirements,
            s.percent_owned,
            s.percent_complete,
            s.grade_company,
            s.min_grade,
            s.max_grade,
            s.require_slab
        FROM v_type_set_summary s
        ORDER BY s.name
    """
    results = execute_query_all(query)
    
    # Ensure we return id field for compatibility
    for r in results:
        r['id'] = r['set_id']
    
    return results


def create_type_set(name: str, description: Optional[str] = None, 
                   metadata: Optional[Dict[str, Any]] = None) -> int:
    """Create a new type set with optional metadata."""
    if not name:
        raise ValueError("Set name is required")
    
    # Create the type set
    set_id = execute_insert(
        "INSERT INTO type_set(name, description) VALUES (?, ?)",
        (name, description)
    )
    
    # Create metadata record if provided
    if metadata:
        save_type_set_metadata(set_id, metadata)
    
    return set_id


def update_type_set(set_id: int, name: str, description: Optional[str] = None) -> int:
    """Update type set basic information."""
    if not name:
        raise ValueError("Set name is required")
    
    query = "UPDATE type_set SET name=?, description=? WHERE id=?"
    rows = execute_update(query, (name, description, set_id))
    
    # Update modified date in metadata if it exists
    execute_update(
        "UPDATE type_set_metadata SET modified_date=? WHERE set_id=?",
        (datetime.now().isoformat(), set_id)
    )
    
    return rows


def delete_type_set(set_id: int) -> int:
    """Delete a type set and all related data (cascade handles members and metadata)."""
    return execute_delete("DELETE FROM type_set WHERE id=?", (set_id,))


# ---------------------------------
# Type Set Metadata Operations
# ---------------------------------
def save_type_set_metadata(set_id: int, metadata: Dict[str, Any]) -> bool:
    """Save or update type set metadata/criteria."""
    # Convert grade text to numeric if needed
    min_numeric = None
    max_numeric = None
    
    if metadata.get('min_grade'):
        min_numeric = get_grade_numeric_value(metadata['min_grade'])
    if metadata.get('max_grade'):
        max_numeric = get_grade_numeric_value(metadata['max_grade'])
    
    # Check if metadata exists
    existing = execute_query_single(
        "SELECT set_id FROM type_set_metadata WHERE set_id=?",
        (set_id,)
    )
    
    if existing:
        # Update existing
        query = """
            UPDATE type_set_metadata SET
                grade_company=?, min_grade=?, max_grade=?,
                min_numeric_grade=?, max_numeric_grade=?,
                require_slab=?, require_cac=?,
                proof_only=?, business_only=?,
                include_varieties=?, year_start=?, year_end=?,
                modified_date=?
            WHERE set_id=?
        """
        params = (
            metadata.get('grade_company'),
            metadata.get('min_grade'),
            metadata.get('max_grade'),
            min_numeric,
            max_numeric,
            1 if metadata.get('require_slab') else 0,
            1 if metadata.get('require_cac') else 0,
            1 if metadata.get('proof_only') else 0,
            1 if metadata.get('business_only') else 0,
            1 if metadata.get('include_varieties', True) else 0,
            metadata.get('year_start'),
            metadata.get('year_end'),
            datetime.now().isoformat(),
            set_id
        )
        execute_update(query, params)
    else:
        # Insert new
        query = """
            INSERT INTO type_set_metadata(
                set_id, grade_company, min_grade, max_grade,
                min_numeric_grade, max_numeric_grade,
                require_slab, require_cac, proof_only, business_only,
                include_varieties, year_start, year_end,
                created_date, modified_date
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """
        params = (
            set_id,
            metadata.get('grade_company'),
            metadata.get('min_grade'),
            metadata.get('max_grade'),
            min_numeric,
            max_numeric,
            1 if metadata.get('require_slab') else 0,
            1 if metadata.get('require_cac') else 0,
            1 if metadata.get('proof_only') else 0,
            1 if metadata.get('business_only') else 0,
            1 if metadata.get('include_varieties', True) else 0,
            metadata.get('year_start'),
            metadata.get('year_end'),
            datetime.now().isoformat(),
            datetime.now().isoformat()
        )
        execute_insert(query, params)
    
    return True


def get_type_set_metadata(set_id: int) -> Dict[str, Any]:
    """Get metadata/criteria for a type set."""
    query = """
        SELECT * FROM type_set_metadata WHERE set_id=?
    """
    result = execute_query_single(query, (set_id,))
    
    if not result:
        return {}
    
    # Convert to more friendly format
    return {
        'grade_company': result['grade_company'],
        'min_grade': result['min_grade'],
        'max_grade': result['max_grade'],
        'min_numeric_grade': result['min_numeric_grade'],
        'max_numeric_grade': result['max_numeric_grade'],
        'require_slab': bool(result['require_slab']),
        'require_cac': bool(result['require_cac']),
        'proof_only': bool(result['proof_only']),
        'business_only': bool(result['business_only']),
        'include_varieties': bool(result['include_varieties']),
        'year_start': result['year_start'],
        'year_end': result['year_end'],
        'created_date': result['created_date'],
        'modified_date': result['modified_date']
    }


# ---------------------------------
# Type Set Progress Operations
# ---------------------------------
def get_type_set_progress(set_id: int) -> pd.DataFrame:
    """Get detailed progress for a type set using the new view."""
    query = """
        SELECT 
            coin_type_id,
            series,
            year,
            mint_mark,
            variety,
            is_proof,
            qty_on_hand,
            have_any,
            best_grade_company,
            best_grade_text,
            best_numeric_grade,
            has_slab_cert,
            required_grade_company,
            required_min_grade,
            required_max_grade,
            requires_slab,
            meets_requirements
        FROM v_type_set_progress_detailed
        WHERE set_id = ?
        ORDER BY series, year, mint_mark, variety
    """
    
    rows = execute_query_all(query, (set_id,))
    return pd.DataFrame(rows)


def get_type_set_summary(set_id: int) -> Dict[str, Any]:
    """Get summary statistics for a type set."""
    query = """
        SELECT * FROM v_type_set_summary WHERE set_id = ?
    """
    return execute_query_single(query, (set_id,))


def get_type_set_upgrade_targets(set_id: int) -> List[Dict[str, Any]]:
    """Get coins that need upgrading to meet set requirements."""
    query = """
        SELECT * FROM v_type_set_upgrade_targets
        WHERE set_id = ?
        ORDER BY series, year, mint_mark
    """
    return execute_query_all(query, (set_id,))


def get_type_set_best_candidates(set_id: int, coin_type_id: int) -> List[Dict[str, Any]]:
    """Get best candidate coins from inventory for a specific type set need."""
    query = """
        SELECT * FROM v_type_set_best_candidates
        WHERE set_id = ? AND coin_type_id = ?
        ORDER BY match_score DESC
        LIMIT 5
    """
    return execute_query_all(query, (set_id, coin_type_id))


# ---------------------------------
# Type Set Member Operations
# ---------------------------------
def get_type_set_members(set_id: int) -> List[Dict[str, Any]]:
    """Get all members of a type set."""
    query = """
        SELECT 
            m.coin_type_id,
            cm.series,
            ct.year,
            ct.mint_mark,
            COALESCE(ct.variety,'') AS variety,
            ct.is_proof
        FROM type_set_member m
        JOIN coin_type ct ON ct.id = m.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        WHERE m.set_id = ?
        ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety
    """
    return execute_query_all(query, (set_id,))


def add_type_set_members(set_id: int, coin_type_ids: List[int]) -> int:
    """Add coin types to a type set."""
    if not coin_type_ids:
        return 0
    
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
    
    # Update modified date
    execute_update(
        "UPDATE type_set_metadata SET modified_date=? WHERE set_id=?",
        (datetime.now().isoformat(), set_id)
    )
    
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
    
    # Update modified date
    execute_update(
        "UPDATE type_set_metadata SET modified_date=? WHERE set_id=?",
        (datetime.now().isoformat(), set_id)
    )
    
    return count


# ---------------------------------
# Catalog Search Functions
# ---------------------------------
def search_coin_types_catalog(
        series: Optional[List[str]] = None,
        year_range: Optional[Tuple[int, int]] = None,
        proof_filter: str = "Any",
        include_varieties: bool = True
) -> List[Dict[str, Any]]:
    """
    Search the coin catalog (all coin_types, not just what's on hand).
    This is used to define what SHOULD be in a type set.
    """
    conditions = []
    params = []
    
    # Series filter
    if series:
        placeholders = ",".join("?" for _ in series)
        conditions.append(f"cm.series IN ({placeholders})")
        params.extend(series)
    
    # Year range filter
    if year_range:
        start, end = year_range
        conditions.append("ct.year BETWEEN ? AND ?")
        params.extend([start, end])
    
    # Proof filter
    if proof_filter == "Proofs only":
        conditions.append("ct.is_proof = 1")
    elif proof_filter == "Business strikes only":
        conditions.append("(ct.is_proof IS NULL OR ct.is_proof = 0)")
    
    # Variety filter
    if not include_varieties:
        conditions.append("(ct.variety IS NULL OR ct.variety = '')")
    
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    
    query = f"""
        SELECT 
            ct.id,
            cm.series,
            ct.year,
            ct.mint_mark,
            COALESCE(ct.variety, '') AS variety,
            ct.is_proof,
            cm.country,
            cm.denomination
        FROM coin_type ct
        JOIN coin_master cm ON cm.id = ct.master_id
        {where_clause}
        ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety
    """
    
    return execute_query_all(query, tuple(params))


def search_coin_types(
        series: Optional[List[str]] = None,
        year_range: Optional[Tuple[int, int]] = None,
        proof_filter: str = "Any"
) -> List[Dict[str, Any]]:
    """Basic search for coin types (backward compatibility)."""
    return search_coin_types_catalog(series, year_range, proof_filter, True)


# ---------------------------------
# Helper Functions
# ---------------------------------
def get_grade_numeric_value(grade_text: str) -> float:
    """Convert grade text to numeric value for comparison."""
    if not grade_text:
        return 0.0
    
    # Handle numeric grades directly (MS-63, PF-70, etc.)
    import re
    match = re.match(r'[A-Z]+-?(\d+)', grade_text.upper())
    if match:
        return float(match.group(1))
    
    # Map text grades to numeric
    grade_map = {
        'P-1': 1, 'FR-2': 2, 'AG-3': 3, 'G-4': 4, 'G-6': 6,
        'VG-8': 8, 'VG-10': 10, 'F-12': 12, 'F-15': 15,
        'VF-20': 20, 'VF-25': 25, 'VF-30': 30, 'VF-35': 35,
        'XF-40': 40, 'XF-45': 45, 'AU-50': 50, 'AU-53': 53,
        'AU-55': 55, 'AU-58': 58, 'MS-60': 60, 'MS-61': 61,
        'MS-62': 62, 'MS-63': 63, 'MS-64': 64, 'MS-65': 65,
        'MS-66': 66, 'MS-67': 67, 'MS-68': 68, 'MS-69': 69,
        'MS-70': 70, 'PF-60': 60, 'PF-61': 61, 'PF-62': 62,
        'PF-63': 63, 'PF-64': 64, 'PF-65': 65, 'PF-66': 66,
        'PF-67': 67, 'PF-68': 68, 'PF-69': 69, 'PF-70': 70
    }
    
    return grade_map.get(grade_text.upper(), 0.0)


def get_all_series() -> List[str]:
    """Get all unique series from coin masters."""
    query = "SELECT DISTINCT series FROM coin_master ORDER BY series"
    results = execute_query_all(query)
    return [r['series'] for r in results]


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


# ---------------------------------
# Analysis Functions
# ---------------------------------
def analyze_missing_coins(set_id: int) -> pd.DataFrame:
    """Get coins that are missing or don't meet requirements."""
    query = """
        SELECT 
            coin_type_id,
            series,
            year,
            mint_mark,
            variety,
            CASE 
                WHEN qty_on_hand = 0 THEN 'Need to acquire'
                WHEN NOT meets_requirements THEN upgrade_needed
                ELSE NULL
            END as status
        FROM v_type_set_progress_detailed p
        LEFT JOIN v_type_set_upgrade_targets u 
            ON u.set_id = p.set_id AND u.coin_type_id = p.coin_type_id
        WHERE p.set_id = ? AND (p.qty_on_hand = 0 OR p.meets_requirements = 0)
        ORDER BY series, year, mint_mark
    """
    
    rows = execute_query_all(query, (set_id,))
    return pd.DataFrame(rows)


# For backward compatibility
def update_type_set_metadata(set_id: int, metadata: Dict[str, Any]) -> bool:
    """Alias for save_type_set_metadata."""
    return save_type_set_metadata(set_id, metadata)