# infrastructure/database/repositories/world_coins_repository.py
"""World Coins data repository - Single Responsibility: Data access for world coins"""
from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class WorldCoinFilters:
    """Data class for world coin filtering options"""
    want_proofs: bool = False
    want_slabbed: bool = False
    asset_category: Optional[str] = None


@dataclass
class WorldCoinSummary:
    """Data class for world coins summary by series"""
    series: str
    coins: int
    melt_value_usd: Optional[float]
    est_value_usd: Optional[float]


@dataclass
class WorldCoinDetail:
    """Data class for detailed world coins data"""
    lot_id: int
    series: str
    year: int
    mint_mark: str
    variety: str
    acquired: str
    party: str
    qty: int
    unit_cost_usd: float
    melt_unit_value: Optional[float]
    chosen_unit_value: Optional[float]
    lot_est_value: Optional[float]
    grade: str
    flip_ids: str
    cert_number: str


class WorldCoinsDataRepository(ABC):
    """Abstract repository for world coins data - Dependency Inversion"""

    @abstractmethod
    def get_countries_with_world_coins(self) -> List[str]:
        pass

    @abstractmethod
    def check_asset_category_support(self) -> bool:
        pass

    @abstractmethod
    def get_world_coins_summary(self, country: str, filters: WorldCoinFilters) -> List[
        WorldCoinSummary]:
        pass

    @abstractmethod
    def get_world_coins_detail(self, country: str, filters: WorldCoinFilters) -> List[
        WorldCoinDetail]:
        pass


