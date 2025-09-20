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
