# report_logic.py
"""Business logic for Seller Report and Collection Value Report."""

from typing import List, Dict, Any
from CoinApp.infastructure.database.db_operations import execute_query_all, execute_query_single
import pandas as pd


# =============================================================================
# SELLER REPORT LOGIC
# =============================================================================

def get_sellers_with_transactions() -> List[Dict[str, Any]]:
    """Get all parties who have sold coins (BUY transactions)."""
    query = """
        SELECT 
            p.id,
            p.name,
            COUNT(DISTINCT t.id) as transaction_count,
            COUNT(DISTINCT DATE(t.tx_date)) as logical_transaction_count,
            MIN(t.tx_date) as first_transaction,
            MAX(t.tx_date) as last_transaction,
            SUM(ABS(tl.quantity)) as total_coins
        FROM tx t
        JOIN party p ON p.id = t.party_id
        JOIN tx_line tl ON tl.tx_id = t.id
        WHERE t.tx_type = 'BUY' AND p.name IS NOT NULL
        GROUP BY p.id, p.name
        ORDER BY p.name
    """
    results = execute_query_all(query)
    
    for result in results:
        if 'transaction_count' in result and 'db_transaction_count' not in result:
            result['db_transaction_count'] = result['transaction_count']
        if 'logical_transaction_count' not in result:
            result['logical_transaction_count'] = result.get('transaction_count', 0)
    
    return results


def get_seller_summary(party_id: int, group_by_date: bool = True) -> Dict[str, Any]:
    """Get summary statistics for a specific seller."""
    if group_by_date:
        transaction_count_sql = "COUNT(DISTINCT DATE(tx_date)) as unique_transactions"
    else:
        transaction_count_sql = "COUNT(DISTINCT tx_id) as unique_transactions"
    
    query = f"""
        WITH purchase_data AS (
            SELECT 
                t.id as tx_id,
                t.tx_date,
                tl.id as line_id,
                tl.coin_type_id,
                ABS(tl.quantity) as quantity,
                tl.unit_price,
                l.id as lot_id,
                l.qty_remaining,
                l.unit_cost,
                l.unit_cost * l.qty_remaining as lot_cost,
                v.chosen_unit_value,
                v.chosen_unit_value * l.qty_remaining as current_value
            FROM tx t
            JOIN tx_line tl ON tl.tx_id = t.id
            JOIN lot l ON l.acquisition_line_id = tl.id
            LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
            WHERE t.party_id = ? AND t.tx_type = 'BUY'
        )
        SELECT 
            {transaction_count_sql},
            COUNT(DISTINCT tx_id) as database_transactions,
            COALESCE(SUM(quantity), 0) as total_coins_purchased,
            COUNT(DISTINCT coin_type_id) as unique_coin_types,
            COALESCE(SUM(lot_cost), 0) as total_cost_usd,
            COALESCE(SUM(current_value), 0) as total_current_value_usd,
            COALESCE(SUM(current_value) - SUM(lot_cost), 0) as unrealized_gain_loss,
            CASE 
                WHEN SUM(lot_cost) > 0 THEN 
                    ((SUM(current_value) - SUM(lot_cost)) / SUM(lot_cost)) * 100
                ELSE 0 
            END as gain_loss_percent,
            COALESCE(SUM(qty_remaining), 0) as coins_still_held,
            COALESCE(SUM(quantity) - SUM(qty_remaining), 0) as coins_sold
        FROM purchase_data
    """
    result = execute_query_single(query, (party_id,))
    
    if result:
        for key in ['unique_transactions', 'database_transactions', 'total_coins_purchased', 
                    'unique_coin_types', 'total_cost_usd', 'total_current_value_usd',
                    'unrealized_gain_loss', 'gain_loss_percent', 'coins_still_held', 'coins_sold']:
            if key not in result or result[key] is None:
                result[key] = 0
    
    return result if result else {}


