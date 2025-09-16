# infrastructure/database/repositories/inventory_repository.py
"""Inventory data repository - Single Responsibility: Data access for inventory"""
from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class InventoryByType:
    """Data class for inventory grouped by type"""
    coin_type_id: int
    series: str
    year: int
    mint_mark: str
    variety: str
    coins_on_hand: int


@dataclass
class InventoryBySeries:
    """Data class for inventory grouped by series"""
    series: str
    country: str
    coins: int
    est_value_usd: Optional[float]


@dataclass
class SeriesDetail:
    """Data class for detailed series inventory"""
    lot_id: int
    series: str
    year: int
    mint_mark: str
    variety: str
    qty_remaining: int
    unit_cost_usd: float
    melt_unit_value: float
    chosen_unit_value: float
    lot_est_value: float
    # Add other fields as needed


@dataclass
class FlaggedInventory:
    """Data class for inventory filtered by flags"""
    lot_id: int
    series: str
    year: int
    mint_mark: str
    variety: str
    qty_remaining: int
    unit_cost_usd: float
    melt_unit_value: float
    chosen_unit_value: float
    lot_est_value: float
    is_proof: bool
    cert_number: Optional[str]
    # Add other fields as needed


class InventoryDataRepository(ABC):
    """Abstract repository for inventory data - Dependency Inversion"""
    
    @abstractmethod
    def get_inventory_by_type(self) -> List[InventoryByType]:
        pass
    
    @abstractmethod
    def get_inventory_by_series(self, country_filter: str = "All") -> List[InventoryBySeries]:
        pass
    
    @abstractmethod
    def get_series_list(self) -> List[str]:
        pass
    
    @abstractmethod
    def get_countries_with_inventory(self) -> List[str]:
        pass
    
    @abstractmethod
    def get_series_list_for_country(self, country: Optional[str] = None) -> List[str]:
        pass

    @abstractmethod
    def get_inventory_by_series_detail(self, series: str) -> List[SeriesDetail]:
        pass
    
    @abstractmethod
    def get_inventory_by_flags(self, want_proofs: bool, want_slabbed: bool) -> List[FlaggedInventory]:
        pass


