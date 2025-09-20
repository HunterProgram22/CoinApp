# infrastructure/database/repositories/bullion_repository.py
"""Bullion data repository - Single Responsibility: Data access for bullion and precious metals"""
from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class SpotPrice:
    """Data class for metal spot prices"""
    metal: str
    price_per_oz_usd: float


@dataclass
class BullionSummary:
    """Data class for bullion summary by category"""
    category: str
    metal: str
    units_on_hand: int
    gross_oz: float
    fine_oz: float
    melt_value_usd: float


@dataclass
class BullionDetail:
    """Data class for bullion detail by series"""
    category: str
    metal: str
    series: str
    unit_troy_oz: float
    unit_fine_oz: float
    units_on_hand: int
    gross_oz: float
    fine_oz: float
    melt_value_usd: float


@dataclass
class BullionTotals:
    """Data class for total bullion statistics"""
    total_units: int
    total_fine_oz: float
    total_value: float


@dataclass
class ConstitutionalSilver:
    """Data class for constitutional (junk) silver data"""
    category: str
    metal: str
    series: Optional[str]  # None for category summary, populated for series detail
    unit_troy_oz: Optional[float]  # None for category summary
    unit_fine_oz: Optional[float]  # None for category summary
    units_on_hand: int
    gross_oz: float
    fine_oz: float
    melt_value_usd: float


class BullionDataRepository(ABC):
    """Abstract repository for bullion data - Dependency Inversion"""

    @abstractmethod
    def get_latest_spot_prices(self) -> List[SpotPrice]:
        pass

    @abstractmethod
    def get_bullion_by_category(self) -> List[BullionSummary]:
        pass

    @abstractmethod
    def get_bullion_by_series(self) -> List[BullionDetail]:
        pass

    @abstractmethod
    def get_bullion_totals(self) -> Optional[BullionTotals]:
        pass

    @abstractmethod
    def get_constitutional_silver_by_category(self) -> List[ConstitutionalSilver]:
        pass

    @abstractmethod
    def get_constitutional_silver_by_series(self) -> List[ConstitutionalSilver]:
        pass

    @abstractmethod
    def get_combined_category_data(self) -> List[BullionSummary]:
        """Get combined bullion + constitutional silver data for category view"""
        pass

    @abstractmethod
    def get_combined_series_data(self) -> List[BullionDetail]:
        """Get combined bullion + constitutional silver data for series view"""
        pass


