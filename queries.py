# queries.py
"""Database query functions for the coin tracker application."""

from typing import List, Optional, Dict, Any
from db import get_conn
from db_operations import (
    execute_query_single, execute_query_all, execute_insert, upsert_record,
    find_or_create_party, find_or_create_storage, normalize_text_field, normalize_for_upsert
)
from query_builders import WhereClauseBuilder, InventoryQueryBuilder, SpecimenQueryHelper, SQLTemplates
from business_logic import TransactionBuilder


# ------------------------------------------------------------------
# Reference data operations
# ------------------------------------------------------------------

def create_or_update_party(name: str, kind: str = None, contact: str = None) -> Optional[int]:
    """Create or update a party record."""
    return find_or_create_party(name, kind, contact)


def create_or_update_storage(name: str, category: str = None, description: str = None) -> Optional[int]:
    """Create or update a storage location record."""
    return find_or_create_storage(name, category, description)

def create_or_update_coin_master(country: str, denomination: str, series: str, **kwargs) -> int:
    """Create or update a coin master record."""
    # Normalize optional fields
    normalized_fields = {field: normalize_for_upsert(value) for field, value in kwargs.items()}

    # Set default asset category
    if normalized_fields.get('asset_category') is None:
        normalized_fields['asset_category'] = 'COIN'

    search_fields = {'country': country, 'denomination': denomination, 'series': series}
    return upsert_record('coin_master', search_fields, normalized_fields)

#
# def create_or_update_coin_master(country: str, denomination: str, series: str, **kwargs) -> int:
#     """Create or update a coin master record."""
#     # Normalize optional fields
#     normalized_fields = {field: normalize_for_upsert(value) for field, value in kwargs.items()}
#
#     # Set default asset category
#     if normalized_fields.get('asset_category') is None:
#         normalized_fields['asset_category'] = 'COIN'
#
#     search_fields = {'country': country, 'denomination': denomination, 'series': series}
#     return upsert_record('coin_master', search_fields, normalized_fields)
#

def create_or_update_coin_type(master_id: int, year: int, mint_mark: str = None, variety: str = None, **kwargs) -> int:
    """Create or update a coin type record."""
    search_fields = {
        'master_id': master_id,
        'year': year,
        'mint_mark': normalize_text_field(mint_mark),
        'variety': normalize_text_field(variety)
    }
    return upsert_record('coin_type', search_fields, kwargs)


def get_all_coin_types() -> List[Dict[str, Any]]:
    """Get all coin types with basic information."""
    return execute_query_all("""
        SELECT ct.id, cm.series, ct.year,
               COALESCE(ct.mint_mark, '') AS mint_mark,
               COALESCE(ct.variety, '') AS variety
        FROM coin_type ct
        JOIN coin_master cm ON cm.id = ct.master_id
        ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety
    """)


# ------------------------------------------------------------------
# Portfolio and summary data
# ------------------------------------------------------------------

def get_portfolio_summary() -> Dict[str, float]:
    """Get portfolio value and coin count summary."""
    result = execute_query_single("SELECT total_estimated_value_usd, total_coins FROM v_portfolio_value_summary")
    
    return {
        "total_estimated_value_usd": float(result["total_estimated_value_usd"] or 0.0),
        "total_coins": int(result["total_coins"] or 0)
    } if result else {"total_estimated_value_usd": 0.0, "total_coins": 0}


def get_latest_metal_prices() -> List[Dict[str, Any]]:
    """Get latest metal spot prices."""
    return execute_query_all("SELECT metal, price_per_oz_usd FROM v_latest_spot")


# ------------------------------------------------------------------
# Transaction operations
# ------------------------------------------------------------------

def create_buy_transaction(tx_date: str, party_name: str = None, currency: str = "USD", 
                          shipping: float = 0.0, tax: float = 0.0, fees: float = 0.0, 
                          notes: str = None, items: List[Dict[str, Any]] = None) -> bool:
    """Create a buy transaction."""
    builder = TransactionBuilder()
    builder.set_basic_info(tx_date, 'BUY', party_name, currency)
    builder.set_costs(shipping, tax, fees)
    builder.set_notes(notes)
    
    for item in (items or []):
        builder.add_item(**item)
    
    return builder.build_buy_transaction()


