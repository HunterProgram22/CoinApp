# pages/inventory_functions.py
"""
Temporary extraction of inventory functions for testing.
These will be moved to the repository during refactoring.
"""
from infrastructure.database.db_operations import execute_query_all, execute_query_single


def get_inventory_by_type():
    """Get inventory grouped by coin type."""
    query = """
        SELECT
            ct.id AS coin_type_id,
            cm.series,
            ct.year,
            ct.mint_mark,
            COALESCE(ct.variety, '') AS variety,
            SUM(l.qty_remaining) AS coins_on_hand
        FROM lot l
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        WHERE l.qty_remaining > 0
        GROUP BY ct.id, cm.series, ct.year, ct.mint_mark, ct.variety
        ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety
    """
    return execute_query_all(query)


def get_inventory_by_series(country_filter="All"):
    """Get inventory summary by series using v_lot_value_details view."""
    # Check if view exists first
    view_check = execute_query_single(
        "SELECT 1 FROM sqlite_master WHERE type='view' AND name='v_lot_value_details'"
    )

    # Build WHERE clause based on filter
    where_clause = ""
    if country_filter == "US Only":
        where_clause = "WHERE cm.country = 'USA'"
    elif country_filter == "World Only":
        where_clause = "WHERE cm.country != 'USA'"

    if view_check:
        query = f"""
            SELECT
                cm.series as series,
                cm.country,
                SUM(v.qty_remaining) AS coins,
                ROUND(SUM(v.qty_remaining * COALESCE(v.chosen_unit_value, 0)), 2) AS est_value_usd
            FROM v_lot_value_details v
            JOIN lot l ON l.id = v.lot_id
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            {where_clause}
            GROUP BY cm.series, cm.country
            ORDER BY est_value_usd DESC, cm.series
        """
    else:
        # Fallback if view doesn't exist
        query = f"""
            SELECT 
                cm.series AS series,
                cm.country,
                SUM(l.qty_remaining) AS coins, 
                NULL AS est_value_usd
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE l.qty_remaining > 0
            {' AND ' + where_clause.replace('WHERE ', '') if where_clause else ''}
            GROUP BY cm.series, cm.country
            ORDER BY coins DESC, cm.series
        """

    return execute_query_all(query)


def get_series_list():
    """Get list of available series."""
    query = "SELECT DISTINCT series FROM coin_master ORDER BY series"
    results = execute_query_all(query)
    return [r['series'] for r in results]


def get_countries_with_inventory():
    """Get list of countries that have inventory on hand."""
    query = """
        SELECT DISTINCT cm.country
        FROM lot l
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        WHERE l.qty_remaining > 0 AND cm.country IS NOT NULL
        ORDER BY cm.country
    """
    results = execute_query_all(query)
    return [r['country'] for r in results]


def get_series_list_for_country(country=None):
    """Get list of available series, optionally filtered by country."""
    if country:
        query = """
            SELECT DISTINCT cm.series 
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE l.qty_remaining > 0 AND cm.country = ?
            ORDER BY cm.series
        """
        results = execute_query_all(query, (country,))
    else:
        query = "SELECT DISTINCT series FROM coin_master ORDER BY series"
        results = execute_query_all(query)
    return [r['series'] for r in results]
