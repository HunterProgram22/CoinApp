# report_logic.py
"""Business logic for all report generation."""

from typing import List, Dict, Any, Optional, Tuple
from datetime import date, datetime, timedelta
from db_operations import execute_query_all, execute_query_single
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
# GAIN/LOSS REPORT LOGIC
# =============================================================================

def get_realized_gains_losses(date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict[str, Any]:
    """Get realized gains and losses from sales."""
    where_clauses = ["t_sell.tx_type = 'SELL'"]
    params = []
    
    if date_from:
        where_clauses.append("t_sell.tx_date >= ?")
        params.append(date_from)
    if date_to:
        where_clauses.append("t_sell.tx_date <= ?")
        params.append(date_to)
    
    where_clause = " AND ".join(where_clauses)
    
    query = f"""
        WITH sales AS (
            SELECT 
                tl_sell.id as sale_line_id,
                t_sell.tx_date as sale_date,
                t_sell.party_id as buyer_id,
                tl_sell.coin_type_id,
                ABS(tl_sell.quantity) as quantity_sold,
                tl_sell.unit_price as sale_price,
                ABS(tl_sell.quantity) * tl_sell.unit_price as sale_proceeds
            FROM tx t_sell
            JOIN tx_line tl_sell ON tl_sell.tx_id = t_sell.id
            WHERE {where_clause}
        ),
        cost_basis AS (
            SELECT 
                ld.disposal_line_id,
                SUM(ld.quantity * l.unit_cost) as total_cost_basis
            FROM lot_disposal ld
            JOIN lot l ON l.id = ld.lot_id
            GROUP BY ld.disposal_line_id
        )
        SELECT 
            COUNT(DISTINCT s.sale_line_id) as total_sales,
            COALESCE(SUM(s.quantity_sold), 0) as coins_sold,
            ROUND(COALESCE(SUM(s.sale_proceeds), 0), 2) as total_proceeds,
            ROUND(COALESCE(SUM(cb.total_cost_basis), 0), 2) as total_cost_basis,
            ROUND(COALESCE(SUM(s.sale_proceeds - cb.total_cost_basis), 0), 2) as realized_gain_loss
        FROM sales s
        LEFT JOIN cost_basis cb ON cb.disposal_line_id = s.sale_line_id
    """
    
    result = execute_query_single(query, params)
    return result if result else {}


def get_unrealized_gains_losses() -> Dict[str, Any]:
    """Get unrealized gains and losses on current inventory."""
    query = """
        SELECT 
            COUNT(DISTINCT l.id) as total_lots,
            SUM(l.qty_remaining) as coins_held,
            ROUND(SUM(l.qty_remaining * l.unit_cost), 2) as total_cost_basis,
            ROUND(SUM(l.qty_remaining * v.chosen_unit_value), 2) as current_value,
            ROUND(SUM(l.qty_remaining * v.chosen_unit_value) - SUM(l.qty_remaining * l.unit_cost), 2) as unrealized_gain_loss,
            CASE 
                WHEN SUM(l.qty_remaining * l.unit_cost) > 0 THEN 
                    ROUND((SUM(l.qty_remaining * v.chosen_unit_value) - SUM(l.qty_remaining * l.unit_cost)) / 
                          SUM(l.qty_remaining * l.unit_cost) * 100, 2)
                ELSE 0 
            END as gain_loss_percent
        FROM lot l
        LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
        WHERE l.qty_remaining > 0
    """
    result = execute_query_single(query)
    return result if result else {}


def get_gain_loss_by_year(year: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get realized gains/losses by year or for a specific year."""
    where_clause = "WHERE t.tx_type = 'SELL'"
    params = []
    
    if year:
        where_clause += " AND strftime('%Y', t.tx_date) = ?"
        params.append(str(year))
    
    query = f"""
        WITH sales_by_period AS (
            SELECT 
                strftime('%Y', t.tx_date) as year,
                strftime('%m', t.tx_date) as month,
                tl.id as sale_line_id,
                ABS(tl.quantity) as quantity_sold,
                tl.unit_price as sale_price,
                ABS(tl.quantity) * tl.unit_price as sale_proceeds
            FROM tx t
            JOIN tx_line tl ON tl.tx_id = t.id
            {where_clause}
        ),
        cost_basis AS (
            SELECT 
                ld.disposal_line_id,
                SUM(ld.quantity * l.unit_cost) as total_cost_basis
            FROM lot_disposal ld
            JOIN lot l ON l.id = ld.lot_id
            GROUP BY ld.disposal_line_id
        )
        SELECT 
            s.year,
            s.month,
            COUNT(DISTINCT s.sale_line_id) as sales,
            SUM(s.quantity_sold) as coins_sold,
            ROUND(SUM(s.sale_proceeds), 2) as proceeds,
            ROUND(SUM(cb.total_cost_basis), 2) as cost_basis,
            ROUND(SUM(s.sale_proceeds - COALESCE(cb.total_cost_basis, 0)), 2) as gain_loss
        FROM sales_by_period s
        LEFT JOIN cost_basis cb ON cb.disposal_line_id = s.sale_line_id
        GROUP BY s.year, s.month
        ORDER BY s.year, s.month
    """
    
    return execute_query_all(query, params)


# =============================================================================
# TAX REPORT LOGIC
# =============================================================================

def get_tax_year_summary(tax_year: int) -> Dict[str, Any]:
    """Get tax year summary for capital gains reporting."""
    query = """
        WITH sales AS (
            SELECT 
                t.tx_date,
                tl.id as sale_line_id,
                ct.id as coin_type_id,
                cm.series,
                ABS(tl.quantity) as quantity_sold,
                tl.unit_price as sale_price,
                ABS(tl.quantity) * tl.unit_price as sale_proceeds
            FROM tx t
            JOIN tx_line tl ON tl.tx_id = t.id
            JOIN coin_type ct ON ct.id = tl.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE t.tx_type = 'SELL' 
            AND strftime('%Y', t.tx_date) = ?
        ),
        cost_basis AS (
            SELECT 
                ld.disposal_line_id,
                MIN(l.acquired_date) as acquisition_date,
                SUM(ld.quantity * l.unit_cost) as total_cost_basis
            FROM lot_disposal ld
            JOIN lot l ON l.id = ld.lot_id
            GROUP BY ld.disposal_line_id
        ),
        categorized AS (
            SELECT 
                s.*,
                cb.acquisition_date,
                cb.total_cost_basis,
                s.sale_proceeds - COALESCE(cb.total_cost_basis, 0) as gain_loss,
                CASE 
                    WHEN julianday(s.tx_date) - julianday(cb.acquisition_date) > 365 THEN 'LONG_TERM'
                    ELSE 'SHORT_TERM'
                END as holding_period
            FROM sales s
            LEFT JOIN cost_basis cb ON cb.disposal_line_id = s.sale_line_id
        )
        SELECT 
            COUNT(DISTINCT sale_line_id) as total_sales,
            SUM(CASE WHEN holding_period = 'SHORT_TERM' THEN 1 ELSE 0 END) as short_term_sales,
            SUM(CASE WHEN holding_period = 'LONG_TERM' THEN 1 ELSE 0 END) as long_term_sales,
            ROUND(SUM(sale_proceeds), 2) as total_proceeds,
            ROUND(SUM(total_cost_basis), 2) as total_cost_basis,
            ROUND(SUM(CASE WHEN holding_period = 'SHORT_TERM' THEN gain_loss ELSE 0 END), 2) as short_term_gain_loss,
            ROUND(SUM(CASE WHEN holding_period = 'LONG_TERM' THEN gain_loss ELSE 0 END), 2) as long_term_gain_loss,
            ROUND(SUM(gain_loss), 2) as total_gain_loss
        FROM categorized
    """
    result = execute_query_single(query, (str(tax_year),))
    return result if result else {}


def get_tax_year_details(tax_year: int) -> List[Dict[str, Any]]:
    """Get detailed transaction list for tax reporting."""
    query = """
        WITH sales AS (
            SELECT 
                t.id as tx_id,
                t.tx_date as sale_date,
                p.name as buyer,
                tl.id as sale_line_id,
                cm.series,
                ct.year,
                ct.mint_mark,
                ct.variety,
                ABS(tl.quantity) as quantity_sold,
                tl.unit_price as sale_price,
                ABS(tl.quantity) * tl.unit_price as sale_proceeds
            FROM tx t
            JOIN tx_line tl ON tl.tx_id = t.id
            JOIN coin_type ct ON ct.id = tl.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            LEFT JOIN party p ON p.id = t.party_id
            WHERE t.tx_type = 'SELL' 
            AND strftime('%Y', t.tx_date) = ?
        ),
        cost_basis AS (
            SELECT 
                ld.disposal_line_id,
                MIN(l.acquired_date) as acquisition_date,
                SUM(ld.quantity * l.unit_cost) as total_cost_basis,
                STRING_AGG(DISTINCT t_buy.tx_date, ', ') as purchase_dates
            FROM lot_disposal ld
            JOIN lot l ON l.id = ld.lot_id
            JOIN tx_line tl_buy ON tl_buy.id = l.acquisition_line_id
            JOIN tx t_buy ON t_buy.id = tl_buy.tx_id
            GROUP BY ld.disposal_line_id
        )
        SELECT 
            s.sale_date,
            s.buyer,
            s.series || ' ' || s.year || 
                CASE WHEN s.mint_mark IS NOT NULL THEN ' ' || s.mint_mark ELSE '' END ||
                CASE WHEN s.variety IS NOT NULL THEN ' • ' || s.variety ELSE '' END as description,
            s.quantity_sold,
            ROUND(s.sale_price, 2) as sale_price,
            ROUND(s.sale_proceeds, 2) as proceeds,
            cb.acquisition_date,
            ROUND(cb.total_cost_basis, 2) as cost_basis,
            ROUND(s.sale_proceeds - COALESCE(cb.total_cost_basis, 0), 2) as gain_loss,
            CASE 
                WHEN julianday(s.sale_date) - julianday(cb.acquisition_date) > 365 THEN 'Long-term'
                ELSE 'Short-term'
            END as holding_period
        FROM sales s
        LEFT JOIN cost_basis cb ON cb.disposal_line_id = s.sale_line_id
        ORDER BY s.sale_date, s.series, s.year
    """
    return execute_query_all(query, (str(tax_year),))


# =============================================================================
# STORAGE REPORT LOGIC
# =============================================================================

def get_storage_summary() -> List[Dict[str, Any]]:
    """Get summary of all storage locations."""
    query = """
        SELECT 
            sl.id,
            sl.name,
            COALESCE(sl.category, 'Uncategorized') as category,
            sl.description,
            COUNT(DISTINCT l.id) as lots,
            COALESCE(SUM(l.qty_remaining), 0) as coins,
            ROUND(COALESCE(SUM(l.qty_remaining * l.unit_cost), 0), 2) as cost,
            ROUND(COALESCE(SUM(l.qty_remaining * v.chosen_unit_value), 0), 2) as value
        FROM storage_location sl
        LEFT JOIN lot l ON l.storage_location_id = sl.id AND l.qty_remaining > 0
        LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
        GROUP BY sl.id, sl.name, sl.category, sl.description
        ORDER BY sl.category, sl.name
    """
    return execute_query_all(query)


def get_unassigned_inventory_summary() -> Dict[str, Any]:
    """Get summary of inventory not assigned to any storage location."""
    query = """
        SELECT 
            COUNT(DISTINCT l.id) as lots,
            COALESCE(SUM(l.qty_remaining), 0) as coins,
            ROUND(COALESCE(SUM(l.qty_remaining * l.unit_cost), 0), 2) as cost,
            ROUND(COALESCE(SUM(l.qty_remaining * v.chosen_unit_value), 0), 2) as value
        FROM lot l
        LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
        WHERE l.storage_location_id IS NULL AND l.qty_remaining > 0
    """
    result = execute_query_single(query)
    return result if result else {}


def get_storage_details(storage_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get detailed inventory for a storage location or unassigned items."""
    if storage_id is None:
        where_clause = "WHERE l.storage_location_id IS NULL AND l.qty_remaining > 0"
        params = []
    else:
        where_clause = "WHERE l.storage_location_id = ? AND l.qty_remaining > 0"
        params = [storage_id]
    
    query = f"""
        SELECT 
            l.id as lot_id,
            cm.series,
            ct.year,
            ct.mint_mark,
            ct.variety,
            cm.metal,
            cm.asset_category,
            l.qty_remaining,
            COALESCE(l.estimated_grade_text, l.purchase_grade_text) as grade,
            l.slab_cert,
            ROUND(l.unit_cost, 2) as unit_cost,
            ROUND(v.chosen_unit_value, 2) as unit_value,
            ROUND(l.qty_remaining * l.unit_cost, 2) as total_cost,
            ROUND(l.qty_remaining * v.chosen_unit_value, 2) as total_value,
            l.acquired_date,
            p.name as acquired_from
        FROM lot l
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
        LEFT JOIN tx_line tl ON tl.id = l.acquisition_line_id
        LEFT JOIN tx t ON t.id = tl.tx_id
        LEFT JOIN party p ON p.id = t.party_id
        {where_clause}
        ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety
    """
    return execute_query_all(query, params)


# =============================================================================
# TYPE SET PROGRESS REPORT LOGIC
# =============================================================================

def get_type_set_definitions() -> List[Dict[str, Any]]:
    """Get available type set definitions."""
    # This would come from a type_set_definition table if implemented
    # For now, return predefined sets
    return [
        {"id": 1, "name": "US Type Set - Major Types", "description": "All major US coin types"},
        {"id": 2, "name": "Morgan Dollars - Complete", "description": "All Morgan Dollar dates and mints"},
        {"id": 3, "name": "Walking Liberty Halves", "description": "All Walking Liberty Half dates and mints"},
        {"id": 4, "name": "20th Century Type Set", "description": "One of each design from 1900-1999"},
    ]


def get_type_set_progress(set_name: str) -> Dict[str, Any]:
    """Get progress for a specific type set."""
    # This is a simplified example - would need actual type set definitions
    if set_name == "US Type Set - Major Types":
        query = """
            WITH required_types AS (
                SELECT DISTINCT series, 'Any' as year_required
                FROM coin_master
                WHERE country = 'USA'
            ),
            owned_types AS (
                SELECT DISTINCT cm.series
                FROM lot l
                JOIN coin_type ct ON ct.id = l.coin_type_id
                JOIN coin_master cm ON cm.id = ct.master_id
                WHERE l.qty_remaining > 0 AND cm.country = 'USA'
            )
            SELECT 
                (SELECT COUNT(*) FROM required_types) as total_required,
                (SELECT COUNT(*) FROM owned_types) as total_owned,
                ROUND(CAST((SELECT COUNT(*) FROM owned_types) AS FLOAT) / 
                      CAST((SELECT COUNT(*) FROM required_types) AS FLOAT) * 100, 1) as percent_complete
        """
    else:
        # Default query for undefined sets
        query = """
            SELECT 
                0 as total_required,
                0 as total_owned,
                0.0 as percent_complete
        """
    
    result = execute_query_single(query)
    return result if result else {}


def get_type_set_details(set_name: str) -> List[Dict[str, Any]]:
    """Get detailed list of coins needed and owned for a type set."""
    if set_name == "US Type Set - Major Types":
        query = """
            WITH all_series AS (
                SELECT DISTINCT series, metal, denomination
                FROM coin_master
                WHERE country = 'USA'
                ORDER BY denomination, series
            ),
            owned AS (
                SELECT 
                    cm.series,
                    MIN(ct.year) as earliest_year,
                    MAX(ct.year) as latest_year,
                    COUNT(DISTINCT l.id) as lots_owned,
                    SUM(l.qty_remaining) as total_coins,
                    MAX(COALESCE(l.estimated_grade_text, l.purchase_grade_text)) as best_grade
                FROM lot l
                JOIN coin_type ct ON ct.id = l.coin_type_id
                JOIN coin_master cm ON cm.id = ct.master_id
                WHERE l.qty_remaining > 0 AND cm.country = 'USA'
                GROUP BY cm.series
            )
            SELECT 
                a.series,
                a.metal,
                a.denomination,
                CASE WHEN o.series IS NOT NULL THEN 'Yes' ELSE 'No' END as owned,
                COALESCE(o.total_coins, 0) as quantity,
                o.best_grade,
                o.earliest_year || CASE WHEN o.latest_year != o.earliest_year 
                    THEN '-' || o.latest_year ELSE '' END as year_range
            FROM all_series a
            LEFT JOIN owned o ON o.series = a.series
            ORDER BY a.denomination, a.series
        """
        return execute_query_all(query)
    else:
        return []


# =============================================================================
# BULLION HOLDINGS REPORT LOGIC
# =============================================================================

def get_bullion_summary() -> Dict[str, Any]:
    """Get summary of all bullion holdings."""
    query = """
        SELECT 
            COUNT(DISTINCT l.id) as total_lots,
            SUM(l.qty_remaining) as total_coins,
            ROUND(SUM(l.qty_remaining * cm.weight_grams * COALESCE(cm.fineness, 0)) / 31.1035, 4) as total_fine_oz,
            ROUND(SUM(l.qty_remaining * l.unit_cost), 2) as total_cost,
            ROUND(SUM(l.qty_remaining * v.melt_unit_value), 2) as total_melt_value
        FROM lot l
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
        WHERE l.qty_remaining > 0 
        AND cm.asset_category IN ('BULLION', 'JUNK_SILVER')
    """
    result = execute_query_single(query)
    return result if result else {}


def get_bullion_by_metal() -> List[Dict[str, Any]]:
    """Get bullion holdings broken down by metal type."""
    query = """
        SELECT 
            cm.metal,
            cm.asset_category,
            COUNT(DISTINCT l.id) as lots,
            SUM(l.qty_remaining) as coins,
            ROUND(SUM(l.qty_remaining * cm.weight_grams) / 31.1035, 4) as gross_oz,
            ROUND(SUM(l.qty_remaining * cm.weight_grams * COALESCE(cm.fineness, 0)) / 31.1035, 4) as fine_oz,
            ROUND(SUM(l.qty_remaining * l.unit_cost), 2) as cost,
            ROUND(SUM(l.qty_remaining * v.melt_unit_value), 2) as melt_value,
            ROUND(SUM(l.qty_remaining * v.chosen_unit_value), 2) as market_value,
            ROUND(AVG(v.melt_unit_value / NULLIF(l.unit_cost, 0)), 4) as avg_premium
        FROM lot l
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
        WHERE l.qty_remaining > 0 
        AND cm.asset_category IN ('BULLION', 'JUNK_SILVER')
        GROUP BY cm.metal, cm.asset_category
        ORDER BY melt_value DESC
    """
    return execute_query_all(query)


def get_bullion_details() -> List[Dict[str, Any]]:
    """Get detailed list of all bullion holdings."""
    query = """
        SELECT 
            cm.series,
            ct.year,
            ct.mint_mark,
            cm.metal,
            cm.asset_category,
            l.qty_remaining,
            ROUND(cm.weight_grams / 31.1035, 4) as gross_oz_per_coin,
            ROUND(cm.weight_grams * COALESCE(cm.fineness, 0) / 31.1035, 4) as fine_oz_per_coin,
            ROUND(l.qty_remaining * cm.weight_grams * COALESCE(cm.fineness, 0) / 31.1035, 4) as total_fine_oz,
            ROUND(l.unit_cost, 2) as unit_cost,
            ROUND(v.melt_unit_value, 2) as melt_value_per_coin,
            ROUND(l.qty_remaining * v.melt_unit_value, 2) as total_melt_value,
            ROUND(v.melt_unit_value / NULLIF(l.unit_cost, 0) - 1, 4) as premium_to_spot,
            sl.name as storage_location
        FROM lot l
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
        LEFT JOIN storage_location sl ON sl.id = l.storage_location_id
        WHERE l.qty_remaining > 0 
        AND cm.asset_category IN ('BULLION', 'JUNK_SILVER')
        ORDER BY cm.metal DESC, total_melt_value DESC
    """
    return execute_query_all(query)


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