def create_sell_transaction(tx_date: str, party_name: str = None, currency: str = "USD",
                           shipping: float = 0.0, tax: float = 0.0, fees: float = 0.0,
                           notes: str = None, items: List[Dict[str, Any]] = None, 
                           method: str = 'FIFO') -> bool:
    """Create a sell transaction."""
    builder = TransactionBuilder()
    builder.set_basic_info(tx_date, 'SELL', party_name, currency)
    builder.set_costs(shipping, tax, fees)
    builder.set_notes(notes)
    
    for item in (items or []):
        builder.add_item(**item)
    
    return builder.build_sell_transaction(method)


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
    
    return execute_query_all(SQLTemplates.TRANSACTION_SEARCH.format(where_clause=where_clause), params)


def get_transaction_details(tx_id: int) -> List[Dict[str, Any]]:
    """Get transaction line details for a specific transaction."""
    return execute_query_all(SQLTemplates.TX_LINES, (tx_id,))


def get_spending_summary(date_from: Optional[str] = None, date_to: Optional[str] = None,
                        party_query: Optional[str] = None, limit: int = 25, offset: int = 0) -> List[Dict[str, Any]]:
    """Get spending summary grouped by date and party."""
    builder = WhereClauseBuilder()
    builder.add_condition("t.tx_type = 'BUY'")
    builder.add_date_range(date_from, date_to)
    builder.add_like_clause("p.name", party_query)
    
    where_clause, params = builder.build()
    params.extend([limit, offset])
    
    return execute_query_all(SQLTemplates.SPENDING_LOG.format(where_clause=where_clause), params)


