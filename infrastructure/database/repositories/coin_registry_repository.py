# infrastructure/database/repositories/coin_registry_repository.py
"""Coin Registry repository for data access operations."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from infrastructure.database.db_operations import (
    execute_query_all, execute_query_single,
    execute_insert, execute_update, execute_delete
)
from core.queries import (
    get_specimen_by_code,
    get_specimens_on_hand,
    create_specimens_for_lot,
    create_or_update_series_code,
    get_all_lots,
)


# ==================== Data Classes ====================
@dataclass
class SlabbedCoin:
    """Slabbed coin information."""
    lot_id: int
    series: str
    year: int
    mint_mark: Optional[str]
    variety: Optional[str]
    quantity: int
    grade_company: str
    grade: str
    numeric_grade: float
    cert_number: str
    acquired_date: str
    cost: float
    acquired_from: str


@dataclass
class SlabbedSummary:
    """Summary statistics for slabbed coins."""
    total_slabs: int
    total_series: int
    total_coins: int
    grading_companies: int
    total_cost: float


@dataclass
class GradingCompanySummary:
    """Grading company breakdown."""
    company: str
    slab_count: int
    coin_count: int
    avg_grade: float


@dataclass
class Specimen:
    """Specimen/flip information."""
    code: str
    series: str
    year: int
    mint_mark: Optional[str]
    variety: Optional[str]
    lot_id: Optional[int]
    notes: Optional[str]


@dataclass
class SpecimenEnhanced:
    """Enhanced specimen with acquisition and value info."""
    code: str
    series: str
    year: int
    mint_mark: Optional[str]
    variety: Optional[str]
    lot_id: Optional[int]
    acquired_date: Optional[str]
    acquired_from: Optional[str]
    unit_cost: Optional[float]
    grade: Optional[str]
    est_value: Optional[float]


@dataclass
class LotInfo:
    """Lot information for specimens."""
    id: int
    series: str
    year: int
    mint_mark: Optional[str]
    variety: Optional[str]
    qty_remaining: int


# ==================== Repository Interface ====================
class CoinRegistryDataRepository(ABC):
    """Abstract interface for coin registry data operations."""

    # Slabbed coins operations
    @abstractmethod
    def get_slabbed_series_list(self) -> List[str]:
        """Get list of series that have slabbed coins."""
        pass

    @abstractmethod
    def get_slabbed_coins_by_series(self, series: Optional[str] = None) -> List[SlabbedCoin]:
        """Get all slabbed coins, optionally filtered by series."""
        pass

    @abstractmethod
    def search_slabbed_by_cert(self, cert_search: str) -> List[SlabbedCoin]:
        """Search slabbed coins by certificate number."""
        pass

    @abstractmethod
    def get_slabbed_summary(self) -> Optional[SlabbedSummary]:
        """Get summary statistics for slabbed coins."""
        pass

    @abstractmethod
    def get_slabbed_by_grade_company(self) -> List[GradingCompanySummary]:
        """Get breakdown by grading company."""
        pass

    # Specimens operations
    @abstractmethod
    def get_specimens_by_series(self, series: Optional[str] = None) -> List[Specimen]:
        """Get specimens optionally filtered by series."""
        pass

    @abstractmethod
    def get_specimens_by_series_enhanced(self, series: Optional[str] = None) -> List[
        SpecimenEnhanced]:
        """Get specimens with enhanced details including acquisition info and values."""
        pass

    @abstractmethod
    def get_series_with_specimens(self) -> List[str]:
        """Get list of series that have specimens."""
        pass

    @abstractmethod
    def count_specimens_for_lot(self, lot_id: int) -> int:
        """Count specimens assigned to a specific lot."""
        pass

    @abstractmethod
    def create_specific_codes_for_lot(self, lot_id: int, codes: List[str]) -> Tuple[
        List[str], List[str]]:
        """Create specific specimen codes for a lot."""
        pass

    @abstractmethod
    def update_specimen(self, old_code: str, new_code: Optional[str] = None,
                        new_lot_id: Optional[int] = None, notes: Optional[str] = None) -> Tuple[
        bool, str]:
        """Update an existing specimen."""
        pass

    @abstractmethod
    def delete_specimen(self, code: str) -> Tuple[bool, str]:
        """Delete a specimen if not sold."""
        pass

    @abstractmethod
    def get_lots_for_coin_type(self, coin_type_id: int) -> List[Dict[str, Any]]:
        """Get all lots for a specific coin type."""
        pass

    @abstractmethod
    def get_coin_type_for_specimen(self, code: str) -> Optional[int]:
        """Get coin_type_id for a specimen."""
        pass

    # Core queries delegation
    @abstractmethod
    def get_specimen_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Get specimen by code."""
        pass

    @abstractmethod
    def get_all_lots(self) -> List[Dict[str, Any]]:
        """Get all lots."""
        pass

    @abstractmethod
    def create_specimens_for_lot(self, lot_id: int, count: int, start_code: Optional[str] = None) -> \
    List[str]:
        """Auto-create specimens for a lot."""
        pass


