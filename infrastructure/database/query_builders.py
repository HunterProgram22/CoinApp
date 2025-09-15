# query_builders.py
"""SQL query building utilities to eliminate repetitive SQL construction."""

from typing import List, Optional, Tuple, Dict, Any


class WhereClauseBuilder:
    """Helper for building WHERE clauses dynamically."""
    
    def __init__(self):
        self.conditions = []
        self.params = []
    
    def add_condition(self, condition: str, *params):
        """Add a WHERE condition with parameters."""
        self.conditions.append(condition)
        self.params.extend(params)
        return self
    
    def add_date_range(self, date_from: Optional[str], date_to: Optional[str], date_field: str = "tx_date"):
        """Add date range conditions."""
        if date_from:
            self.add_condition(f"t.{date_field} >= ?", date_from)
        if date_to:
            self.add_condition(f"t.{date_field} <= ?", date_to)
        return self
    
    def add_in_clause(self, field: str, values: Optional[List[Any]]):
        """Add IN clause for multiple values."""
        if values:
            placeholders = ",".join(["?"] * len(values))
            self.add_condition(f"{field} IN ({placeholders})", *values)
        return self
    
    def add_like_clause(self, field: str, value: Optional[str], nullable: bool = True):
        """Add LIKE clause for text search."""
        if value:
            field_expr = f"COALESCE({field}, '')" if nullable else field
            self.add_condition(f"{field_expr} LIKE ?", f"%{value}%")
        return self
    
    def add_numeric_range(self, field: str, min_val: Optional[float], max_val: Optional[float]):
        """Add numeric range conditions."""
        if min_val is not None:
            self.add_condition(f"{field} >= ?", min_val)
        if max_val is not None:
            self.add_condition(f"{field} <= ?", max_val)
        return self
    
    def add_not_null(self, field: str):
        """Add NOT NULL condition."""
        self.add_condition(f"{field} IS NOT NULL")
        return self
    
    def build(self) -> Tuple[str, List[Any]]:
        """Build the WHERE clause and return (where_sql, params)."""
        if not self.conditions:
            return "", self.params
        
        where_sql = "WHERE " + " AND ".join(self.conditions)
        return where_sql, self.params