def get_spending_details(tx_date: str, party: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get items purchased on a specific date from a specific party."""
    builder = WhereClauseBuilder()
    builder.add_condition("t.tx_type = 'BUY'")
    builder.add_condition("t.tx_date = ?", tx_date)
    
    if party is None or party == '':
        builder.add_condition("COALESCE(p.name,'') = ''")
    else:
        builder.add_condition("COALESCE(p.name,'') = ?", party)
    
    where_clause, params = builder.build()
    
    return execute_query_all(f"""
        SELECT cm.series, SUM(ABS(tl.quantity)) AS qty
        FROM tx t
        LEFT JOIN party p ON p.id = t.party_id
        JOIN tx_line tl ON tl.tx_id = t.id
        JOIN coin_type ct ON ct.id = tl.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        {where_clause}
        GROUP BY cm.series
        ORDER BY cm.series
    """, params)


# ------------------------------------------------------------------
# Inventory queries
# ------------------------------------------------------------------

def get_all_lots() -> List[Dict[str, Any]]:
    """Get all lots with basic information."""
    return execute_query_all(f"""
        SELECT l.id, cm.series, ct.year, ct.mint_mark, COALESCE(ct.variety,'') AS variety,
               l.qty_remaining, l.unit_cost, l.valuation_method,
               COALESCE(l.estimated_grade_text, l.purchase_grade_text) AS grade,
               l.manual_est_unit_value
        {InventoryQueryBuilder.base_lot_query()}
        ORDER BY l.acquired_date DESC, l.id DESC
    """)


def get_inventory_by_type() -> List[Dict[str, Any]]:
    """Get inventory summary by coin type."""
    return execute_query_all("SELECT * FROM v_inventory_by_type ORDER BY series, year, mint_mark, variety")


def get_inventory_by_series() -> List[Dict[str, Any]]:
    """Get series-level inventory summary."""
    return execute_query_all("""
        SELECT
            series,
            SUM(qty_remaining) AS coins,
            ROUND(SUM(qty_remaining * COALESCE(chosen_unit_value,0)), 2) AS est_value_usd
        FROM v_lot_value_details
        GROUP BY series
        ORDER BY est_value_usd DESC, series
    """)


def get_storage_locations() -> List[Dict[str, Any]]:
    """Get all storage locations."""
    return execute_query_all("""
        SELECT id, name, COALESCE(category,'') AS category, COALESCE(description,'') AS description 
        FROM storage_location 
        ORDER BY name
    """)


def get_available_series(only_on_hand: bool = True) -> List[str]:
    """Get available coin series, optionally restricted to those with inventory."""
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
# Detailed inventory queries
# ------------------------------------------------------------------

def _build_detailed_inventory_query(additional_where: str = "", additional_fields: str = "") -> str:
    """Build detailed inventory query template."""
    return f"""
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


def get_inventory_details_by_series(series: str) -> List[Dict[str, Any]]:
    """Get detailed inventory for a specific series."""
    if not series:
        return []
    
    with get_conn() as cx:
        has_specimen, has_specimen_code = SpecimenQueryHelper.detect_specimen_table(cx)
        specimen_join = SpecimenQueryHelper.specimen_join_clause(has_specimen, has_specimen_code)
        specimen_field = SpecimenQueryHelper.specimen_select_field(has_specimen, has_specimen_code)
        
        query = _build_detailed_inventory_query("AND cm.series = ?", specimen_field)
        query = query.format(specimen_join=specimen_join)
        
        results = cx.execute(query, (series,)).fetchall()
        return [dict(row) for row in results]


def get_proof_inventory() -> List[Dict[str, Any]]:
    """Get detailed inventory for proof coins."""
    with get_conn() as cx:
        has_specimen, has_specimen_code = SpecimenQueryHelper.detect_specimen_table(cx)
        specimen_join = SpecimenQueryHelper.specimen_join_clause(has_specimen, has_specimen_code)
        specimen_field = SpecimenQueryHelper.specimen_select_field(has_specimen, has_specimen_code)
        
        additional_fields = f"{specimen_field}, ct.is_proof"
        query = _build_detailed_inventory_query("AND ct.is_proof = 1", additional_fields)
        query = query.format(specimen_join=specimen_join)
        
        results = cx.execute(query).fetchall()
        return [dict(row) for row in results]


def get_slabbed_inventory() -> List[Dict[str, Any]]:
    """Get detailed inventory for slabbed coins."""
    with get_conn() as cx:
        has_specimen, has_specimen_code = SpecimenQueryHelper.detect_specimen_table(cx)
        specimen_join = SpecimenQueryHelper.specimen_join_clause(has_specimen, has_specimen_code)
        specimen_field = SpecimenQueryHelper.specimen_select_field(has_specimen, has_specimen_code)
        
        additional_where = "AND l.slab_cert IS NOT NULL AND TRIM(l.slab_cert) <> ''"
        additional_fields = f", l.slab_cert{specimen_field}"
        
        query = _build_detailed_inventory_query(additional_where, additional_fields)
        query = query.format(specimen_join=specimen_join)
        
        results = cx.execute(query).fetchall()
        return [dict(row) for row in results]


# ------------------------------------------------------------------
# Dashboard and reporting
# ------------------------------------------------------------------

def get_dashboard_series_rollup() -> List[Dict[str, Any]]:
    """Get series-level rollup for dashboard display."""
    return execute_query_all("""
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
    """)


# ------------------------------------------------------------------
# Bullion queries
# ------------------------------------------------------------------

def get_bullion_by_category() -> List[Dict[str, Any]]:
    """Get bullion summary by category and metal."""
    return execute_query_all("""
        SELECT category, metal, units_on_hand, gross_oz, fine_oz, melt_value_usd
        FROM v_inventory_bullion_by_category
        ORDER BY category, metal
    """)


def get_bullion_by_series() -> List[Dict[str, Any]]:
    """Get bullion summary by series (product)."""
    return execute_query_all("""
        SELECT category, metal, series, unit_troy_oz, unit_fine_oz, units_on_hand, gross_oz, fine_oz, melt_value_usd
        FROM v_inventory_bullion_by_series
        ORDER BY category, metal, series
    """)


# ------------------------------------------------------------------
# Specimen/Flip ID operations
# ------------------------------------------------------------------

def _ensure_specimen_tables():
    """Ensure specimen tables exist (for backward compatibility)."""
    with get_conn() as cx:
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


def create_or_update_series_code(series: str, prefix: str) -> int:
    """Create or update series code configuration."""
    _ensure_specimen_tables()
    
    series = series.strip()
    prefix = prefix.strip().upper()[:3]
    
    if not series or not prefix:
        raise ValueError("Series and prefix are required.")
    
    return upsert_record('series_code', {'series': series}, {'prefix': prefix})


def allocate_specimen_codes(series: str, qty: int) -> List[str]:
    """Allocate multiple specimen codes for a series."""
    _ensure_specimen_tables()
    series = series.strip()
    
    sc = execute_query_single("SELECT id, prefix, next_seq FROM series_code WHERE series=?", (series,))
    if not sc:
        raise ValueError(f"No prefix set for series '{series}'. Set it in Specimens page.")
    
    start = sc["next_seq"]
    codes = [f"{sc['prefix']}{i}" for i in range(start, start + qty)]
    
    execute_query_single("UPDATE series_code SET next_seq = ? WHERE id=?", (start + qty, sc["id"]))
    return codes


def allocate_single_specimen_code(series: str) -> str:
    """Allocate a single specimen code for a series."""
    return allocate_specimen_codes(series, 1)[0]


def create_specimens_for_lot(lot_id: int, qty: int, start_code: str = None) -> List[str]:
    """Create specimen records for a lot."""
    _ensure_specimen_tables()
    
    if qty <= 0:
        return []
    
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
        match = re.match(r"([A-Z]+)(\d+)$", start_code.strip().upper())
        if not match:
            raise ValueError("start_code must look like P101 or CB7 (letters+digits).")
        prefix, n = match.group(1), int(match.group(2))
        codes = [f"{prefix}{n+i}" for i in range(qty)]
    else:
        codes = allocate_specimen_codes(series, qty)
    
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
    
    return execute_query_single("""
        SELECT s.code, s.notes, s.lot_id, s.sold_line_id,
               cm.series, ct.year, ct.mint_mark, ct.variety
        FROM specimen s
        JOIN coin_type ct ON ct.id = s.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        WHERE s.code = ?
    """, (code.strip().upper(),))


def get_specimens_on_hand(filter_series: str = None) -> List[Dict[str, Any]]:
    """Get specimens currently on hand."""
    _ensure_specimen_tables()
    
    builder = WhereClauseBuilder()
    builder.add_condition("s.sold_line_id IS NULL")
    
    if filter_series and filter_series.strip():
        builder.add_like_clause("cm.series", filter_series.strip(), nullable=False)
    
    where_clause, params = builder.build()
    
    return execute_query_all(f"""
        SELECT s.code, cm.series, ct.year, ct.mint_mark, ct.variety, s.lot_id
        FROM specimen s
        JOIN coin_type ct ON ct.id = s.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        {where_clause}
        ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety, s.code
    """, params)


# Add this to the end of your queries.py file for backward compatibility

# Backward compatibility aliases for existing pages
list_specimens_on_hand = get_specimens_on_hand
list_coin_types = get_all_coin_types
# upsert_coin_master = create_or_update_coin_master
get_latest_spot = get_latest_metal_prices
upsert_coin_type = create_or_update_coin_type
upsert_party = create_or_update_party
upsert_storage = create_or_update_storage
list_lots = get_all_lots
inventory_by_type = get_inventory_by_type
inventory_by_series_summary = get_inventory_by_series
list_storage_locations = get_storage_locations
list_series_for_filter = get_available_series
inventory_details_by_series = get_inventory_details_by_series
inventory_details_proof = get_proof_inventory
inventory_details_slabbed = get_slabbed_inventory
dashboard_series_rollup = get_dashboard_series_rollup
bullion_by_category = get_bullion_by_category
bullion_by_series = get_bullion_by_series
search_transactions = search_transactions  # same name
get_tx_lines = get_transaction_details
spending_log = get_spending_summary
spending_log_items = get_spending_details

# Specimen function compatibility
upsert_series_code = create_or_update_series_code
allocate_specimen_code_for_series = allocate_single_specimen_code

# Replace this line in your compatibility shim:
# upsert_coin_master = create_or_update_coin_master
# With this wrapper function:
def upsert_coin_master(country, denomination, series, metal=None, fineness=None,
                      weight_grams=None, diameter_mm=None, thickness_mm=None,
                      edge=None, years_start=None, years_end=None, notes=None,
                      asset_category=None, numista_url=None):
    """Backward compatibility wrapper for upsert_coin_master."""
    return create_or_update_coin_master(
        country, denomination, series,
        metal=metal, fineness=fineness, weight_grams=weight_grams,
        diameter_mm=diameter_mm, thickness_mm=thickness_mm, edge=edge,
        years_start=years_start, years_end=years_end, notes=notes,
        asset_category=asset_category, numista_url=numista_url
    )
