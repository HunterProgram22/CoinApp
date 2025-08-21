# patches/queries_bullion_additions.py
from db import get_conn

def bullion_by_category():
    """Summary of bullion (ROUND/BAR) totals by category & metal."""
    with get_conn() as cx:
        rows = cx.execute("""
            SELECT category, metal, units_on_hand, gross_oz, fine_oz, melt_value_usd
            FROM v_inventory_bullion_by_category
            ORDER BY category, metal
        """).fetchall()
        return [dict(r) for r in rows]

def bullion_by_series():
    """Summary of bullion (ROUND/BAR) totals by series (product), including unit oz and fine oz."""
    with get_conn() as cx:
        rows = cx.execute("""
            SELECT category, metal, series, unit_troy_oz, unit_fine_oz, units_on_hand, gross_oz, fine_oz, melt_value_usd
            FROM v_inventory_bullion_by_series
            ORDER BY category, metal, series
        """).fetchall()
        return [dict(r) for r in rows]