class SQLInventoryRepository(InventoryDataRepository):
    """Concrete SQL implementation of inventory repository"""
    
    def __init__(self, db_executor):
        """Inject database executor dependency"""
        self.db = db_executor
    
    def get_inventory_by_type(self) -> List[InventoryByType]:
        """Get inventory grouped by coin type."""
        query = """
            SELECT
                ct.id AS coin_type_id,
                cm.series,
                ct.year,
                ct.mint_mark,
                COALESCE(ct.variety, '') AS variety,
                SUM(l.qty_remaining) AS coins_on_hand
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE l.qty_remaining > 0
            GROUP BY ct.id, cm.series, ct.year, ct.mint_mark, ct.variety
            ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety
        """
        results = self.db.execute_query_all(query)
        return [InventoryByType(**result) for result in results]
    
    def get_inventory_by_series(self, country_filter: str = "All") -> List[InventoryBySeries]:
        """Get inventory summary by series using v_lot_value_details view."""
        # Check if view exists first
        view_check = self.db.execute_query_single(
            "SELECT 1 FROM sqlite_master WHERE type='view' AND name='v_lot_value_details'"
        )

        # Build WHERE clause based on filter
        where_clause = ""
        if country_filter == "US Only":
            where_clause = "WHERE cm.country = 'USA'"
        elif country_filter == "World Only":
            where_clause = "WHERE cm.country != 'USA'"

        if view_check:
            query = f"""
                SELECT
                    cm.series as series,
                    cm.country,
                    SUM(v.qty_remaining) AS coins,
                    ROUND(SUM(v.qty_remaining * COALESCE(v.chosen_unit_value, 0)), 2) AS est_value_usd
                FROM v_lot_value_details v
                JOIN lot l ON l.id = v.lot_id
                JOIN coin_type ct ON ct.id = l.coin_type_id
                JOIN coin_master cm ON cm.id = ct.master_id
                {where_clause}
                GROUP BY cm.series, cm.country
                ORDER BY est_value_usd DESC, cm.series
            """
        else:
            # Fallback if view doesn't exist
            query = f"""
                SELECT 
                    cm.series AS series,
                    cm.country,
                    SUM(l.qty_remaining) AS coins, 
                    NULL AS est_value_usd
                FROM lot l
                JOIN coin_type ct ON ct.id = l.coin_type_id
                JOIN coin_master cm ON cm.id = ct.master_id
                WHERE l.qty_remaining > 0
                {' AND ' + where_clause.replace('WHERE ', '') if where_clause else ''}
                GROUP BY cm.series, cm.country
                ORDER BY coins DESC, cm.series
            """

        results = self.db.execute_query_all(query)
        return [InventoryBySeries(**result) for result in results]
    
    def get_series_list(self) -> List[str]:
        """Get list of available series."""
        query = "SELECT DISTINCT series FROM coin_master ORDER BY series"
        results = self.db.execute_query_all(query)
        return [r['series'] for r in results]
    
    def get_countries_with_inventory(self) -> List[str]:
        """Get list of countries that have inventory on hand."""
        query = """
            SELECT DISTINCT cm.country
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE l.qty_remaining > 0 AND cm.country IS NOT NULL
            ORDER BY cm.country
        """
        results = self.db.execute_query_all(query)
        return [r['country'] for r in results]
    
    def get_series_list_for_country(self, country: Optional[str] = None) -> List[str]:
        """Get list of available series, optionally filtered by country."""
        if country:
            query = """
                SELECT DISTINCT cm.series 
                FROM lot l
                JOIN coin_type ct ON ct.id = l.coin_type_id
                JOIN coin_master cm ON cm.id = ct.master_id
                WHERE l.qty_remaining > 0 AND cm.country = ?
                ORDER BY cm.series
            """
            results = self.db.execute_query_all(query, (country,))
        else:
            query = "SELECT DISTINCT series FROM coin_master ORDER BY series"
            results = self.db.execute_query_all(query)
        return [r['series'] for r in results]

    # Replace these two methods in your inventory_repository.py

    def get_inventory_by_series_detail(self, series: str) -> List[SeriesDetail]:
        """Get detailed inventory for a specific series."""
        from presentation.components.helpers.inventory_helpers import \
            get_inventory_by_series_detail as helper_detail
        results = helper_detail(series)

        # Convert dict results to dataclass instances using CORRECT column names
        return [SeriesDetail(
            lot_id=r.get('lot_id', 0),
            series=r.get('Series', ''),  # Note: Capital 'S'
            year=r.get('Year', 0),  # Note: Capital 'Y'
            mint_mark=r.get('Mint Mark', ''),  # Note: Spaces and capitals
            variety=r.get('Variety', ''),  # Note: Capital 'V'
            qty_remaining=r.get('Qty', 0),  # Note: 'Qty' not 'qty_remaining'
            unit_cost_usd=r.get('Unit Cost (USD)', 0.0),  # Note: Full name with spaces
            melt_unit_value=r.get('Melt Unit Value', 0.0),  # Note: Spaces
            chosen_unit_value=r.get('Chosen Unit Value', 0.0),  # Note: Spaces
            lot_est_value=r.get('Lot Est. Value', 0.0)  # Note: Spaces and period
        ) for r in results]

    def get_inventory_by_flags(self, want_proofs: bool, want_slabbed: bool) -> List[
        FlaggedInventory]:
        """Get inventory filtered by flags."""
        from presentation.components.helpers.inventory_helpers import \
            get_inventory_by_flags as helper_flags
        results = helper_flags(want_proofs, want_slabbed)

        # Convert dict results to dataclass instances using CORRECT column names
        return [FlaggedInventory(
            lot_id=r.get('lot_id', 0),
            series=r.get('Series', ''),  # Note: Capital 'S'
            year=r.get('Year', 0),  # Note: Capital 'Y'
            mint_mark=r.get('Mint Mark', ''),  # Note: Spaces and capitals
            variety=r.get('Variety', ''),  # Note: Capital 'V'
            qty_remaining=r.get('Qty', 0),  # Note: 'Qty' not 'qty_remaining'
            unit_cost_usd=r.get('Unit Cost (USD)', 0.0),  # Note: Full name with spaces
            melt_unit_value=r.get('Melt Unit Value', 0.0),  # Note: Spaces
            chosen_unit_value=r.get('Chosen Unit Value', 0.0),  # Note: Spaces
            lot_est_value=r.get('Lot Est. Value', 0.0),  # Note: Spaces and period
            is_proof=r.get('Proof', 'No') == 'Yes',  # Convert 'Yes'/'No' to boolean
            cert_number=r.get('Slabbed', 'No')  # Note: using 'Slabbed' field
        ) for r in results]
