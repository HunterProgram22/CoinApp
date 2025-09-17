# infrastructure/database/repositories/proof_sets_repository.py
"""Proof Sets repository for data access operations."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from infrastructure.database.db_operations import (
    execute_query_all, execute_query_single,
    execute_insert, execute_update
)


# ==================== Data Classes ====================
@dataclass
class ProofSetMaster:
    """Proof set master definition."""
    id: int
    country: str
    year: int
    set_type: str
    set_name: str
    coin_count: Optional[int]
    includes_silver: int
    original_mint_price: Optional[float]


@dataclass
class ProofSetInventory:
    """Proof set inventory item."""
    id: int
    country: str
    year: int
    set_type: str
    set_name: str
    coin_count: Optional[int]
    includes_silver: int
    acquisition_date: str
    acquisition_price: float
    acquired_from: Optional[str]
    condition: str
    has_coa: int
    has_original_box: int
    storage_location: Optional[str]
    current_value: Optional[float]
    value_as_of: Optional[str]
    unrealized_gain_loss: Optional[float]
    gain_loss_percent: Optional[float]
    sold_date: Optional[str] = None
    sold_price: Optional[float] = None
    realized_gain_loss: Optional[float] = None


@dataclass
class InventorySummary:
    """Inventory summary by set type."""
    country: str
    year: int
    set_type: str
    sets_owned: int
    sets_on_hand: int
    sealed_sets: int
    total_cost: float
    total_current_value: Optional[float]
    avg_cost: float
    min_cost: float
    max_cost: float


@dataclass
class PortfolioSummary:
    """Overall portfolio summary."""
    items: int
    total_cost: float
    total_value: float
    unrealized_gl: float


@dataclass
class StorageLocation:
    """Storage location info."""
    id: int
    name: str
    category: Optional[str]


@dataclass
class MarketValue:
    """Market value entry."""
    value_date: str
    source: str
    condition: str
    market_value: float
    notes: Optional[str]


# ==================== Repository Interface ====================
class ProofSetsDataRepository(ABC):
    """Abstract interface for proof sets data operations."""

    @abstractmethod
    def get_proof_set_masters(self) -> List[ProofSetMaster]:
        """Get all proof set definitions."""
        pass

    @abstractmethod
    def get_inventory_summary(self) -> List[InventorySummary]:
        """Get summary of proof set inventory."""
        pass

    @abstractmethod
    def get_inventory_details(self, country: Optional[str] = None,
                              year: Optional[int] = None,
                              set_type: Optional[str] = None,
                              show_sold: bool = False) -> List[ProofSetInventory]:
        """Get detailed inventory with filters."""
        pass

    @abstractmethod
    def add_proof_set_master(self, country: str, year: int, set_type: str,
                             set_name: str, **kwargs) -> int:
        """Add a new proof set master record."""
        pass

    @abstractmethod
    def add_inventory_item(self, set_master_id: int, acquisition_date: str,
                           acquisition_price: float, **kwargs) -> int:
        """Add a proof set to inventory."""
        pass

    @abstractmethod
    def update_current_value(self, inventory_id: int, current_value: float,
                             value_date: str) -> bool:
        """Update current value of an inventory item."""
        pass

    @abstractmethod
    def record_sale(self, inventory_id: int, sold_date: str, sold_price: float,
                    sold_to: Optional[str] = None) -> bool:
        """Record the sale of a proof set."""
        pass

    @abstractmethod
    def get_storage_locations(self) -> List[StorageLocation]:
        """Get all storage locations."""
        pass

    @abstractmethod
    def get_portfolio_summary(self) -> PortfolioSummary:
        """Get portfolio summary including proof sets."""
        pass

    @abstractmethod
    def get_market_values(self, set_master_id: int) -> List[MarketValue]:
        """Get market value history for a proof set master."""
        pass

    @abstractmethod
    def add_market_value(self, set_master_id: int, value_date: str,
                         source: str, condition: str, market_value: float,
                         notes: Optional[str] = None) -> int:
        """Add a market value entry."""
        pass

    @abstractmethod
    def get_distinct_countries(self) -> List[str]:
        """Get distinct countries from proof set masters."""
        pass

    @abstractmethod
    def get_distinct_years(self) -> List[int]:
        """Get distinct years from proof set masters."""
        pass


# ==================== SQL Implementation ====================
class ProofSetsRepository(ProofSetsDataRepository):
    """SQL implementation of proof sets data operations."""

    def __init__(self, db_executor):
        """Initialize with database executor."""
        self.db = db_executor

    def get_proof_set_masters(self) -> List[ProofSetMaster]:
        """Get all proof set definitions."""
        query = """
            SELECT id, country, year, set_type, set_name, coin_count, 
                   includes_silver, original_mint_price
            FROM proof_set_master
            ORDER BY country, year DESC, set_type
        """
        results = execute_query_all(query)
        return [ProofSetMaster(**row) for row in results]

    def get_inventory_summary(self) -> List[InventorySummary]:
        """Get summary of proof set inventory."""
        query = """
            SELECT * FROM v_proof_set_summary
            ORDER BY country, year DESC, set_type
        """
        results = execute_query_all(query)

        return [InventorySummary(**row) for row in results] if results else []

    def get_inventory_details(self, country: Optional[str] = None,
                              year: Optional[int] = None,
                              set_type: Optional[str] = None,
                              show_sold: bool = False) -> List[ProofSetInventory]:
        """Get detailed inventory with filters."""
        conditions = []
        params = []

        if country:
            conditions.append("country = ?")
            params.append(country)

        if year:
            conditions.append("year = ?")
            params.append(year)

        if set_type:
            conditions.append("set_type = ?")
            params.append(set_type)

        if not show_sold:
            conditions.append("sold_date IS NULL")

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
            SELECT * FROM v_proof_set_inventory
            {where_clause}
            ORDER BY country, year DESC, acquisition_date DESC
        """

        results = execute_query_all(query, tuple(params))
        return [ProofSetInventory(**row) for row in results] if results else []

    def add_proof_set_master(self, country: str, year: int, set_type: str,
                             set_name: str, **kwargs) -> int:
        """Add a new proof set master record."""
        query = """
            INSERT INTO proof_set_master (
                country, year, set_type, set_name, mint_mark, face_value,
                original_mint_price, coin_count, includes_silver, special_features,
                packaging_type, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            country, year, set_type, set_name,
            kwargs.get('mint_mark'),
            kwargs.get('face_value'),
            kwargs.get('original_mint_price'),
            kwargs.get('coin_count'),
            1 if kwargs.get('includes_silver') else 0,
            kwargs.get('special_features'),
            kwargs.get('packaging_type'),
            kwargs.get('notes')
        )
        return execute_insert(query, params)

    def add_inventory_item(self, set_master_id: int, acquisition_date: str,
                           acquisition_price: float, **kwargs) -> int:
        """Add a proof set to inventory."""
        # Find or create party if provided
        party_id = None
        if kwargs.get('party_name'):
            party = execute_query_single("SELECT id FROM party WHERE name = ?",
                                         (kwargs['party_name'],))
            if party:
                party_id = party['id']
            else:
                party_id = execute_insert("INSERT INTO party(name) VALUES (?)",
                                          (kwargs['party_name'],))

        query = """
            INSERT INTO proof_set_inventory (
                set_master_id, acquisition_date, acquisition_price, party_id,
                condition, has_coa, has_original_box, storage_location_id,
                purchase_notes, current_value, value_as_of, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            set_master_id, acquisition_date, acquisition_price, party_id,
            kwargs.get('condition', 'SEALED'),
            1 if kwargs.get('has_coa', True) else 0,
            1 if kwargs.get('has_original_box', True) else 0,
            kwargs.get('storage_location_id'),
            kwargs.get('purchase_notes'),
            kwargs.get('current_value'),
            kwargs.get('value_as_of'),
            kwargs.get('notes')
        )
        return execute_insert(query, params)

    def update_current_value(self, inventory_id: int, current_value: float,
                             value_date: str) -> bool:
        """Update current value of an inventory item."""
        query = """
            UPDATE proof_set_inventory 
            SET current_value = ?, value_as_of = ?
            WHERE id = ?
        """
        return execute_update(query, (current_value, value_date, inventory_id)) > 0

    def record_sale(self, inventory_id: int, sold_date: str, sold_price: float,
                    sold_to: Optional[str] = None) -> bool:
        """Record the sale of a proof set."""
        # Handle sold_to party
        sold_to_party_id = None
        if sold_to:
            party = execute_query_single("SELECT id FROM party WHERE name = ?", (sold_to,))
            if party:
                sold_to_party_id = party['id']
            else:
                sold_to_party_id = execute_insert("INSERT INTO party(name) VALUES (?)", (sold_to,))

        query = """
            UPDATE proof_set_inventory 
            SET sold_date = ?, sold_price = ?, sold_to_party_id = ?
            WHERE id = ?
        """
        return execute_update(query, (sold_date, sold_price, sold_to_party_id, inventory_id)) > 0

    def get_storage_locations(self) -> List[StorageLocation]:
        """Get all storage locations."""
        query = "SELECT id, name, category FROM storage_location ORDER BY name"
        results = execute_query_all(query)
        return [StorageLocation(**row) for row in results]

    def get_portfolio_summary(self) -> PortfolioSummary:
        """Get portfolio summary including proof sets."""
        query = """
            SELECT 
                COALESCE(COUNT(DISTINCT psi.id), 0) AS items,
                COALESCE(ROUND(SUM(psi.acquisition_price), 2), 0.0) AS total_cost,
                COALESCE(ROUND(SUM(COALESCE(psi.current_value, psi.acquisition_price)), 2), 0.0) AS total_value,
                COALESCE(ROUND(SUM(COALESCE(psi.current_value, psi.acquisition_price)) - SUM(psi.acquisition_price), 2), 0.0) AS unrealized_gl
            FROM proof_set_inventory psi
            WHERE psi.sold_date IS NULL
        """
        result = execute_query_single(query)

        if result:
            return PortfolioSummary(
                items=result.get('items') or 0,
                total_cost=float(result.get('total_cost') or 0),
                total_value=float(result.get('total_value') or 0),
                unrealized_gl=float(result.get('unrealized_gl') or 0)
            )
        else:
            return PortfolioSummary(items=0, total_cost=0.0, total_value=0.0, unrealized_gl=0.0)

    def get_market_values(self, set_master_id: int) -> List[MarketValue]:
        """Get market value history for a proof set master."""
        query = """
            SELECT value_date, source, condition, market_value, notes
            FROM proof_set_values
            WHERE set_master_id = ?
            ORDER BY value_date DESC
        """
        results = execute_query_all(query, (set_master_id,))
        return [MarketValue(**row) for row in results] if results else []

    def add_market_value(self, set_master_id: int, value_date: str,
                         source: str, condition: str, market_value: float,
                         notes: Optional[str] = None) -> int:
        """Add a market value entry."""
        query = """
            INSERT INTO proof_set_values 
            (set_master_id, value_date, source, condition, market_value, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        return execute_insert(query,
                              (set_master_id, value_date, source, condition, market_value, notes))

    def get_distinct_countries(self) -> List[str]:
        """Get distinct countries from proof set masters."""
        query = "SELECT DISTINCT country FROM proof_set_master ORDER BY country"
        results = execute_query_all(query)
        return [r['country'] for r in results]

    def get_distinct_years(self) -> List[int]:
        """Get distinct years from proof set masters."""
        query = "SELECT DISTINCT year FROM proof_set_master ORDER BY year DESC"
        results = execute_query_all(query)
        return [r['year'] for r in results]
