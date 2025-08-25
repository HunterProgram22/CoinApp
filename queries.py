# queries.py
"""Database query functions for the coin tracker application."""

from typing import List, Optional, Dict, Any
from db_operations import (
    execute_query_single, execute_query_all, execute_insert, upsert_record,
    find_or_create_party, find_or_create_storage, normalize_text_field, normalize_for_upsert
)
from query_builders import WhereClauseBuilder, InventoryQueryBuilder, SpecimenQueryHelper, SQLTemplates
from business_logic import create_buy_transaction, create_sell_transaction  # For backward compatibility


# ------------------------------------------------------------------
# Reference data CRUD (simplified using helpers)
# ------------------------------------------------------------------

def upsert_party(name: str, kind: str = None, contact: str = None) -> Optional[int]:
    """Create or update a party record."""
    return find_or_create_party(name, kind, contact)


def upsert_storage(name: str, category: str = None, description: str = None) -> Optional[int]:
    """Create or update a storage location record."""
    return find_or_create_storage(name, category, description)


def upsert_coin_master(country: str, denomination: str, series: str, **kwargs) -> int:
    """Create or update a coin master record."""
    # Normalize optional fields
    normalized_fields = {}
    for field, value in kwargs.items():
        normalized_fields[field] = normalize_for_upsert(value)
    
    # Set default asset category
    if normalized_fields.get('asset_category') is None:
        normalized_fields['asset_category'] = 'COIN'
    
    search_fields = {
        'country': country,
        'denomination': denomination,
        'series': series
    }
    
    return upsert_record('coin_master', search_fields, normalized_fields)


def upsert_coin_type(master_id: int, year: int, mint_mark: str = None, variety: str = None, **kwargs) -> int:
    """Create or update a coin type record."""
    mint_mark = normalize_text_field(mint_mark)
    variety = normalize_text_field(variety)
    
    search_fields = {
        'master_id': master_id,
        'year': year,
        'mint_mark': mint_mark,
        'variety': variety
    }
    
    return upsert_record('coin_type', search_fields, kwargs)


def list_coin_types() -> List[Dict[str, Any]]:
    """List all coin types with basic information."""
    query = """
        SELECT ct.id, cm.series, ct.year,
               COALESCE(ct.mint_mark, '') AS mint_mark,
               COALESCE(ct.variety, '') AS variety
        FROM coin_type ct
        JOIN coin_master cm ON cm.id = ct.master_id
        ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety
    """
    return execute_query_all(query)


# ------------------------------------------------------------------
# Portfolio and summary queries
# ------------------------------------------------------------------

def get_portfolio_summary() -> Dict[str, Any]:
    """Get portfolio value and coin count summary."""
    result = execute_query_single("SELECT total_estimated_value_usd, total_coins FROM v_portfolio_value_summary")
    
    if not result:
        return {"total_estimated_value_usd": 0.0, "total_coins": 0}
    
    return {
        "total_estimated_value_usd": result["total_estimated_value_usd"] or 0.0,
        "total_coins": result["total_coins"] or 0
    }


def get_latest_spot() -> List[Dict[str, Any]]:
    """Get latest metal spot prices."""
    return execute_query_all("SELECT metal, price_per_oz_usd FROM v_latest_spot")


# ------------------------------------------------------------------
# Inventory queries (using builders to reduce duplication)
# ------------------------------------------------------------------

def list_lots() -> List[Dict[str, Any]]:
    """List all lots with basic information."""
    query = f"""
        SELECT l.id, cm.series, ct.year, ct.mint_mark, COALESCE(ct.variety,'') AS variety,
               l.qty_remaining, l.unit_cost, l.valuation_method,
               COALESCE(l.estimated_grade_text, l.purchase_grade_text) AS grade,
               l.manual_est_unit_value
        {InventoryQueryBuilder.base_lot_query()}
        ORDER BY l.acquired_date DESC, l.id DESC
    """
    return execute_query_all(query)


def inventory_by_type() -> List[Dict[str, Any]]:
    """Get inventory summary by coin type."""
    return execute_query_all(
        "SELECT * FROM v_inventory_by_type ORDER BY series, year, mint_mark, variety"
    )


def inventory_by_series_summary() -> List[Dict[str, Any]]:
    """Get series-level inventory summary."""
    query = """
        SELECT
            series,
            SUM(qty_remaining) AS coins,
            ROUND(SUM(qty_remaining * COALESCE(chosen_unit_value,0)), 2) AS est_value_usd
        FROM v_lot_value_details
        GROUP BY series
        ORDER BY est_value_usd DESC, series
    """
    return execute_query_all(query)


