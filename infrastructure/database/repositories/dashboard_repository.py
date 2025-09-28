# ========== dashboard_repository.py ==========
"""Dashboard data repository - Single Responsibility: Data access for dashboard"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class PortfolioSummary:
    """Data class for portfolio summary - more type-safe than dict"""
    total_lots: int
    total_coins: int
    total_cost_usd: float
    total_estimated_value_usd: float
    estimated_sale_proceeds: float


@dataclass
class MetalPrice:
    """Data class for metal prices"""
    metal: str
    price_per_oz_usd: float


@dataclass
class SeriesRollup:
    """Data class for series rollup data"""
    series: str
    coins: int
    melt_total_usd: float
    chosen_total_usd: float
    cost_total_usd: float


class DashboardDataRepository(ABC):
    """Abstract repository for dashboard data - Dependency Inversion"""

    @abstractmethod
    def get_portfolio_summary(self) -> PortfolioSummary:
        pass

    @abstractmethod
    def get_latest_metal_prices(self) -> List[MetalPrice]:
        pass

    @abstractmethod
    def get_series_rollup(self) -> List[SeriesRollup]:
        pass


class SQLDashboardRepository(DashboardDataRepository):
    """Concrete SQL implementation of dashboard repository"""

    def __init__(self, db_executor):
        """Inject database executor dependency"""
        self.db = db_executor

    def get_portfolio_summary(self) -> PortfolioSummary:
        """Get portfolio summary statistics using schema views."""
        # Main summary from view
        query = "SELECT total_estimated_value_usd, total_coins FROM v_portfolio_value_summary"
        result = self.db.execute_query_single(query)

        if not result:
            return PortfolioSummary(0, 0, 0.0, 0.0, 0.0)

        # Additional stats not in the view
        cost_query = """
            SELECT 
                COUNT(DISTINCT l.id) AS total_lots,
                ROUND(SUM(l.qty_remaining * l.unit_cost), 2) AS total_cost_usd
            FROM lot l
            WHERE l.qty_remaining > 0 AND l.status = 'OPEN'
        """
        cost_result = self.db.execute_query_single(cost_query)

        proceeds_query = "SELECT estimated_sale_proceeds FROM v_portfolio_sale_proceeds"
        proceeds_result = self.db.execute_query_single(proceeds_query)

        return PortfolioSummary(
            total_lots=cost_result['total_lots'] if cost_result else 0,
            total_coins=result['total_coins'] or 0,
            total_cost_usd=cost_result['total_cost_usd'] if cost_result else 0.0,
            total_estimated_value_usd=result['total_estimated_value_usd'] or 0.0,
            estimated_sale_proceeds=(proceeds_result['estimated_sale_proceeds']
                                     if proceeds_result and proceeds_result[
                'estimated_sale_proceeds']
                                     else 0.0)
        )

    def get_latest_metal_prices(self) -> List[MetalPrice]:
        """Get latest metal spot prices."""
        query = "SELECT metal, price_per_oz_usd FROM v_latest_spot ORDER BY metal"
        results = self.db.execute_query_all(query)
        return [MetalPrice(r['metal'], r['price_per_oz_usd']) for r in results] if results else []

    def get_series_rollup(self) -> List[SeriesRollup]:
        """Get series rollup data for dashboard using existing views."""
        query = """
            SELECT 
                lvd.series,
                SUM(lvd.qty_remaining) AS coins,
                ROUND(SUM(lvd.qty_remaining * lvd.melt_unit_value), 2) AS melt_total_usd,
                ROUND(SUM(lvd.qty_remaining * lvd.chosen_unit_value), 2) AS chosen_total_usd,
                ROUND(SUM(lvd.qty_remaining * l.unit_cost), 2) AS cost_total_usd
            FROM v_lot_value_details lvd
            JOIN lot l ON l.id = lvd.lot_id
            GROUP BY lvd.series
            HAVING SUM(lvd.qty_remaining) > 0
            ORDER BY lvd.series
        """
        results = self.db.execute_query_all(query)
        return [SeriesRollup(**r) for r in results] if results else []

    # Add these new methods to SQLDashboardRepository class

    def get_portfolio_composition(self) -> Dict[str, Any]:
        """Get portfolio composition data for charts."""
        query = """
            SELECT 
                CASE 
                    WHEN cm.asset_category IN ('ROUND', 'BAR', 'BULLION COIN') THEN 'Bullion'
                    WHEN l.valuation_method = 'MELT_ONLY' THEN 'Junk Silver'
                    ELSE 'Numismatic'
                END as category,
                ROUND(SUM(l.qty_remaining * lvd.chosen_unit_value), 2) as value
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            JOIN v_lot_value_details lvd ON lvd.lot_id = l.id
            WHERE l.qty_remaining > 0
            GROUP BY category
            HAVING value > 0
        """
        results = self.db.execute_query_all(query)
        return results if results else []

    def get_coins_by_metal(self) -> List[Dict]:
        """Get coin distribution by metal type."""
        query = """
            SELECT 
                COALESCE(cm.metal, 'Other') as metal,
                SUM(l.qty_remaining) as count,
                ROUND(SUM(l.qty_remaining * lvd.chosen_unit_value), 2) as value
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            JOIN v_lot_value_details lvd ON lvd.lot_id = l.id
            WHERE l.qty_remaining > 0
            GROUP BY cm.metal
            ORDER BY value DESC
        """
        results = self.db.execute_query_all(query)
        return results if results else []

    def get_top_series_by_value(self, limit: int = 10) -> List[Dict]:
        """Get top coin series by total value."""
        query = """
            SELECT 
                cm.series,
                SUM(l.qty_remaining) as coins,
                ROUND(SUM(l.qty_remaining * lvd.chosen_unit_value), 2) as total_value
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            JOIN v_lot_value_details lvd ON lvd.lot_id = l.id
            WHERE l.qty_remaining > 0
            GROUP BY cm.series
            ORDER BY total_value DESC
            LIMIT ?
        """
        results = self.db.execute_query_all(query, (limit,))
        return results if results else []

    def get_value_vs_cost_by_series(self) -> List[Dict]:
        """Get value vs cost comparison by series."""
        query = """
            SELECT 
                cm.series,
                ROUND(SUM(l.qty_remaining * l.unit_cost), 2) as total_cost,
                ROUND(SUM(l.qty_remaining * lvd.chosen_unit_value), 2) as total_value
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            JOIN v_lot_value_details lvd ON lvd.lot_id = l.id
            WHERE l.qty_remaining > 0
            GROUP BY cm.series
            HAVING total_cost > 0
            ORDER BY total_value DESC
            LIMIT 15
        """
        results = self.db.execute_query_all(query)
        return results if results else []

    def get_country_distribution(self) -> List[Dict]:
        """Get distribution of coins by country."""
        query = """
            SELECT 
                cm.country,
                COUNT(DISTINCT ct.id) as types,
                SUM(l.qty_remaining) as coins,
                ROUND(SUM(l.qty_remaining * lvd.chosen_unit_value), 2) as value
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            JOIN v_lot_value_details lvd ON lvd.lot_id = l.id
            WHERE l.qty_remaining > 0
            GROUP BY cm.country
            HAVING coins > 0
            ORDER BY value DESC
        """
        results = self.db.execute_query_all(query)
        return results if results else []