class SQLWorldCoinsRepository(WorldCoinsDataRepository):
    """Concrete SQL implementation of world coins repository"""

    def __init__(self, db_executor):
        """Inject database executor dependency"""
        self.db = db_executor

    def get_countries_with_world_coins(self) -> List[str]:
        """Get list of countries with inventory on hand."""
        query = """
            SELECT DISTINCT COALESCE(cm.country, '') AS country
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE l.qty_remaining > 0 AND COALESCE(cm.country, '') <> ''
            ORDER BY country
        """
        results = self.db.execute_query_all(query)
        return [r["country"] for r in results]

    def check_asset_category_support(self) -> bool:
        """Check if coin_master table has asset_category column."""
        try:
            result = self.db.execute_query_single(
                "SELECT 1 FROM pragma_table_info('coin_master') WHERE name='asset_category'"
            )
            return bool(result)
        except Exception:
            return False

    def get_world_coins_summary(self, country: str, filters: WorldCoinFilters) -> List[
        WorldCoinSummary]:
        """Get summary data for world coins by series."""
        where_conditions = ["cm.country = ?", "l.qty_remaining > 0"]
        params = [country]

        if filters.want_proofs:
            where_conditions.append("ct.is_proof = 1")

        if filters.want_slabbed:
            where_conditions.append(
                "(COALESCE(l.slab_cert, '') <> '' OR "
                "UPPER(COALESCE(l.purchase_grade_company, '')) IN ('PCGS','NGC','ANACS','ICG'))"
            )

        if filters.asset_category and filters.asset_category != "All":
            where_conditions.append("cm.asset_category = ?")
            params.append(filters.asset_category)

        where_clause = " AND ".join(where_conditions)

        # Check if v_lot_value_details view exists
        view_check = self.db.execute_query_single(
            "SELECT 1 FROM sqlite_master WHERE type='view' AND name='v_lot_value_details'"
        )

        if view_check:
            query = f"""
                SELECT
                    cm.series AS Series,
                    SUM(v.qty_remaining) AS Coins,
                    ROUND(SUM(v.qty_remaining * COALESCE(v.melt_unit_value, 0)), 2) AS "Melt Value (USD)",
                    ROUND(SUM(v.qty_remaining * COALESCE(v.chosen_unit_value, 0)), 2) AS "Est. Value (USD)"
                FROM v_lot_value_details v
                JOIN lot l ON l.id = v.lot_id
                JOIN coin_type ct ON ct.id = l.coin_type_id
                JOIN coin_master cm ON cm.id = ct.master_id
                WHERE {where_clause}
                GROUP BY cm.series
                ORDER BY "Est. Value (USD)" DESC, cm.series
            """
        else:
            # Fallback without valuation view
            query = f"""
                SELECT
                    cm.series AS Series,
                    SUM(l.qty_remaining) AS Coins,
                    NULL AS "Melt Value (USD)",
                    NULL AS "Est. Value (USD)"
                FROM lot l
                JOIN coin_type ct ON ct.id = l.coin_type_id
                JOIN coin_master cm ON cm.id = ct.master_id
                WHERE {where_clause}
                GROUP BY cm.series
                ORDER BY Coins DESC, cm.series
            """

        results = self.db.execute_query_all(query, params)

        # Convert to dataclass instances using CORRECT column names
        return [WorldCoinSummary(
            series=r.get('Series', ''),
            coins=r.get('Coins', 0),
            melt_value_usd=r.get('Melt Value (USD)'),
            est_value_usd=r.get('Est. Value (USD)')
        ) for r in results]

    def get_world_coins_detail(self, country: str, filters: WorldCoinFilters) -> List[
        WorldCoinDetail]:
        """Get detailed data for world coins."""
        where_conditions = ["cm.country = ?", "l.qty_remaining > 0"]
        params = [country]

        if filters.want_proofs:
            where_conditions.append("ct.is_proof = 1")

        if filters.want_slabbed:
            where_conditions.append(
                "(COALESCE(l.slab_cert, '') <> '' OR "
                "UPPER(COALESCE(l.purchase_grade_company, '')) IN ('PCGS','NGC','ANACS','ICG'))"
            )

        if filters.asset_category and filters.asset_category != "All":
            where_conditions.append("cm.asset_category = ?")
            params.append(filters.asset_category)

        where_clause = " AND ".join(where_conditions)

        # Check for specimen table and features
        specimen_check = self.db.execute_query_single(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='specimen'"
        )

        flip_cte = ""
        flip_join = ""
        flip_select = "'' AS [Flip IDs],"

        if specimen_check:
            code_check = self.db.execute_query_single(
                "SELECT 1 FROM pragma_table_info('specimen') WHERE name='specimen_code'"
            )

            if code_check:
                sold_check = self.db.execute_query_single(
                    "SELECT 1 FROM pragma_table_info('specimen') WHERE name='sold_line_id'"
                )

                where_unsold = " WHERE sold_line_id IS NULL" if sold_check else ""
                flip_cte = f"""
                    WITH flip AS (
                        SELECT lot_id, GROUP_CONCAT(specimen_code, ', ') AS flip_ids
                        FROM specimen{where_unsold}
                        GROUP BY lot_id
                    )
                """
                flip_join = "LEFT JOIN flip f ON f.lot_id = l.id"
                flip_select = "COALESCE(f.flip_ids, '') AS [Flip IDs],"

        # Check if v_lot_value_details view exists
        view_check = self.db.execute_query_single(
            "SELECT 1 FROM sqlite_master WHERE type='view' AND name='v_lot_value_details'"
        )

        if view_check:
            value_columns = """
                ROUND(v.melt_unit_value, 4) AS [Melt Unit Value],
                ROUND(v.chosen_unit_value, 2) AS [Chosen Unit Value],
                ROUND(l.qty_remaining * COALESCE(v.chosen_unit_value, 0), 2) AS [Lot Est. Value],
            """
            value_join = "LEFT JOIN v_lot_value_details v ON v.lot_id = l.id"
        else:
            value_columns = """
                NULL AS [Melt Unit Value],
                NULL AS [Chosen Unit Value], 
                NULL AS [Lot Est. Value],
            """
            value_join = ""

        query = f"""
            {flip_cte}
            SELECT
                cm.series AS Series,
                ct.year AS Year,
                ct.mint_mark AS [Mint Mark],
                COALESCE(ct.variety, '') AS Variety,
                l.id AS lot_id,
                t.tx_date AS Acquired,
                COALESCE(p.name, '') AS Party,
                l.qty_remaining AS Qty,
                ROUND(l.unit_cost, 2) AS [Unit Cost (USD)],
                {value_columns}
                COALESCE(l.estimated_grade_text, l.purchase_grade_text, '') AS Grade,
                {flip_select}
                COALESCE(l.slab_cert, '') AS [Cert #]
            FROM lot l
            JOIN tx_line tl ON tl.id = l.acquisition_line_id
            JOIN tx t ON t.id = tl.tx_id
            LEFT JOIN party p ON p.id = t.party_id
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            {value_join}
            {flip_join}
            WHERE {where_clause}
            ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety, l.id
        """

        results = self.db.execute_query_all(query, params)

        # Convert to dataclass instances using CORRECT column names
        return [WorldCoinDetail(
            lot_id=r.get('lot_id', 0),
            series=r.get('Series', ''),
            year=r.get('Year', 0),
            mint_mark=r.get('Mint Mark', ''),
            variety=r.get('Variety', ''),
            acquired=r.get('Acquired', ''),
            party=r.get('Party', ''),
            qty=r.get('Qty', 0),
            unit_cost_usd=r.get('Unit Cost (USD)', 0.0),
            melt_unit_value=r.get('Melt Unit Value'),
            chosen_unit_value=r.get('Chosen Unit Value'),
            lot_est_value=r.get('Lot Est. Value'),
            grade=r.get('Grade', ''),
            flip_ids=r.get('Flip IDs', ''),
            cert_number=r.get('Cert #', '')
        ) for r in results]