class InventoryQueryBuilder:
    """Builder for common inventory query patterns."""
    
    @staticmethod
    def base_lot_query() -> str:
        """Base query for lot details with common joins."""
        return """
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            JOIN tx_line tl ON tl.id = l.acquisition_line_id
            JOIN tx t ON t.id = tl.tx_id
            LEFT JOIN party p ON p.id = t.party_id
        """
    
    @staticmethod
    def melt_value_cte() -> str:
        """Common table expression for melt values using schema view."""
        return """
            WITH melt AS (
                SELECT metal, price_per_oz_usd FROM v_latest_spot
            )
        """
    
    @staticmethod
    def melt_calculation_fields() -> str:
        """Standard melt calculation fields with better precision."""
        return """
            ROUND(
                (cm.weight_grams * COALESCE(cm.fineness, 0.0)) / 31.1034768
                * COALESCE((SELECT price_per_oz_usd FROM melt WHERE metal = cm.metal), 0.0),
            4) AS melt_unit_usd,
            ROUND(
                l.qty_remaining * (cm.weight_grams * COALESCE(cm.fineness, 0.0)) / 31.1034768
                * COALESCE((SELECT price_per_oz_usd FROM melt WHERE metal = cm.metal), 0.0),
            2) AS melt_total_usd
        """
    
    @staticmethod
    def numismatic_calculation_fields() -> str:
        """Standard numismatic value calculation fields using schema views."""
        return """
            COALESCE(
                CASE l.valuation_method
                    WHEN 'MANUAL' THEN l.manual_est_unit_value
                    WHEN 'GUIDE_ONLY' THEN (
                        SELECT g.price_usd FROM v_latest_guide g 
                        WHERE g.coin_type_id = l.coin_type_id 
                        AND g.grade_text = COALESCE(l.estimated_grade_text, l.purchase_grade_text)
                    )
                    WHEN 'MELT_ONLY' THEN (
                        (cm.weight_grams * COALESCE(cm.fineness, 0.0)) / 31.1034768
                        * COALESCE((SELECT price_per_oz_usd FROM v_latest_spot WHERE metal = cm.metal), 0.0)
                    )
                    ELSE COALESCE(
                        (SELECT g.price_usd FROM v_latest_guide g 
                         WHERE g.coin_type_id = l.coin_type_id 
                         AND g.grade_text = COALESCE(l.estimated_grade_text, l.purchase_grade_text)),
                        (cm.weight_grams * COALESCE(cm.fineness, 0.0)) / 31.1034768
                        * COALESCE((SELECT price_per_oz_usd FROM v_latest_spot WHERE metal = cm.metal), 0.0),
                        NULLIF(l.manual_est_unit_value, 0),
                        NULLIF(l.unit_cost, 0),
                        0.0
                    )
                END,
                0.0
            ) AS numi_unit_usd
        """
    
    @staticmethod
    def standard_lot_fields() -> str:
        """Standard fields for lot detail queries."""
        return """
            l.id AS lot_id,
            l.acquired_date,
            cm.series,
            ct.year,
            ct.mint_mark,
            COALESCE(ct.variety, '') AS variety,
            l.qty_remaining,
            COALESCE(p.name, '') AS party,
            ROUND(l.unit_cost, 2) AS unit_cost_usd,
            COALESCE(l.estimated_grade_text, l.purchase_grade_text, '') AS grade,
            l.valuation_method,
            l.status
        """
    
    @staticmethod
    def standard_order_by() -> str:
        """Standard ordering for inventory queries."""
        return "ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety, l.acquired_date"
    
    @staticmethod
    def build_series_rollup_query(where_clause: str = "") -> str:
        """Build series rollup query for dashboard using schema views."""
        return f"""
            SELECT 
                lvd.series,
                SUM(lvd.qty_remaining) AS coins,
                ROUND(SUM(lvd.qty_remaining * lvd.melt_unit_value), 2) AS melt_total_usd,
                ROUND(SUM(lvd.qty_remaining * lvd.chosen_unit_value), 2) AS chosen_total_usd,
                ROUND(SUM(lvd.qty_remaining * l.unit_cost), 2) AS cost_total_usd
            FROM v_lot_value_details lvd
            JOIN lot l ON l.id = lvd.lot_id
            {where_clause}
            GROUP BY lvd.series
            HAVING SUM(lvd.qty_remaining) > 0
            ORDER BY lvd.series
        """


class SpecimenQueryHelper:
    """Helper for specimen/flip ID related queries."""
    
    @staticmethod
    def detect_specimen_table(connection) -> Tuple[bool, bool]:
        """Detect if specimen table exists and has specimen_code column."""
        has_specimen = bool(connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='specimen'"
        ).fetchone())
        
        has_specimen_code = False
        if has_specimen:
            try:
                connection.execute("SELECT specimen_code FROM specimen LIMIT 1")
                has_specimen_code = True
            except Exception:
                has_specimen_code = False
        
        return has_specimen, has_specimen_code
    
    @staticmethod
    def specimen_join_clause(has_specimen: bool, has_specimen_code: bool) -> str:
        """Get specimen JOIN clause if available."""
        if not (has_specimen and has_specimen_code):
            return ""
        
        return """
            LEFT JOIN (
                SELECT lot_id, 
                       GROUP_CONCAT(specimen_code, ', ') AS flip_ids, 
                       COUNT(*) AS flip_count
                FROM specimen
                WHERE sold_line_id IS NULL
                GROUP BY lot_id
            ) sp ON sp.lot_id = l.id
        """
    
    @staticmethod
    def specimen_select_field(has_specimen: bool, has_specimen_code: bool) -> str:
        """Get specimen field for SELECT clause."""
        return ", COALESCE(sp.flip_ids, '') AS flip_ids" if (has_specimen and has_specimen_code) else ", '' AS flip_ids"