# ==================== SQL Implementation ====================
class CoinRegistryRepository(CoinRegistryDataRepository):
    """SQL implementation of coin registry data operations."""

    def __init__(self, db_executor):
        """Initialize with database executor."""
        self.db = db_executor

    # Slabbed coins operations
    def get_slabbed_series_list(self) -> List[str]:
        """Get list of series that have slabbed coins."""
        query = """
            SELECT DISTINCT cm.series
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE l.qty_remaining > 0 
            AND l.slab_cert IS NOT NULL 
            AND TRIM(l.slab_cert) != ''
            ORDER BY cm.series
        """
        results = execute_query_all(query)
        return [r['series'] for r in results]

    def get_slabbed_coins_by_series(self, series: Optional[str] = None) -> List[SlabbedCoin]:
        """Get all slabbed coins, optionally filtered by series."""
        conditions = [
            "l.qty_remaining > 0",
            "l.slab_cert IS NOT NULL",
            "TRIM(l.slab_cert) != ''"
        ]
        params = []

        if series:
            conditions.append("cm.series = ?")
            params.append(series)

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT 
                l.id as lot_id,
                cm.series,
                ct.year,
                ct.mint_mark,
                COALESCE(ct.variety, '') as variety,
                l.qty_remaining as quantity,
                COALESCE(l.purchase_grade_company, '') as grade_company,
                COALESCE(l.purchase_grade_text, '') as grade,
                COALESCE(l.purchase_numeric_grade, 0) as numeric_grade,
                l.slab_cert as cert_number,
                l.acquired_date,
                ROUND(l.unit_cost, 2) as cost,
                COALESCE(p.name, '') as acquired_from
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            JOIN tx_line tl ON tl.id = l.acquisition_line_id
            JOIN tx t ON t.id = tl.tx_id
            LEFT JOIN party p ON p.id = t.party_id
            WHERE {where_clause}
            ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety, l.purchase_numeric_grade DESC
        """

        results = execute_query_all(query, tuple(params))
        return [SlabbedCoin(**row) for row in results]

    def search_slabbed_by_cert(self, cert_search: str) -> List[SlabbedCoin]:
        """Search slabbed coins by certificate number."""
        query = """
            SELECT 
                l.id as lot_id,
                cm.series,
                ct.year,
                ct.mint_mark,
                COALESCE(ct.variety, '') as variety,
                l.qty_remaining as quantity,
                COALESCE(l.purchase_grade_company, '') as grade_company,
                COALESCE(l.purchase_grade_text, '') as grade,
                COALESCE(l.purchase_numeric_grade, 0) as numeric_grade,
                l.slab_cert as cert_number,
                l.acquired_date,
                ROUND(l.unit_cost, 2) as cost,
                COALESCE(p.name, '') as acquired_from
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            JOIN tx_line tl ON tl.id = l.acquisition_line_id
            JOIN tx t ON t.id = tl.tx_id
            LEFT JOIN party p ON p.id = t.party_id
            WHERE l.qty_remaining > 0 
            AND l.slab_cert LIKE ?
            ORDER BY cm.series, ct.year
        """
        results = execute_query_all(query, (f"%{cert_search}%",))
        return [SlabbedCoin(**row) for row in results]

    def get_slabbed_summary(self) -> Optional[SlabbedSummary]:
        """Get summary statistics for slabbed coins."""
        query = """
            SELECT 
                COUNT(DISTINCT l.id) as total_slabs,
                COUNT(DISTINCT cm.series) as total_series,
                SUM(l.qty_remaining) as total_coins,
                COUNT(DISTINCT l.purchase_grade_company) as grading_companies,
                ROUND(SUM(l.qty_remaining * l.unit_cost), 2) as total_cost
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE l.qty_remaining > 0 
            AND l.slab_cert IS NOT NULL 
            AND TRIM(l.slab_cert) != ''
        """
        result = execute_query_single(query)
        return SlabbedSummary(**result) if result else None

    def get_slabbed_by_grade_company(self) -> List[GradingCompanySummary]:
        """Get breakdown by grading company."""
        query = """
            SELECT 
                COALESCE(l.purchase_grade_company, 'Unknown') as company,
                COUNT(DISTINCT l.id) as slab_count,
                SUM(l.qty_remaining) as coin_count,
                ROUND(AVG(l.purchase_numeric_grade), 1) as avg_grade
            FROM lot l
            WHERE l.qty_remaining > 0 
            AND l.slab_cert IS NOT NULL 
            AND TRIM(l.slab_cert) != ''
            GROUP BY l.purchase_grade_company
            ORDER BY slab_count DESC
        """
        results = execute_query_all(query)
        return [GradingCompanySummary(**row) for row in results]

    # Specimens operations
    def get_specimens_by_series(self, series: Optional[str] = None) -> List[Specimen]:
        """Get specimens optionally filtered by series."""
        conditions = ["s.sold_line_id IS NULL"]
        params = []

        if series and series != "All":
            conditions.append("cm.series = ?")
            params.append(series)

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        query = f"""
            SELECT 
                s.code,
                cm.series,
                ct.year,
                ct.mint_mark,
                COALESCE(ct.variety, '') as variety,
                s.lot_id,
                COALESCE(s.notes, '') as notes
            FROM specimen s
            JOIN coin_type ct ON ct.id = s.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            {where_clause}
            ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety, s.code
        """

        results = execute_query_all(query, tuple(params))
        return [Specimen(**row) for row in results]

    def get_specimens_by_series_enhanced(self, series: Optional[str] = None) -> List[
        SpecimenEnhanced]:
        """Get specimens with enhanced details including acquisition info and values."""
        conditions = ["s.sold_line_id IS NULL"]
        params = []

        if series and series != "All":
            conditions.append("cm.series = ?")
            params.append(series)

        where_clause = "WHERE " + " AND ".join(conditions)

        query = f"""
            SELECT 
                s.code,
                cm.series,
                ct.year,
                ct.mint_mark,
                ct.variety,
                s.lot_id,
                l.acquired_date,
                COALESCE(p.name, '') AS acquired_from,
                ROUND(l.unit_cost, 2) AS unit_cost,
                COALESCE(l.estimated_grade_text, l.purchase_grade_text, '') AS grade,
                ROUND(COALESCE(v.chosen_unit_value, l.unit_cost), 2) AS est_value
            FROM specimen s
            JOIN coin_type ct ON ct.id = s.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            LEFT JOIN lot l ON l.id = s.lot_id
            LEFT JOIN tx_line tl ON tl.id = l.acquisition_line_id
            LEFT JOIN tx t ON t.id = tl.tx_id
            LEFT JOIN party p ON p.id = t.party_id
            LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
            {where_clause}
            ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety, s.code
        """

        results = execute_query_all(query, params)
        return [SpecimenEnhanced(**row) for row in results]

    def get_series_with_specimens(self) -> List[str]:
        """Get list of series that have specimens."""
        query = """
            SELECT DISTINCT cm.series
            FROM specimen s
            JOIN coin_type ct ON ct.id = s.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE s.sold_line_id IS NULL
            ORDER BY cm.series
        """
        results = execute_query_all(query)
        return [r['series'] for r in results]

    def count_specimens_for_lot(self, lot_id: int) -> int:
        """Count specimens assigned to a specific lot."""
        query = "SELECT COUNT(*) AS count FROM specimen WHERE lot_id = ?"
        result = execute_query_single(query, (lot_id,))
        return result['count'] if result else 0

    def create_specific_codes_for_lot(self, lot_id: int, codes: List[str]) -> Tuple[
        List[str], List[str]]:
        """Create specific specimen codes for a lot."""
        created = []
        errors = []

        # Clean and validate codes
        codes = [c.strip().upper() for c in codes if str(c).strip()]
        if not codes:
            return created, ["No codes provided."]

        # Get coin_type_id for the lot
        lot_query = "SELECT coin_type_id FROM lot WHERE id = ?"
        lot_result = execute_query_single(lot_query, (lot_id,))

        if not lot_result:
            return created, [f"Unknown lot_id {lot_id}"]

        coin_type_id = lot_result['coin_type_id']

        # Process each code
        for code in codes:
            # Check if code already exists
            exists_query = "SELECT 1 FROM specimen WHERE code = ?"
            exists = execute_query_single(exists_query, (code,))

            if exists:
                errors.append(f"{code} already exists.")
                continue

            # Create the specimen
            try:
                execute_insert(
                    "INSERT INTO specimen(code, coin_type_id, lot_id) VALUES (?, ?, ?)",
                    (code, coin_type_id, lot_id)
                )
                created.append(code)
            except Exception as e:
                errors.append(f"Error creating {code}: {str(e)}")

        return created, errors

    def update_specimen(self, old_code: str, new_code: Optional[str] = None,
                        new_lot_id: Optional[int] = None, notes: Optional[str] = None) -> Tuple[
        bool, str]:
        """Update an existing specimen."""
        # Get current specimen
        query = "SELECT id, sold_line_id FROM specimen WHERE code = ?"
        specimen = execute_query_single(query, (old_code,))

        if not specimen:
            return False, "Specimen not found."

        # Check if new code already exists
        if new_code:
            exists = execute_query_single("SELECT 1 FROM specimen WHERE code = ?", (new_code,))
            if exists:
                return False, "The new code already exists."

        # Build update query
        updates = []
        params = []

        if new_code:
            updates.append("code = ?")
            params.append(new_code)

        if new_lot_id is not None:
            # Don't allow moving sold specimens
            if specimen['sold_line_id'] is not None:
                return False, "Cannot move a sold specimen."
            updates.append("lot_id = ?")
            params.append(new_lot_id)

        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)

        if not updates:
            return True, "Nothing to update."

        # Execute update
        params.append(specimen['id'])
        update_query = f"UPDATE specimen SET {', '.join(updates)} WHERE id = ?"

        try:
            execute_update(update_query, tuple(params))
            return True, "Updated."
        except Exception as e:
            return False, f"Update failed: {str(e)}"

    def delete_specimen(self, code: str) -> Tuple[bool, str]:
        """Delete a specimen if not sold."""
        # Check if specimen exists and is not sold
        query = "SELECT sold_line_id FROM specimen WHERE code = ?"
        specimen = execute_query_single(query, (code,))

        if not specimen:
            return False, "Specimen not found."

        if specimen['sold_line_id'] is not None:
            return False, "Cannot delete a specimen that has been sold."

        # Delete the specimen
        try:
            execute_delete("DELETE FROM specimen WHERE code = ?", (code,))
            return True, "Deleted."
        except Exception as e:
            return False, f"Delete failed: {str(e)}"

    def get_lots_for_coin_type(self, coin_type_id: int) -> List[Dict[str, Any]]:
        """Get all lots for a specific coin type."""
        query = "SELECT id, qty_remaining FROM lot WHERE coin_type_id = ?"
        return execute_query_all(query, (coin_type_id,))

    def get_coin_type_for_specimen(self, code: str) -> Optional[int]:
        """Get coin_type_id for a specimen."""
        query = "SELECT coin_type_id FROM specimen WHERE code = ?"
        result = execute_query_single(query, (code,))
        return result['coin_type_id'] if result else None

    # Core queries delegation
    def get_specimen_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Get specimen by code."""
        return get_specimen_by_code(code)

    def get_all_lots(self) -> List[Dict[str, Any]]:
        """Get all lots."""
        return get_all_lots()

    def create_specimens_for_lot(self, lot_id: int, count: int, start_code: Optional[str] = None) -> \
    List[str]:
        """Auto-create specimens for a lot."""
        return create_specimens_for_lot(lot_id, count, start_code)