def list_storage_locations() -> List[Dict[str, Any]]:
    """List all storage locations."""
    query = """
        SELECT id, name, COALESCE(category,'') AS category, COALESCE(description,'') AS description 
        FROM storage_location 
        ORDER BY name
    """
    return execute_query_all(query)


def list_series_for_filter(only_on_hand: bool = True) -> List[str]:
    """Get distinct coin series, optionally restricted to those with coins on hand."""
    if only_on_hand:
        query = """
            SELECT DISTINCT cm.series
            FROM coin_master cm
            JOIN coin_type ct ON ct.master_id = cm.id
            JOIN lot l ON l.coin_type_id = ct.id
            WHERE l.qty_remaining > 0
            ORDER BY cm.series
        """
    else:
        query = "SELECT DISTINCT series FROM coin_master ORDER BY series"
    
    results = execute_query_all(query)
    return [row['series'] if isinstance(row, dict) else row[0] for row in results]


# ------------------------------------------------------------------
# Detailed inventory queries (using builders)
# ------------------------------------------------------------------

def _build_inventory_detail_query(additional_where: str = "", additional_fields: str = "") -> str:
    """Build detailed inventory query with common structure."""
    query = f"""
        {InventoryQueryBuilder.melt_value_cte()}
        SELECT
            {InventoryQueryBuilder.standard_lot_fields()},
            {InventoryQueryBuilder.melt_calculation_fields()}
            {additional_fields}
        {InventoryQueryBuilder.base_lot_query()}
        {{specimen_join}}
        WHERE l.qty_remaining > 0 {additional_where}
        {InventoryQueryBuilder.standard_order_by()}
    """
    return query


def inventory_details_by_series(series: str) -> List[Dict[str, Any]]:
    """Get detailed inventory for a specific series."""
    if not series:
        return []
    
    with db.get_conn() as cx:
        has_specimen, has_specimen_code = SpecimenQueryHelper.detect_specimen_table(cx)
        specimen_join = SpecimenQueryHelper.specimen_join_clause(has_specimen, has_specimen_code)
        specimen_field = SpecimenQueryHelper.specimen_select_field(has_specimen, has_specimen_code)
        
        query = _build_inventory_detail_query("AND cm.series = ?", specimen_field)
        query = query.format(specimen_join=specimen_join)
        
        results = cx.execute(query, (series,)).fetchall()
        return [dict(row) for row in results]


def inventory_details_proof() -> List[Dict[str, Any]]:
    """Get detailed inventory for proof coins."""
    with db.get_conn() as cx:
        has_specimen, has_specimen_code = SpecimenQueryHelper.detect_specimen_table(cx)
        specimen_join = SpecimenQueryHelper.specimen_join_clause(has_specimen, has_specimen_code)
        specimen_field = SpecimenQueryHelper.specimen_select_field(has_specimen, has_specimen_code)
        
        additional_fields = f"{specimen_field}, ct.is_proof"
        query = _build_inventory_detail_query("AND ct.is_proof = 1", additional_fields)
        query = query.format(specimen_join=specimen_join)
        
        results = cx.execute(query).fetchall()
        return [dict(row) for row in results]


def inventory_details_slabbed() -> List[Dict[str, Any]]:
    """Get detailed inventory for slabbed coins."""
    with db.get_conn() as cx:
        has_specimen, has_specimen_code = SpecimenQueryHelper.detect_specimen_table(cx)
        specimen_join = SpecimenQueryHelper.specimen_join_clause(has_specimen, has_specimen_code)
        specimen_field = SpecimenQueryHelper.specimen_select_field(has_specimen, has_specimen_code)
        
        additional_where = "AND l.slab_cert IS NOT NULL AND TRIM(l.slab_cert) <> ''"
        additional_fields = f", l.slab_cert{specimen_field}"
        
        query = _build_inventory_detail_query(additional_where, additional_fields)
        query = query.format(specimen_join=specimen_join)
        
        results = cx.execute(query).fetchall()
        return [dict(row) for row in results]


# ------------------------------------------------------------------
# Transaction queries (using builders)
# ------------------------------------------------------------------