def get_seller_detail_by_coin_type(party_id: int) -> List[Dict[str, Any]]:
    """Get detailed purchases by coin type from a specific seller."""
    query = """
        SELECT 
            cm.series,
            ct.year,
            ct.mint_mark,
            COALESCE(ct.variety, '') as variety,
            cm.metal,
            cm.asset_category,
            COUNT(DISTINCT t.id) as purchase_transactions,
            SUM(ABS(tl.quantity)) as total_purchased,
            ROUND(AVG(tl.unit_price), 2) as avg_purchase_price,
            ROUND(SUM(ABS(tl.quantity) * tl.unit_price), 2) as total_spent,
            SUM(l.qty_remaining) as qty_remaining,
            ROUND(SUM(l.qty_remaining * l.unit_cost), 2) as cost_of_remaining,
            ROUND(SUM(l.qty_remaining * v.chosen_unit_value), 2) as current_value,
            ROUND(SUM(l.qty_remaining * v.chosen_unit_value) - SUM(l.qty_remaining * l.unit_cost), 2) as unrealized_gl,
            MIN(t.tx_date) as first_purchase,
            MAX(t.tx_date) as last_purchase,
            COALESCE(MAX(l.estimated_grade_text), MAX(l.purchase_grade_text)) as best_grade
        FROM tx t
        JOIN tx_line tl ON tl.tx_id = t.id
        JOIN coin_type ct ON ct.id = tl.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        JOIN lot l ON l.acquisition_line_id = tl.id
        LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
        WHERE t.party_id = ? AND t.tx_type = 'BUY'
        GROUP BY cm.series, ct.year, ct.mint_mark, ct.variety, cm.metal, cm.asset_category
        ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety
    """
    return execute_query_all(query, (party_id,))


def get_seller_transactions(party_id: int, group_by_date: bool = True) -> List[Dict[str, Any]]:
    """Get all transactions from a specific seller, optionally grouped by date."""
    if group_by_date:
        query = """
            SELECT 
                GROUP_CONCAT(t.id, ', ') as tx_ids,
                COUNT(DISTINCT t.id) as db_transaction_count,
                t.tx_date,
                SUM(line_counts.line_items) as line_items,
                SUM(line_counts.total_quantity) as total_quantity,
                ROUND(SUM(line_counts.subtotal), 2) as subtotal,
                ROUND(SUM(t.shipping), 2) as shipping,
                ROUND(SUM(t.tax), 2) as tax,
                ROUND(SUM(t.fees), 2) as fees,
                ROUND(SUM(line_counts.subtotal) + 
                      SUM(COALESCE(t.shipping, 0)) + 
                      SUM(COALESCE(t.tax, 0)) + 
                      SUM(COALESCE(t.fees, 0)), 2) as total,
                GROUP_CONCAT(NULLIF(t.notes, ''), '; ') as notes
            FROM tx t
            JOIN (
                SELECT 
                    tl.tx_id,
                    COUNT(tl.id) as line_items,
                    SUM(ABS(tl.quantity)) as total_quantity,
                    SUM(ABS(tl.quantity) * tl.unit_price) as subtotal
                FROM tx_line tl
                GROUP BY tl.tx_id
            ) line_counts ON line_counts.tx_id = t.id
            WHERE t.party_id = ? AND t.tx_type = 'BUY'
            GROUP BY t.tx_date
            ORDER BY t.tx_date DESC
        """
    else:
        query = """
            SELECT 
                t.id as tx_ids,
                1 as db_transaction_count,
                t.tx_date,
                COUNT(tl.id) as line_items,
                SUM(ABS(tl.quantity)) as total_quantity,
                ROUND(SUM(ABS(tl.quantity) * tl.unit_price), 2) as subtotal,
                t.shipping,
                t.tax,
                t.fees,
                ROUND(SUM(ABS(tl.quantity) * tl.unit_price) + 
                      COALESCE(t.shipping, 0) + COALESCE(t.tax, 0) + COALESCE(t.fees, 0), 2) as total,
                t.notes
            FROM tx t
            JOIN tx_line tl ON tl.tx_id = t.id
            WHERE t.party_id = ? AND t.tx_type = 'BUY'
            GROUP BY t.id, t.tx_date, t.shipping, t.tax, t.fees, t.notes
            ORDER BY t.tx_date DESC
        """
    
    return execute_query_all(query, (party_id,))


# =============================================================================
# COLLECTION VALUE REPORT LOGIC
# =============================================================================

