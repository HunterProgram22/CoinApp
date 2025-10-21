# infrastructure/database/repositories/storage_report_repository.py
"""Storage Report repository for data access operations."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from infrastructure.database.db_operations import (
    execute_query_all, execute_query_single,
    execute_insert, execute_update, execute_delete
)


# ==================== Data Classes ====================
@dataclass
class StorageLocation:
    """Storage location with inventory summary."""
    id: int
    name: str
    category: Optional[str]
    description: Optional[str]
    lot_count: int
    total_coins: int
    total_cost_usd: float
    total_value_usd: float


@dataclass
class StorageInventory:
    """Detailed inventory item in storage."""
    lot_id: int
    series: str
    year: Optional[int]
    mint_mark: Optional[str]
    variety: Optional[str]
    is_proof: str
    quantity: int
    acquired_date: str
    acquired_from: Optional[str]
    unit_cost_usd: float
    lot_cost_usd: float
    grade: Optional[str]
    cert_number: Optional[str]
    valuation_method: Optional[str]
    notes: Optional[str]
    est_value_usd: float


@dataclass
class StorageSummary:
    """Overall storage summary statistics."""
    total_locations: int
    locations_with_inventory: int
    unassigned_coins: int
    unassigned_value: float


@dataclass
class CategorySummary:
    """Summary statistics for a storage category."""
    location_count: int
    total_coins: int
    total_cost: float
    total_value: float


@dataclass
class LotInStorage:
    """Simplified lot info for bulk operations."""
    id: int
    description: str
    qty_remaining: int
    total_value: float


# ==================== Repository Interface ====================
class StorageReportDataRepository(ABC):
    """Abstract interface for storage report data operations."""

    @abstractmethod
    def get_storage_locations(self, category_filter: Optional[str] = None) -> List[StorageLocation]:
        """Get all storage locations with inventory counts."""
        pass

    @abstractmethod
    def get_storage_categories(self) -> List[str]:
        """Get list of unique storage categories."""
        pass

    @abstractmethod
    def get_category_summary(self, category: str) -> Optional[CategorySummary]:
        """Get summary statistics for a specific storage category."""
        pass

    @abstractmethod
    def get_inventory_by_storage(self, storage_id: int) -> List[StorageInventory]:
        """Get detailed inventory for a specific storage location."""
        pass

    @abstractmethod
    def get_unassigned_inventory(self) -> List[StorageInventory]:
        """Get inventory not assigned to any storage location."""
        pass

    @abstractmethod
    def get_storage_summary(self) -> Optional[StorageSummary]:
        """Get overall storage summary statistics."""
        pass

    @abstractmethod
    def create_storage_location(self, name: str, category: Optional[str] = None,
                                description: Optional[str] = None) -> int:
        """Create a new storage location."""
        pass

    @abstractmethod
    def update_storage_location(self, storage_id: int, name: str,
                                category: Optional[str] = None,
                                description: Optional[str] = None) -> int:
        """Update an existing storage location."""
        pass

    @abstractmethod
    def delete_storage_location(self, storage_id: int) -> bool:
        """Delete a storage location if it has no inventory."""
        pass

    @abstractmethod
    def bulk_move_lots(self, lot_ids: List[int], new_storage_id: Optional[int]) -> int:
        """Move multiple lots to a new storage location."""
        pass

    @abstractmethod
    def get_lots_in_storage(self, storage_id: Optional[int]) -> List[LotInStorage]:
        """Get all lots in a specific storage location."""
        pass

    @abstractmethod
    def get_storage_location_info(self, storage_id: int) -> Optional[Dict[str, Any]]:
        """Get basic info for a storage location."""
        pass


# ==================== SQL Implementation ====================
class StorageReportRepository(StorageReportDataRepository):
    """SQL implementation of storage report data operations."""

    def __init__(self, db_executor):
        """Initialize with database executor."""
        self.db = db_executor

    def get_storage_locations(self, category_filter: Optional[str] = None) -> List[StorageLocation]:
        """Get all storage locations with inventory counts."""
        # OPTIMIZED: Use CTEs to avoid expensive v_lot_value_details view
        base_query = """
            WITH spot_prices AS (
                SELECT metal, price_per_oz_usd FROM v_latest_spot
            ),
            guide_prices AS (
                SELECT coin_type_id, grade_text, price_usd FROM v_latest_guide
            )
            SELECT 
                sl.id,
                sl.name,
                COALESCE(sl.category, '') AS category,
                COALESCE(sl.description, '') AS description,
                COUNT(l.id) AS lot_count,
                COALESCE(SUM(l.qty_remaining), 0) AS total_coins,
                COALESCE(SUM(l.qty_remaining * l.unit_cost), 0) AS total_cost_usd,
                COALESCE(SUM(
                    l.qty_remaining * 
                    CASE l.valuation_method
                        WHEN 'MELT_ONLY' THEN 
                            (cm.weight_grams * COALESCE(cm.fineness, 0)) / 31.1034768 
                            * COALESCE(sp.price_per_oz_usd, 0)
                        WHEN 'GUIDE_ONLY' THEN 
                            COALESCE(gp.price_usd, 0)
                        WHEN 'MANUAL' THEN 
                            COALESCE(l.manual_est_unit_value, 0)
                        ELSE 
                            COALESCE(
                                gp.price_usd,
                                CASE 
                                    WHEN cm.metal IN ('Ag','Au','Pt','Pd') THEN
                                        (cm.weight_grams * COALESCE(cm.fineness, 0)) / 31.1034768 
                                        * COALESCE(sp.price_per_oz_usd, 0)
                                    ELSE 0
                                END,
                                l.manual_est_unit_value,
                                l.unit_cost,
                                0
                            )
                    END
                ), 0) AS total_value_usd
            FROM storage_location sl
            LEFT JOIN lot l ON l.storage_location_id = sl.id AND l.qty_remaining > 0
            LEFT JOIN coin_type ct ON ct.id = l.coin_type_id
            LEFT JOIN coin_master cm ON cm.id = ct.master_id
            LEFT JOIN spot_prices sp ON sp.metal = cm.metal
            LEFT JOIN guide_prices gp ON gp.coin_type_id = l.coin_type_id 
                AND gp.grade_text = COALESCE(l.estimated_grade_text, l.purchase_grade_text)
        """

        if category_filter and category_filter != "All":
            query = base_query + """
                WHERE sl.category = ?
                GROUP BY sl.id, sl.name, sl.category, sl.description
                ORDER BY sl.name
            """
            results = execute_query_all(query, (category_filter,))
        else:
            query = base_query + """
                GROUP BY sl.id, sl.name, sl.category, sl.description
                ORDER BY sl.name
            """
            results = execute_query_all(query)

        return [StorageLocation(**row) for row in results]

    def get_storage_categories(self) -> List[str]:
        """Get list of unique storage categories."""
        query = """
            SELECT DISTINCT category 
            FROM storage_location 
            WHERE category IS NOT NULL AND category != ''
            ORDER BY category
        """
        results = execute_query_all(query)
        return [r['category'] for r in results]

    def get_category_summary(self, category: str) -> Optional[CategorySummary]:
        """Get summary statistics for a specific storage category."""
        query = """
            SELECT 
                COUNT(DISTINCT sl.id) AS location_count,
                COALESCE(SUM(l.qty_remaining), 0) AS total_coins,
                COALESCE(SUM(l.qty_remaining * l.unit_cost), 0) AS total_cost,
                COALESCE(SUM(l.qty_remaining * COALESCE(v.chosen_unit_value, l.unit_cost)), 0) AS total_value
            FROM storage_location sl
            LEFT JOIN lot l ON l.storage_location_id = sl.id AND l.qty_remaining > 0
            LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
            WHERE sl.category = ?
        """
        result = execute_query_single(query, (category,))
        return CategorySummary(**result) if result else None

    def get_inventory_by_storage(self, storage_id: int) -> List[StorageInventory]:
        """Get detailed inventory for a specific storage location."""
        query = """
            SELECT
                l.id AS lot_id,
                cm.series,
                ct.year,
                ct.mint_mark,
                COALESCE(ct.variety, '') AS variety,
                CASE WHEN ct.is_proof = 1 THEN 'Yes' ELSE 'No' END AS is_proof,
                l.qty_remaining AS quantity,
                t.tx_date AS acquired_date,
                COALESCE(p.name, '') AS acquired_from,
                ROUND(l.unit_cost, 2) AS unit_cost_usd,
                ROUND(l.qty_remaining * l.unit_cost, 2) AS lot_cost_usd,
                COALESCE(l.estimated_grade_text, l.purchase_grade_text, '') AS grade,
                COALESCE(l.slab_cert, '') AS cert_number,
                l.valuation_method,
                COALESCE(l.notes, '') AS notes,
                ROUND(l.qty_remaining * COALESCE(v.chosen_unit_value, l.unit_cost), 2) AS est_value_usd
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            JOIN tx_line tl ON tl.id = l.acquisition_line_id
            JOIN tx t ON t.id = tl.tx_id
            LEFT JOIN party p ON p.id = t.party_id
            LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
            WHERE l.storage_location_id = ? AND l.qty_remaining > 0
            ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety, l.acquired_date
        """
        results = execute_query_all(query, (storage_id,))
        return [StorageInventory(**row) for row in results]

    def get_unassigned_inventory(self) -> List[StorageInventory]:
        """Get inventory not assigned to any storage location."""
        query = """
            SELECT
                l.id AS lot_id,
                cm.series,
                ct.year,
                ct.mint_mark,
                COALESCE(ct.variety, '') AS variety,
                CASE WHEN ct.is_proof = 1 THEN 'Yes' ELSE 'No' END AS is_proof,
                l.qty_remaining AS quantity,
                t.tx_date AS acquired_date,
                COALESCE(p.name, '') AS acquired_from,
                ROUND(l.unit_cost, 2) AS unit_cost_usd,
                ROUND(l.qty_remaining * l.unit_cost, 2) AS lot_cost_usd,
                COALESCE(l.estimated_grade_text, l.purchase_grade_text, '') AS grade,
                COALESCE(l.slab_cert, '') AS cert_number,
                l.valuation_method,
                COALESCE(l.notes, '') AS notes,
                ROUND(l.qty_remaining * COALESCE(v.chosen_unit_value, l.unit_cost), 2) AS est_value_usd
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            JOIN tx_line tl ON tl.id = l.acquisition_line_id
            JOIN tx t ON t.id = tl.tx_id
            LEFT JOIN party p ON p.id = t.party_id
            LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
            WHERE l.storage_location_id IS NULL AND l.qty_remaining > 0
            ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety, l.acquired_date
        """
        results = execute_query_all(query)
        return [StorageInventory(**row) for row in results]

    def get_storage_summary(self) -> Optional[StorageSummary]:
        """Get overall storage summary statistics."""
        query = """
            SELECT 
                (SELECT COUNT(*) FROM storage_location) AS total_locations,
                (SELECT COUNT(DISTINCT l.storage_location_id) 
                 FROM lot l 
                 WHERE l.qty_remaining > 0 AND l.storage_location_id IS NOT NULL) AS locations_with_inventory,
                (SELECT COALESCE(SUM(l.qty_remaining), 0) 
                 FROM lot l 
                 WHERE l.qty_remaining > 0 AND l.storage_location_id IS NULL) AS unassigned_coins,
                (SELECT COALESCE(SUM(l.qty_remaining * l.unit_cost), 0)
                 FROM lot l 
                 WHERE l.qty_remaining > 0 AND l.storage_location_id IS NULL) AS unassigned_value
        """
        result = execute_query_single(query)
        return StorageSummary(**result) if result else None

    def create_storage_location(self, name: str, category: Optional[str] = None,
                                description: Optional[str] = None) -> int:
        """Create a new storage location."""
        query = "INSERT INTO storage_location (name, category, description) VALUES (?, ?, ?)"
        return execute_insert(query, (name, category, description))

    def update_storage_location(self, storage_id: int, name: str,
                                category: Optional[str] = None,
                                description: Optional[str] = None) -> int:
        """Update an existing storage location."""
        query = "UPDATE storage_location SET name = ?, category = ?, description = ? WHERE id = ?"
        return execute_update(query, (name, category, description, storage_id))

    def delete_storage_location(self, storage_id: int) -> bool:
        """Delete a storage location if it has no inventory."""
        # Check if location has inventory
        check_query = "SELECT COUNT(*) as count FROM lot WHERE storage_location_id = ? AND qty_remaining > 0"
        result = execute_query_single(check_query, (storage_id,))

        if result and result['count'] > 0:
            return False  # Has inventory, cannot delete

        delete_query = "DELETE FROM storage_location WHERE id = ?"
        execute_delete(delete_query, (storage_id,))
        return True

    def bulk_move_lots(self, lot_ids: List[int], new_storage_id: Optional[int]) -> int:
        """Move multiple lots to a new storage location."""
        if not lot_ids:
            return 0

        # Build the query with proper parameterization
        placeholders = ','.join('?' * len(lot_ids))
        query = f"UPDATE lot SET storage_location_id = ? WHERE id IN ({placeholders})"

        # Parameters: new_storage_id first, then all lot_ids
        params = [new_storage_id] + lot_ids
        return execute_update(query, tuple(params))

    def get_lots_in_storage(self, storage_id: Optional[int]) -> List[LotInStorage]:
        """Get all lots in a specific storage location."""
        if storage_id is None:
            query = """
                SELECT 
                    l.id,
                    cm.series || ' ' || ct.year || 
                    CASE WHEN ct.mint_mark != '' THEN ' ' || ct.mint_mark ELSE '' END ||
                    CASE WHEN ct.variety != '' THEN ' - ' || ct.variety ELSE '' END AS description,
                    l.qty_remaining,
                    ROUND(l.unit_cost * l.qty_remaining, 2) as total_value
                FROM lot l
                JOIN coin_type ct ON ct.id = l.coin_type_id
                JOIN coin_master cm ON cm.id = ct.master_id
                WHERE l.storage_location_id IS NULL AND l.qty_remaining > 0
                ORDER BY cm.series, ct.year
            """
            results = execute_query_all(query)
        else:
            query = """
                SELECT 
                    l.id,
                    cm.series || ' ' || ct.year || 
                    CASE WHEN ct.mint_mark != '' THEN ' ' || ct.mint_mark ELSE '' END ||
                    CASE WHEN ct.variety != '' THEN ' - ' || ct.variety ELSE '' END AS description,
                    l.qty_remaining,
                    ROUND(l.unit_cost * l.qty_remaining, 2) as total_value
                FROM lot l
                JOIN coin_type ct ON ct.id = l.coin_type_id
                JOIN coin_master cm ON cm.id = ct.master_id
                WHERE l.storage_location_id = ? AND l.qty_remaining > 0
                ORDER BY cm.series, ct.year
            """
            results = execute_query_all(query, (storage_id,))

        return [LotInStorage(**row) for row in results]

    def get_storage_location_info(self, storage_id: int) -> Optional[Dict[str, Any]]:
        """Get basic info for a storage location."""
        query = "SELECT name, category, description FROM storage_location WHERE id = ?"
        return execute_query_single(query, (storage_id,))