def search_transactions(date_from: Optional[str] = None, date_to: Optional[str] = None,
                       tx_types: Optional[List[str]] = None, party_query: Optional[str] = None,
                       limit: int = 25, offset: int = 0) -> List[Dict[str, Any]]:
    """Search transactions with optional filters."""
    builder = WhereClauseBuilder()
    builder.add_date_range(date_from, date_to)
    builder.add_in_clause("t.tx_type", tx_types)
    builder.add_like_clause("p.name", party_query)
    
    where_clause, params = builder.build()
    params.extend([limit, offset])
    
    query = SQLTemplates.TRANSACTION_SEARCH.format(where_clause=where_clause)
    return execute_query_all(query, params)


def get_tx_lines(tx_id: int) -> List[Dict[str, Any]]:
    """Get transaction lines for a specific transaction."""
    return execute_query_all(SQLTemplates.TX_LINES, (tx_id,))


def spending_log(date_from: Optional[str] = None, date_to: Optional[str] = None,
                party_query: Optional[str] = None, limit: int = 25, offset: int = 0) -> List[Dict[str, Any]]:
    """Get spending log grouped by date and party."""
    builder = WhereClauseBuilder()
    builder.add_condition("t.tx_type = 'BUY'")
    builder.add_date_range(date_from, date_to)
    builder.add_like_clause("p.name", party_query)
    
    where_clause, params = builder.build()
    params.extend([limit, offset])
    
    query = SQLTemplates.SPENDING_LOG.format(where_clause=where_clause)
    return execute_query_all(query, params)


def spending_log_items(tx_date: str, party: Optional[str]) -> List[Dict[str, Any]]:
    """Get items purchased on a specific date from a specific party."""
    builder = WhereClauseBuilder()
    builder.add_condition("t.tx_type = 'BUY'")
    builder.add_condition("t.tx_date = ?", tx_date)
    
    if party is None or party == '':
        builder.add_condition("COALESCE(p.name,'') = ''")
    else:
        builder.add_condition("COALESCE(p.name,'') = ?", party)
    
    where_clause, params = builder.build()
    
    query = f"""
        SELECT cm.series, SUM(ABS(tl.quantity)) AS qty
        FROM tx t
        LEFT JOIN party p ON p.id = t.party_id
        JOIN tx_line tl ON tl.tx_id = t.id
        JOIN coin_type ct ON ct.id = tl.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        {where_clause}
        GROUP BY cm.series
        ORDER BY cm.series
    """
    return execute_query_all(query, params)


# ------------------------------------------------------------------
# Dashboard and rollup queries
# ------------------------------------------------------------------

def dashboard_series_rollup() -> List[Dict[str, Any]]:
    """Get series-level rollup for dashboard."""
    query = """
        SELECT
            cm.series AS series,
            SUM(l.qty_remaining) AS coins,
            ROUND(SUM(l.qty_remaining * v.melt_unit_value), 2) AS melt_total_usd,
            ROUND(SUM(
                l.qty_remaining * COALESCE(
                    v.guide_unit_value,
                    CASE WHEN l.valuation_method = 'MANUAL' THEN l.manual_est_unit_value END
                )
            ), 2) AS numi_total_usd,
            ROUND(SUM(l.qty_remaining * l.unit_cost), 2) AS cost_total_usd,
            ROUND(SUM(l.qty_remaining * v.chosen_unit_value), 2) AS chosen_total_usd
        FROM v_lot_value_details v
        JOIN lot l ON l.id = v.lot_id
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        GROUP BY cm.series
        ORDER BY chosen_total_usd DESC, cm.series
    """
    return execute_query_all(query)


# ------------------------------------------------------------------
# Bullion queries
# ------------------------------------------------------------------

def bullion_by_category() -> List[Dict[str, Any]]:
    """Get bullion summary by category and metal."""
    return execute_query_all("""
        SELECT category, metal, units_on_hand, gross_oz, fine_oz, melt_value_usd
        FROM v_inventory_bullion_by_category
        ORDER BY category, metal
    """)


def bullion_by_series() -> List[Dict[str, Any]]:
    """Get bullion summary by series (product)."""
    return execute_query_all("""
        SELECT category, metal, series, unit_troy_oz, unit_fine_oz, units_on_hand, gross_oz, fine_oz, melt_value_usd
        FROM v_inventory_bullion_by_series
        ORDER BY category, metal, series
    """)


# ------------------------------------------------------------------
# Specimen/Flip ID functions (kept as-is for backward compatibility)
# ------------------------------------------------------------------