def get_collection_value_summary() -> Dict[str, Any]:
    """Get overall collection value summary."""
    query = """
        WITH summary AS (
            SELECT 
                COUNT(DISTINCT l.id) as total_lots,
                SUM(l.qty_remaining) as total_coins,
                ROUND(SUM(l.qty_remaining * l.unit_cost), 2) as total_cost,
                ROUND(SUM(l.qty_remaining * v.melt_unit_value), 2) as total_melt_value,
                ROUND(SUM(l.qty_remaining * v.chosen_unit_value), 2) as total_estimated_value
            FROM lot l
            LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
            WHERE l.qty_remaining > 0
        )
        SELECT 
            total_lots,
            total_coins,
            total_cost,
            total_melt_value,
            total_estimated_value,
            ROUND(total_estimated_value - total_cost, 2) as unrealized_gain_loss,
            CASE 
                WHEN total_cost > 0 THEN ROUND((total_estimated_value - total_cost) / total_cost * 100, 2)
                ELSE 0 
            END as gain_loss_percent
        FROM summary
    """
    result = execute_query_single(query)
    return result if result else {}


def get_value_by_category() -> List[Dict[str, Any]]:
    """Get collection value broken down by asset category."""
    query = """
        SELECT 
            COALESCE(cm.asset_category, 'UNCATEGORIZED') as category,
            COUNT(DISTINCT l.id) as lots,
            SUM(l.qty_remaining) as coins,
            ROUND(SUM(l.qty_remaining * l.unit_cost), 2) as cost,
            ROUND(SUM(l.qty_remaining * v.melt_unit_value), 2) as melt_value,
            ROUND(SUM(l.qty_remaining * v.chosen_unit_value), 2) as estimated_value,
            ROUND(SUM(l.qty_remaining * v.chosen_unit_value) - SUM(l.qty_remaining * l.unit_cost), 2) as unrealized_gl
        FROM lot l
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
        WHERE l.qty_remaining > 0
        GROUP BY cm.asset_category
        ORDER BY estimated_value DESC
    """
    return execute_query_all(query)


def get_value_by_metal() -> List[Dict[str, Any]]:
    """Get collection value broken down by metal type."""
    query = """
        SELECT 
            COALESCE(cm.metal, 'UNKNOWN') as metal,
            COUNT(DISTINCT l.id) as lots,
            SUM(l.qty_remaining) as coins,
            ROUND(SUM(l.qty_remaining * l.unit_cost), 2) as cost,
            ROUND(SUM(l.qty_remaining * v.melt_unit_value), 2) as melt_value,
            ROUND(SUM(l.qty_remaining * v.chosen_unit_value), 2) as estimated_value,
            ROUND(SUM(l.qty_remaining * v.chosen_unit_value) - SUM(l.qty_remaining * l.unit_cost), 2) as unrealized_gl,
            -- Calculate metal weight
            ROUND(SUM(l.qty_remaining * cm.weight_grams * COALESCE(cm.fineness, 0)) / 31.1035, 4) as troy_oz_fine
        FROM lot l
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
        WHERE l.qty_remaining > 0
        GROUP BY cm.metal
        ORDER BY estimated_value DESC
    """
    return execute_query_all(query)


def get_top_valued_coins(limit: int = 20) -> List[Dict[str, Any]]:
    """Get top valued individual coin lots."""
    query = """
        SELECT 
            cm.series,
            ct.year,
            ct.mint_mark,
            ct.variety,
            l.qty_remaining,
            COALESCE(l.estimated_grade_text, l.purchase_grade_text) as grade,
            ROUND(l.unit_cost, 2) as unit_cost,
            ROUND(v.chosen_unit_value, 2) as unit_value,
            ROUND(l.qty_remaining * v.chosen_unit_value, 2) as total_value,
            ROUND((v.chosen_unit_value - l.unit_cost) * l.qty_remaining, 2) as unrealized_gl
        FROM lot l
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
        WHERE l.qty_remaining > 0 AND v.chosen_unit_value > 0
        ORDER BY total_value DESC
        LIMIT ?
    """
    return execute_query_all(query, (limit,))


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def format_currency(value: float) -> str:
    """Format a number as currency."""
    return f"${value:,.2f}"


def format_percentage(value: float) -> str:
    """Format a number as percentage."""
    return f"{value:.1f}%"


def export_to_csv(data: List[Dict[str, Any]], filename: str) -> bytes:
    """Convert data to CSV format for export."""
    if not data:
        return b""
    
    df = pd.DataFrame(data)
    return df.to_csv(index=False).encode('utf-8')