class TransactionQueryBuilder:
    """Builder for transaction-related queries."""
    
    @staticmethod
    def build_transaction_summary(tx_id: int) -> str:
        """Build transaction summary query."""
        return """
            SELECT 
                t.tx_date, t.tx_type, t.currency,
                COALESCE(p.name, '') AS party,
                COALESCE(t.shipping, 0.0) AS shipping,
                COALESCE(t.tax, 0.0) AS tax,
                COALESCE(t.fees, 0.0) AS fees,
                t.notes,
                COUNT(tl.id) AS line_count,
                SUM(ABS(tl.quantity) * COALESCE(tl.unit_price, 0.0)) AS subtotal
            FROM tx t
            LEFT JOIN party p ON p.id = t.party_id
            LEFT JOIN tx_line tl ON tl.tx_id = t.id
            WHERE t.id = ?
            GROUP BY t.id
        """
    
    @staticmethod
    def build_fifo_availability_check(coin_type_id: int) -> str:
        """Build query to check FIFO lot availability."""
        return """
            SELECT 
                l.id AS lot_id,
                l.qty_remaining,
                l.unit_cost,
                l.acquired_date
            FROM lot l
            WHERE l.coin_type_id = ? 
              AND l.qty_remaining > 0 
              AND l.status = 'OPEN'
            ORDER BY l.acquired_date ASC, l.id ASC
        """


# SQL Templates
class SQLTemplates:
    """Common SQL query templates optimized for SQLite."""
    
    TRANSACTION_SEARCH = """
        SELECT
            t.id, t.tx_date, t.tx_type,
            COALESCE(p.name, '') AS party,
            t.currency, 
            COALESCE(t.shipping, 0.0) AS shipping, 
            COALESCE(t.tax, 0.0) AS tax, 
            COALESCE(t.fees, 0.0) AS fees, 
            COALESCE(t.notes, '') AS notes
        FROM tx t
        LEFT JOIN party p ON p.id = t.party_id
        {where_clause}
        ORDER BY t.tx_date DESC, t.id DESC
        LIMIT ? OFFSET ?
    """
    
    TX_LINES = """
        SELECT
            tl.id AS line_id,
            cm.series, 
            COALESCE(ct.year, 0) AS year, 
            COALESCE(ct.mint_mark, '') AS mint_mark, 
            COALESCE(ct.variety, '') AS variety,
            ABS(tl.quantity) AS quantity, 
            COALESCE(tl.unit_price, 0.0) AS unit_price,
            COALESCE(tl.grade_company, '') AS grade_company, 
            COALESCE(tl.grade_text, '') AS grade_text, 
            COALESCE(tl.numeric_grade, 0) AS numeric_grade, 
            COALESCE(tl.slab_cert, '') AS slab_cert
        FROM tx_line tl
        LEFT JOIN coin_type ct ON ct.id = tl.coin_type_id
        LEFT JOIN coin_master cm ON cm.id = ct.master_id
        WHERE tl.tx_id = ?
        ORDER BY tl.id
    """
    
    SPENDING_LOG = """
        WITH buys AS (
            SELECT t.id, t.tx_date, 
                   COALESCE(p.name, '') AS party,
                   COALESCE(t.shipping, 0.0) AS shipping, 
                   COALESCE(t.tax, 0.0) AS tax, 
                   COALESCE(t.fees, 0.0) AS fees
            FROM tx t
            LEFT JOIN party p ON p.id = t.party_id
            WHERE t.tx_type = 'BUY'
            {where_clause}
        ),
        line_sub AS (
            SELECT tl.tx_id, 
                   SUM(ABS(tl.quantity) * COALESCE(tl.unit_price, 0.0)) AS line_subtotal
            FROM tx_line tl
            JOIN buys b ON b.id = tl.tx_id
            GROUP BY tl.tx_id
        )
        SELECT b.tx_date, b.party,
               ROUND(COALESCE(ls.line_subtotal, 0.0) + b.shipping + b.tax + b.fees, 2) AS spent_usd
        FROM buys b
        LEFT JOIN line_sub ls ON ls.tx_id = b.id
        ORDER BY b.tx_date DESC, b.party
        LIMIT ? OFFSET ?
    """
    
    INVENTORY_SUMMARY = """
        SELECT 
            cm.metal,
            COUNT(DISTINCT l.id) AS lot_count,
            SUM(l.qty_remaining) AS total_coins,
            ROUND(SUM(l.qty_remaining * l.unit_cost), 2) AS total_cost_usd,
            ROUND(SUM(
                l.qty_remaining * (cm.weight_grams * COALESCE(cm.fineness, 0.0)) / 31.1034768
                * COALESCE((SELECT price_per_oz_usd FROM v_latest_spot WHERE metal = cm.metal), 0.0)
            ), 2) AS total_melt_usd
        FROM lot l
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        WHERE l.qty_remaining > 0 AND l.status = 'OPEN'
        GROUP BY cm.metal
        ORDER BY cm.metal
    """