def _ensure_specimen_tables():
    """Safety: create specimen & series_code tables if schema is older."""
    with db.get_conn() as cx:
        cx.execute("""
        CREATE TABLE IF NOT EXISTS series_code (
            id INTEGER PRIMARY KEY,
            series TEXT NOT NULL UNIQUE,
            prefix TEXT NOT NULL,
            next_seq INTEGER NOT NULL DEFAULT 1
        )""")
        cx.execute("""
        CREATE TABLE IF NOT EXISTS specimen (
            id INTEGER PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            coin_type_id INTEGER NOT NULL REFERENCES coin_type(id),
            lot_id INTEGER REFERENCES lot(id),
            sold_line_id INTEGER REFERENCES tx_line(id),
            notes TEXT
        )""")


def upsert_series_code(series: str, prefix: str) -> int:
    """Create or update series code configuration."""
    _ensure_specimen_tables()
    
    series = series.strip()
    prefix = prefix.strip().upper()[:3]
    
    if not series or not prefix:
        raise ValueError("Series and prefix are required.")
    
    return upsert_record(
        'series_code',
        {'series': series},
        {'prefix': prefix}
    )


def _allocate_code(series: str, qty: int) -> List[str]:
    """Allocate specimen codes for a series."""
    _ensure_specimen_tables()
    series = series.strip()
    
    with db.get_conn() as cx:
        sc = execute_query_single("SELECT id, prefix, next_seq FROM series_code WHERE series=?", (series,))
        if not sc:
            raise ValueError(f"No prefix set for series '{series}'. Set it in Specimens page.")
        
        start = sc["next_seq"]
        codes = [f"{sc['prefix']}{i}" for i in range(start, start + qty)]
        
        execute_query_single("UPDATE series_code SET next_seq = ? WHERE id=?", (start + qty, sc["id"]))
        return codes


def allocate_specimen_code_for_series(series: str) -> str:
    """Allocate a single specimen code for a series."""
    return _allocate_code(series, 1)[0]


def create_specimens_for_lot(lot_id: int, qty: int, start_code: str = None) -> List[str]:
    """Create specimen records for a lot."""
    _ensure_specimen_tables()
    
    if qty <= 0:
        return []
    
    # Get lot information
    lot = execute_query_single("""
        SELECT l.id, l.coin_type_id, cm.series
        FROM lot l
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        WHERE l.id=?
    """, (lot_id,))
    
    if not lot:
        raise ValueError("Unknown lot_id")
    
    series = lot["series"]
    coin_type_id = lot["coin_type_id"]
    
    # Determine codes to create
    if start_code:
        import re
        s = start_code.strip().upper()
        match = re.match(r"([A-Z]+)(\d+)$", s)
        if not match:
            raise ValueError("start_code must look like P101 or CB7 (letters+digits).")
        prefix, n = match.group(1), int(match.group(2))
        codes = [f"{prefix}{n+i}" for i in range(qty)]
    else:
        codes = _allocate_code(series, qty)
    
    # Create specimen records
    created = []
    for code in codes:
        existing = execute_query_single("SELECT 1 FROM specimen WHERE code=?", (code,))
        if not existing:
            execute_insert("INSERT INTO specimen(code, coin_type_id, lot_id) VALUES (?,?,?)",
                          (code, coin_type_id, lot_id))
            created.append(code)
    
    return created


def get_specimen_by_code(code: str) -> Optional[Dict[str, Any]]:
    """Get specimen information by code."""
    _ensure_specimen_tables()
    code = code.strip().upper()
    
    return execute_query_single("""
        SELECT s.code, s.notes, s.lot_id, s.sold_line_id,
               cm.series, ct.year, ct.mint_mark, ct.variety
        FROM specimen s
        JOIN coin_type ct ON ct.id = s.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        WHERE s.code = ?
    """, (code,))


def list_specimens_on_hand(filter_series: str = None) -> List[Dict[str, Any]]:
    """List specimens currently on hand."""
    _ensure_specimen_tables()
    
    builder = WhereClauseBuilder()
    builder.add_condition("s.sold_line_id IS NULL")
    
    if filter_series and filter_series.strip():
        builder.add_like_clause("cm.series", filter_series.strip(), nullable=False)
    
    where_clause, params = builder.build()
    
    query = f"""
        SELECT s.code, cm.series, ct.year, ct.mint_mark, ct.variety, s.lot_id
        FROM specimen s
        JOIN coin_type ct ON ct.id = s.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        {where_clause}
        ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety, s.code
    """
    
    return execute_query_all(query, params)


# Import necessary modules at the end to avoid circular imports
from db import get_conn
import db
