# infrastructure/database/repositories/series_analysis_repository.py
"""Series Analysis data repository - Single Responsibility: Data access for series analysis"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class SeriesMetrics:
    """Core metrics for a series"""
    series: str
    total_coins: int
    total_lots: int
    total_cost_usd: float
    total_melt_value_usd: float
    total_est_value_usd: float
    gain_loss_usd: float
    gain_loss_pct: float
    avg_grade: Optional[float]
    min_grade: Optional[float]
    max_grade: Optional[float]
    earliest_acquisition: Optional[str]
    latest_acquisition: Optional[str]


@dataclass
class GradeDistribution:
    """Grade distribution for a series"""
    grade_text: str
    numeric_grade: Optional[float]
    count: int


@dataclass
class SellerBreakdown:
    """Seller breakdown for a series"""
    seller: str
    coins_purchased: int
    total_spent_usd: float
    avg_cost_per_coin: float


@dataclass
class LocationBreakdown:
    """Location breakdown for a series"""
    location: str
    coins_stored: int
    total_value_usd: float


@dataclass
class TypeBreakdown:
    """Breakdown by coin type (year/mint/variety)"""
    year: Optional[int]
    mint_mark: Optional[str]
    variety: Optional[str]
    quantity: int
    avg_cost: float
    total_cost: float
    total_value: float


@dataclass
class AcquisitionTimeline:
    """Timeline of acquisitions"""
    acquisition_date: str
    coins_acquired: int
    total_spent: float


class SeriesAnalysisDataRepository(ABC):
    """Abstract repository for series analysis data - Dependency Inversion"""

    @abstractmethod
    def get_all_countries(self) -> List[str]:
        """Get list of all countries with inventory"""
        pass

    @abstractmethod
    def get_series_by_country(self, country: str) -> List[str]:
        """Get list of series for a specific country"""
        pass

    @abstractmethod
    def get_series_metrics(self, series: str) -> Optional[SeriesMetrics]:
        """Get core metrics for a series"""
        pass

    @abstractmethod
    def get_grade_distribution(self, series: str) -> List[GradeDistribution]:
        """Get grade distribution for a series"""
        pass

    @abstractmethod
    def get_seller_breakdown(self, series: str) -> List[SellerBreakdown]:
        """Get seller breakdown for a series"""
        pass

    @abstractmethod
    def get_location_breakdown(self, series: str) -> List[LocationBreakdown]:
        """Get location breakdown for a series"""
        pass

    @abstractmethod
    def get_type_breakdown(self, series: str) -> List[TypeBreakdown]:
        """Get breakdown by coin type"""
        pass

    @abstractmethod
    def get_acquisition_timeline(self, series: str) -> List[AcquisitionTimeline]:
        """Get acquisition timeline for a series"""
        pass

    @abstractmethod
    def get_series_notes(self, series: str) -> List[Dict[str, Any]]:
        """Get notes for coins in a series"""
        pass


class SQLSeriesAnalysisRepository(SeriesAnalysisDataRepository):
    """Concrete SQL implementation of series analysis repository"""

    def __init__(self, db_executor):
        """Inject database executor dependency"""
        self.db = db_executor

    def get_all_countries(self) -> List[str]:
        """Get list of all countries with inventory"""
        query = """
            SELECT DISTINCT cm.country
            FROM coin_master cm
            JOIN coin_type ct ON ct.master_id = cm.id
            JOIN lot l ON l.coin_type_id = ct.id
            WHERE l.qty_remaining > 0 AND cm.country IS NOT NULL AND TRIM(cm.country) != ''
            ORDER BY cm.country
        """
        results = self.db.execute_query_all(query)
        return [r['country'] for r in results] if results else []

    def get_series_by_country(self, country: str) -> List[str]:
        """Get list of series for a specific country"""
        query = """
            SELECT DISTINCT cm.series
            FROM coin_master cm
            JOIN coin_type ct ON ct.master_id = cm.id
            JOIN lot l ON l.coin_type_id = ct.id
            WHERE l.qty_remaining > 0 AND cm.country = ?
            ORDER BY cm.series
        """
        results = self.db.execute_query_all(query, (country,))
        return [r['series'] for r in results] if results else []

    def get_series_metrics(self, series: str) -> Optional[SeriesMetrics]:
        """Get core metrics for a series"""
        query = """
            SELECT 
                cm.series,
                COUNT(DISTINCT l.id) as total_lots,
                SUM(l.qty_remaining) as total_coins,
                ROUND(SUM(l.qty_remaining * l.unit_cost), 2) as total_cost_usd,
                ROUND(SUM(l.qty_remaining * lvd.melt_unit_value), 2) as total_melt_value_usd,
                ROUND(SUM(l.qty_remaining * lvd.chosen_unit_value), 2) as total_est_value_usd,
                ROUND(
                    SUM(l.qty_remaining * lvd.chosen_unit_value) - 
                    SUM(l.qty_remaining * l.unit_cost), 2
                ) as gain_loss_usd,
                ROUND(
                    (SUM(l.qty_remaining * lvd.chosen_unit_value) - 
                     SUM(l.qty_remaining * l.unit_cost)) / 
                    NULLIF(SUM(l.qty_remaining * l.unit_cost), 0) * 100, 2
                ) as gain_loss_pct,
                AVG(COALESCE(l.estimated_numeric_grade, l.purchase_numeric_grade)) as avg_grade,
                MIN(COALESCE(l.estimated_numeric_grade, l.purchase_numeric_grade)) as min_grade,
                MAX(COALESCE(l.estimated_numeric_grade, l.purchase_numeric_grade)) as max_grade,
                MIN(l.acquired_date) as earliest_acquisition,
                MAX(l.acquired_date) as latest_acquisition
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            JOIN v_lot_value_details lvd ON lvd.lot_id = l.id
            WHERE l.qty_remaining > 0 AND cm.series = ?
            GROUP BY cm.series
        """
        result = self.db.execute_query_single(query, (series,))
        return SeriesMetrics(**result) if result else None

    def get_grade_distribution(self, series: str) -> List[GradeDistribution]:
        """Get grade distribution for a series"""
        query = """
            SELECT 
                COALESCE(l.estimated_grade_text, l.purchase_grade_text) as grade_text,
                COALESCE(l.estimated_numeric_grade, l.purchase_numeric_grade) as numeric_grade,
                SUM(l.qty_remaining) as count
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE l.qty_remaining > 0 
                AND cm.series = ?
                AND (l.estimated_grade_text IS NOT NULL OR l.purchase_grade_text IS NOT NULL)
            GROUP BY grade_text, numeric_grade
            ORDER BY numeric_grade DESC NULLS LAST, grade_text
        """
        results = self.db.execute_query_all(query, (series,))
        return [GradeDistribution(**r) for r in results] if results else []

    def get_seller_breakdown(self, series: str) -> List[SellerBreakdown]:
        """Get seller breakdown for a series"""
        query = """
            SELECT 
                COALESCE(p.name, 'Unknown') as seller,
                SUM(l.qty_remaining) as coins_purchased,
                ROUND(SUM(l.qty_remaining * l.unit_cost), 2) as total_spent_usd,
                ROUND(AVG(l.unit_cost), 2) as avg_cost_per_coin
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            JOIN tx_line tl ON tl.id = l.acquisition_line_id
            JOIN tx t ON t.id = tl.tx_id
            LEFT JOIN party p ON p.id = t.party_id
            WHERE l.qty_remaining > 0 AND cm.series = ?
            GROUP BY seller
            ORDER BY total_spent_usd DESC
        """
        results = self.db.execute_query_all(query, (series,))
        return [SellerBreakdown(**r) for r in results] if results else []

    def get_location_breakdown(self, series: str) -> List[LocationBreakdown]:
        """Get location breakdown for a series"""
        query = """
            SELECT 
                COALESCE(sl.name, 'Not Specified') as location,
                SUM(l.qty_remaining) as coins_stored,
                ROUND(SUM(l.qty_remaining * lvd.chosen_unit_value), 2) as total_value_usd
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            JOIN v_lot_value_details lvd ON lvd.lot_id = l.id
            LEFT JOIN storage_location sl ON sl.id = l.storage_location_id
            WHERE l.qty_remaining > 0 AND cm.series = ?
            GROUP BY location
            ORDER BY total_value_usd DESC
        """
        results = self.db.execute_query_all(query, (series,))
        return [LocationBreakdown(**r) for r in results] if results else []

    def get_type_breakdown(self, series: str) -> List[TypeBreakdown]:
        """Get breakdown by coin type (year/mint/variety)"""
        query = """
            SELECT 
                ct.year,
                ct.mint_mark,
                COALESCE(ct.variety, '') as variety,
                SUM(l.qty_remaining) as quantity,
                ROUND(AVG(l.unit_cost), 2) as avg_cost,
                ROUND(SUM(l.qty_remaining * l.unit_cost), 2) as total_cost,
                ROUND(SUM(l.qty_remaining * lvd.chosen_unit_value), 2) as total_value
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            JOIN v_lot_value_details lvd ON lvd.lot_id = l.id
            WHERE l.qty_remaining > 0 AND cm.series = ?
            GROUP BY ct.year, ct.mint_mark, ct.variety
            ORDER BY ct.year, ct.mint_mark, ct.variety
        """
        results = self.db.execute_query_all(query, (series,))
        return [TypeBreakdown(**r) for r in results] if results else []

    def get_acquisition_timeline(self, series: str) -> List[AcquisitionTimeline]:
        """Get acquisition timeline for a series"""
        query = """
            SELECT 
                l.acquired_date as acquisition_date,
                SUM(l.qty_acquired) as coins_acquired,
                ROUND(SUM(l.qty_acquired * l.unit_cost), 2) as total_spent
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE cm.series = ?
            GROUP BY l.acquired_date
            ORDER BY l.acquired_date
        """
        results = self.db.execute_query_all(query, (series,))
        return [AcquisitionTimeline(**r) for r in results] if results else []

    def get_series_notes(self, series: str) -> List[Dict[str, Any]]:
        """Get notes for coins in a series"""
        query = """
            SELECT 
                ct.year,
                ct.mint_mark,
                COALESCE(ct.variety, '') as variety,
                l.notes,
                l.qty_remaining as quantity
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE l.qty_remaining > 0 
                AND cm.series = ?
                AND l.notes IS NOT NULL 
                AND TRIM(l.notes) != ''
            ORDER BY ct.year, ct.mint_mark, ct.variety
        """
        return self.db.execute_query_all(query, (series,))
