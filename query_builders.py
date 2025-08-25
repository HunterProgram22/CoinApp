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
        """Common table expression for melt values."""
        return """
            WITH melt AS (
                SELECT metal, price_per_oz_usd FROM v_latest_spot
            )
        """
    
    @staticmethod
    def melt_calculation_fields() -> str:
        """Standard melt calculation fields."""
        return """
            ROUND(
                (cm.weight_grams * COALESCE(cm.fineness,0)) / 31.1034768
                * (SELECT price_per_oz_usd FROM melt WHERE metal = cm.metal),
            2) AS melt_unit_usd,
            ROUND(
                l.qty_remaining * (cm.weight_grams * COALESCE(cm.fineness,0)) / 31.1034768
                * (SELECT price_per_oz_usd FROM melt WHERE metal = cm.metal),
            2) AS melt_total_usd
        """
    
    @staticmethod
    def standard_lot_fields() -> str:
        """Standard fields for lot detail queries."""
        return """
            l.acquired_date,
            cm.series,
            ct.year,
            ct.mint_mark,
            COALESCE(ct.variety,'') AS variety,
            l.qty_remaining,
            COALESCE(p.name,'') AS party,
            ROUND(l.unit_cost, 2) AS unit_cost_usd,
            COALESCE(l.estimated_grade_text, l.purchase_grade_text) AS grade
        """
    
    @staticmethod
    def standard_order_by() -> str:
        """Standard ordering for inventory queries."""
        return "ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety, l.acquired_date"


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
                SELECT lot_id, GROUP_CONCAT(specimen_code, ', ') AS flip_ids, COUNT(*) AS flip_count
                FROM specimen
                WHERE sold_line_id IS NULL
                GROUP BY lot_id
            ) sp ON sp.lot_id = l.id
        """
    
    @staticmethod
    def specimen_select_field(has_specimen: bool, has_specimen_code: bool) -> str:
        """Get specimen field for SELECT clause."""
        return ", sp.flip_ids" if (has_specimen and has_specimen_code) else ""


# SQL Templates
class SQLTemplates:
    """Common SQL query templates."""
    
    TRANSACTION_SEARCH = """
        SELECT
            t.id, t.tx_date, t.tx_type,
            p.name AS party,
            t.currency, t.shipping, t.tax, t.fees, t.notes
        FROM tx t
        LEFT JOIN party p ON p.id = t.party_id
        {where_clause}
        ORDER BY t.tx_date DESC, t.id DESC
        LIMIT ? OFFSET ?
    """
    
    TX_LINES = """
        SELECT
            tl.id AS line_id,
            cm.series, ct.year, ct.mint_mark, COALESCE(ct.variety,'') AS variety,
            ABS(tl.quantity) AS quantity, tl.unit_price,
            tl.grade_company, tl.grade_text, tl.numeric_grade, tl.slab_cert
        FROM tx_line tl
        LEFT JOIN coin_type ct ON ct.id = tl.coin_type_id
        LEFT JOIN coin_master cm ON cm.id = ct.master_id
        WHERE tl.tx_id = ?
        ORDER BY tl.id
    """
    
    SPENDING_LOG = """
        WITH buys AS (
            SELECT t.id, t.tx_date, COALESCE(p.name,'') AS party,
                   COALESCE(t.shipping,0) AS shipping, COALESCE(t.tax,0) AS tax, COALESCE(t.fees,0) AS fees
            FROM tx t
            LEFT JOIN party p ON p.id = t.party_id
            {where_clause}
        ),
        line_sub AS (
            SELECT tl.tx_id, SUM(ABS(tl.quantity) * COALESCE(tl.unit_price,0)) AS line_subtotal
            FROM tx_line tl
            JOIN tx t2 ON t2.id = tl.tx_id AND t2.tx_type = 'BUY'
            GROUP BY tl.tx_id
        )
        SELECT b.tx_date, b.party,
               ROUND(SUM(COALESCE(ls.line_subtotal,0) + b.shipping + b.tax + b.fees), 2) AS spent_usd
        FROM buys b
        LEFT JOIN line_sub ls ON ls.tx_id = b.id
        GROUP BY b.tx_date, b.party
        ORDER BY b.tx_date DESC, b.party
        LIMIT ? OFFSET ?
    """