class SQLBullionRepository(BullionDataRepository):
    """Concrete SQL implementation of bullion repository"""

    def __init__(self, db_executor):
        """Inject database executor dependency"""
        self.db = db_executor

    def get_latest_spot_prices(self) -> List[SpotPrice]:
        """Get latest metal spot prices."""
        query = "SELECT metal, price_per_oz_usd FROM v_latest_spot ORDER BY metal"
        results = self.db.execute_query_all(query)
        return [SpotPrice(
            metal=r['metal'],
            price_per_oz_usd=r['price_per_oz_usd']
        ) for r in results]

    def get_bullion_by_category(self) -> List[BullionSummary]:
        """Get bullion summary by category and metal using the schema view."""
        query = """
            SELECT 
                category, 
                metal, 
                units_on_hand, 
                gross_oz, 
                fine_oz, 
                melt_value_usd
            FROM v_inventory_bullion_by_category
            ORDER BY category, metal
        """
        results = self.db.execute_query_all(query)
        return [BullionSummary(
            category=r['category'],
            metal=r['metal'],
            units_on_hand=int(r['units_on_hand'] or 0),
            gross_oz=float(r['gross_oz'] or 0.0),
            fine_oz=float(r['fine_oz'] or 0.0),
            melt_value_usd=float(r['melt_value_usd'] or 0.0)
        ) for r in results]

    def get_bullion_by_series(self) -> List[BullionDetail]:
        """Get bullion summary by series using the schema view."""
        query = """
            SELECT 
                category, 
                metal, 
                series, 
                unit_troy_oz, 
                unit_fine_oz, 
                units_on_hand, 
                gross_oz, 
                fine_oz, 
                melt_value_usd
            FROM v_inventory_bullion_by_series
            ORDER BY category, metal, series
        """
        results = self.db.execute_query_all(query)
        return [BullionDetail(
            category=r['category'],
            metal=r['metal'],
            series=r['series'],
            unit_troy_oz=float(r['unit_troy_oz'] or 0.0),
            unit_fine_oz=float(r['unit_fine_oz'] or 0.0),
            units_on_hand=int(r['units_on_hand'] or 0),
            gross_oz=float(r['gross_oz'] or 0.0),
            fine_oz=float(r['fine_oz'] or 0.0),
            melt_value_usd=float(r['melt_value_usd'] or 0.0)
        ) for r in results]

    def get_bullion_totals(self) -> Optional[BullionTotals]:
        """Get total bullion statistics including constitutional silver."""
        query = """
            WITH bullion_totals AS (
                SELECT 
                    SUM(units_on_hand) as total_units,
                    SUM(fine_oz) as total_fine_oz,
                    SUM(melt_value_usd) as total_value
                FROM v_inventory_bullion_by_category
            ),
            constitutional_totals AS (
                SELECT 
                    SUM(quantity) as total_units,
                    SUM(total_fine_oz) as total_fine_oz,
                    SUM(total_melt_value) as total_value
                FROM v_junk_silver
            )
            SELECT 
                COALESCE(b.total_units, 0) + COALESCE(c.total_units, 0) as total_units,
                COALESCE(b.total_fine_oz, 0) + COALESCE(c.total_fine_oz, 0) as total_fine_oz,
                COALESCE(b.total_value, 0) + COALESCE(c.total_value, 0) as total_value
            FROM bullion_totals b
            CROSS JOIN constitutional_totals c
        """
        result = self.db.execute_query_single(query)

        if not result or not result.get('total_units'):
            return None

        return BullionTotals(
            total_units=int(result['total_units'] or 0),
            total_fine_oz=float(result['total_fine_oz'] or 0.0),
            total_value=float(result['total_value'] or 0.0)
        )

    def get_constitutional_silver_by_category(self) -> List[ConstitutionalSilver]:
        """Get constitutional silver summary."""
        query = """
            SELECT 
                'Constitutional (Junk Silver)' as category,
                'Ag' as metal,
                SUM(quantity) as units_on_hand,
                SUM(total_fine_oz / 0.9) as gross_oz,  -- Approximate gross from fine for 90% silver
                SUM(total_fine_oz) as fine_oz,
                SUM(total_melt_value) as melt_value_usd
            FROM v_junk_silver
        """
        result = self.db.execute_query_single(query)

        if not result or not result.get('units_on_hand'):
            return []

        return [ConstitutionalSilver(
            category=result['category'],
            metal=result['metal'],
            series=None,  # Category summary has no series
            unit_troy_oz=None,  # Category summary has no unit values
            unit_fine_oz=None,
            units_on_hand=int(result['units_on_hand'] or 0),
            gross_oz=float(result['gross_oz'] or 0.0),
            fine_oz=float(result['fine_oz'] or 0.0),
            melt_value_usd=float(result['melt_value_usd'] or 0.0)
        )]

    def get_constitutional_silver_by_series(self) -> List[ConstitutionalSilver]:
        """Get constitutional silver by series."""
        query = """
            SELECT 
                'Constitutional (Junk Silver)' as category,
                'Ag' as metal,
                cm.series,
                ROUND((cm.weight_grams / 31.1034768), 4) as unit_troy_oz,
                ROUND((cm.weight_grams * cm.fineness) / 31.1034768, 4) as unit_fine_oz,
                SUM(l.qty_remaining) as units_on_hand,
                ROUND(SUM(l.qty_remaining * cm.weight_grams / 31.1034768), 4) as gross_oz,
                ROUND(SUM(l.qty_remaining * (cm.weight_grams * cm.fineness) / 31.1034768), 4) as fine_oz,
                ROUND(SUM(l.qty_remaining * v.melt_unit_value), 2) as melt_value_usd
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            JOIN v_lot_value_details v ON v.lot_id = l.id
            WHERE l.valuation_method = 'MELT_ONLY'
                AND l.qty_remaining > 0
                AND cm.metal = 'Ag'
                AND cm.asset_category = 'COIN'
            GROUP BY cm.series, cm.weight_grams, cm.fineness
            ORDER BY cm.series
        """
        results = self.db.execute_query_all(query)
        return [ConstitutionalSilver(
            category=r['category'],
            metal=r['metal'],
            series=r['series'],
            unit_troy_oz=float(r['unit_troy_oz'] or 0.0),
            unit_fine_oz=float(r['unit_fine_oz'] or 0.0),
            units_on_hand=int(r['units_on_hand'] or 0),
            gross_oz=float(r['gross_oz'] or 0.0),
            fine_oz=float(r['fine_oz'] or 0.0),
            melt_value_usd=float(r['melt_value_usd'] or 0.0)
        ) for r in results]

    def get_combined_category_data(self) -> List[BullionSummary]:
        """Get combined bullion + constitutional silver data for category view."""
        # Get regular bullion data
        bullion_data = self.get_bullion_by_category()

        # Get constitutional silver data and convert to BullionSummary format
        constitutional_data = self.get_constitutional_silver_by_category()
        constitutional_as_bullion = [
            BullionSummary(
                category=cs.category,
                metal=cs.metal,
                units_on_hand=cs.units_on_hand,
                gross_oz=cs.gross_oz,
                fine_oz=cs.fine_oz,
                melt_value_usd=cs.melt_value_usd
            ) for cs in constitutional_data
        ]

        return bullion_data + constitutional_as_bullion

    def get_combined_series_data(self) -> List[BullionDetail]:
        """Get combined bullion + constitutional silver data for series view."""
        # Get regular bullion data
        bullion_data = self.get_bullion_by_series()

        # Get constitutional silver data and convert to BullionDetail format
        constitutional_data = self.get_constitutional_silver_by_series()
        constitutional_as_bullion = [
            BullionDetail(
                category=cs.category,
                metal=cs.metal,
                series=cs.series or '',  # Handle None series
                unit_troy_oz=cs.unit_troy_oz or 0.0,
                unit_fine_oz=cs.unit_fine_oz or 0.0,
                units_on_hand=cs.units_on_hand,
                gross_oz=cs.gross_oz,
                fine_oz=cs.fine_oz,
                melt_value_usd=cs.melt_value_usd
            ) for cs in constitutional_data
        ]

        return bullion_data + constitutional_as_bullion
