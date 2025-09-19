# infrastructure/database/repositories/type_sets_repository.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple
import pandas as pd
from datetime import datetime
from infrastructure.database.db_operations import (
    execute_query_all, execute_query_single, execute_insert,
    execute_update, execute_delete
)


@dataclass
class TypeSet:
    id: int
    name: str
    description: Optional[str] = None
    total_coins: int = 0
    coins_owned: int = 0
    coins_meeting_requirements: int = 0
    percent_owned: float = 0.0
    percent_complete: float = 0.0
    grade_company: Optional[str] = None
    min_grade: Optional[str] = None
    max_grade: Optional[str] = None
    require_slab: bool = False


@dataclass
class TypeSetMember:
    coin_type_id: int
    series: str
    year: int
    mint_mark: Optional[str] = None
    variety: Optional[str] = None
    is_proof: bool = False


@dataclass
class TypeSetProgress:
    coin_type_id: int
    series: str
    year: int
    mint_mark: Optional[str]
    variety: Optional[str]
    is_proof: bool
    qty_on_hand: int
    have_any: bool
    best_grade_company: Optional[str]
    best_grade_text: Optional[str]
    best_numeric_grade: Optional[float]
    has_slab_cert: bool
    required_grade_company: Optional[str]
    required_min_grade: Optional[str]
    required_max_grade: Optional[str]
    requires_slab: bool
    meets_requirements: bool


@dataclass
class TypeSetSummary:
    total_coins: int
    coins_owned: int
    coins_meeting_requirements: int
    percent_complete: float


@dataclass
class TypeSetValue:
    total_est_value: float
    total_cost: float


@dataclass
class CoinType:
    id: int
    series: str
    year: int
    mint_mark: Optional[str] = None
    variety: Optional[str] = None
    is_proof: bool = False
    country: Optional[str] = None
    denomination: Optional[str] = None


class TypeSetsDataRepository(ABC):
    """Abstract repository interface for Type Sets data access"""

    @abstractmethod
    def get_all_type_sets(self) -> List[TypeSet]:
        """Get all type sets"""
        pass

    @abstractmethod
    def get_type_set_by_id(self, set_id: int) -> Optional[TypeSet]:
        """Get a specific type set by ID"""
        pass

    @abstractmethod
    def create_type_set(self, name: str, description: Optional[str] = None,
                        metadata: Optional[Dict] = None) -> int:
        """Create a new type set, returns the new set ID"""
        pass

    @abstractmethod
    def update_type_set(self, set_id: int, name: str, description: Optional[str] = None) -> int:
        """Update an existing type set"""
        pass

    @abstractmethod
    def delete_type_set(self, set_id: int) -> int:
        """Delete a type set"""
        pass

    @abstractmethod
    def get_type_set_members(self, set_id: int) -> List[TypeSetMember]:
        """Get all members of a type set"""
        pass

    @abstractmethod
    def add_type_set_members(self, set_id: int, coin_type_ids: List[int]) -> int:
        """Add coins to a type set, returns number added"""
        pass

    @abstractmethod
    def remove_type_set_members(self, set_id: int, coin_type_ids: List[int]) -> int:
        """Remove coins from a type set, returns number removed"""
        pass

    @abstractmethod
    def get_type_set_progress(self, set_id: int) -> pd.DataFrame:
        """Get progress data for a type set"""
        pass

    @abstractmethod
    def get_type_set_summary(self, set_id: int) -> Optional[TypeSetSummary]:
        """Get summary statistics for a type set"""
        pass

    @abstractmethod
    def get_type_set_value_data(self, set_id: int) -> TypeSetValue:
        """Get value and cost data for a type set"""
        pass

    @abstractmethod
    def get_type_set_metadata(self, set_id: int) -> Dict[str, Any]:
        """Get metadata for a type set"""
        pass

    @abstractmethod
    def save_type_set_metadata(self, set_id: int, metadata: Dict[str, Any]) -> bool:
        """Save metadata for a type set"""
        pass

    @abstractmethod
    def get_type_set_upgrade_targets(self, set_id: int) -> List[Dict[str, Any]]:
        """Get coins that need upgrading in a type set"""
        pass

    @abstractmethod
    def get_type_set_best_candidates(self, set_id: int, coin_type_id: int) -> List[Dict[str, Any]]:
        """Get best candidate coins from inventory for a specific type set need"""
        pass

    @abstractmethod
    def search_coin_types(self, series: Optional[List[str]] = None,
                          year_range: Optional[Tuple[int, int]] = None,
                          proof_filter: str = "Any") -> List[CoinType]:
        """Search coin types with filters"""
        pass

    @abstractmethod
    def search_coin_types_catalog(self, series: Optional[List[str]] = None,
                                  year_range: Optional[Tuple[int, int]] = None,
                                  proof_filter: str = "Any",
                                  include_varieties: bool = False) -> List[CoinType]:
        """Search coin types catalog with filters"""
        pass

    @abstractmethod
    def get_all_series(self) -> List[str]:
        """Get all available series"""
        pass

    @abstractmethod
    def analyze_missing_coins(self, set_id: int) -> pd.DataFrame:
        """Get coins that are missing or don't meet requirements"""
        pass


class TypeSetsRepository(TypeSetsDataRepository):
    """Concrete implementation of TypeSets data repository"""

    def __init__(self, db_executor):
        self.db = db_executor

    def get_all_type_sets(self) -> List[TypeSet]:
        """Get all type sets with summary information."""
        query = """
            SELECT 
                s.set_id,
                s.name,
                s.description,
                s.total_coins,
                s.coins_owned,
                s.coins_meeting_requirements,
                s.percent_owned,
                s.percent_complete,
                s.grade_company,
                s.min_grade,
                s.max_grade,
                s.require_slab
            FROM v_type_set_summary s
            ORDER BY s.name
        """
        results = execute_query_all(query)

        type_sets = []
        for r in results:
            type_sets.append(TypeSet(
                id=r['set_id'],
                name=r['name'],
                description=r.get('description'),
                total_coins=r.get('total_coins', 0),
                coins_owned=r.get('coins_owned', 0),
                coins_meeting_requirements=r.get('coins_meeting_requirements', 0),
                percent_owned=r.get('percent_owned', 0.0),
                percent_complete=r.get('percent_complete', 0.0),
                grade_company=r.get('grade_company'),
                min_grade=r.get('min_grade'),
                max_grade=r.get('max_grade'),
                require_slab=bool(r.get('require_slab', False))
            ))

        return type_sets

    def get_type_set_by_id(self, set_id: int) -> Optional[TypeSet]:
        """Get a specific type set by ID"""
        query = "SELECT id, name, description FROM type_set WHERE id = ?"
        result = execute_query_single(query, (set_id,))
        if result:
            return TypeSet(
                id=result['id'],
                name=result['name'],
                description=result.get('description')
            )
        return None

    def create_type_set(self, name: str, description: Optional[str] = None,
                        metadata: Optional[Dict] = None) -> int:
        """Create a new type set with optional metadata."""
        if not name:
            raise ValueError("Set name is required")

        # Create the type set
        set_id = execute_insert(
            "INSERT INTO type_set(name, description) VALUES (?, ?)",
            (name, description)
        )

        # Create metadata record if provided
        if metadata:
            self.save_type_set_metadata(set_id, metadata)

        return set_id

    def update_type_set(self, set_id: int, name: str, description: Optional[str] = None) -> int:
        """Update type set basic information."""
        if not name:
            raise ValueError("Set name is required")

        query = "UPDATE type_set SET name=?, description=? WHERE id=?"
        rows = execute_update(query, (name, description, set_id))

        # Update modified date in metadata if it exists
        execute_update(
            "UPDATE type_set_metadata SET modified_date=? WHERE set_id=?",
            (datetime.now().isoformat(), set_id)
        )

        return rows

    def delete_type_set(self, set_id: int) -> int:
        """Delete a type set and all related data (cascade handles members and metadata)."""
        return execute_delete("DELETE FROM type_set WHERE id=?", (set_id,))

    def get_type_set_members(self, set_id: int) -> List[TypeSetMember]:
        """Get all members of a type set."""
        query = """
            SELECT 
                m.coin_type_id,
                cm.series,
                ct.year,
                ct.mint_mark,
                COALESCE(ct.variety,'') AS variety,
                ct.is_proof
            FROM type_set_member m
            JOIN coin_type ct ON ct.id = m.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE m.set_id = ?
            ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety
        """
        results = execute_query_all(query, (set_id,))
        return [TypeSetMember(**row) for row in results]

    def add_type_set_members(self, set_id: int, coin_type_ids: List[int]) -> int:
        """Add coin types to a type set."""
        if not coin_type_ids:
            return 0

        count = 0
        for coin_type_id in coin_type_ids:
            try:
                execute_insert(
                    "INSERT OR IGNORE INTO type_set_member(set_id, coin_type_id) VALUES (?, ?)",
                    (set_id, coin_type_id)
                )
                count += 1
            except Exception:
                pass  # Ignore duplicates

        # Update modified date
        execute_update(
            "UPDATE type_set_metadata SET modified_date=? WHERE set_id=?",
            (datetime.now().isoformat(), set_id)
        )

        return count

    def remove_type_set_members(self, set_id: int, coin_type_ids: List[int]) -> int:
        """Remove coin types from a type set."""
        if not coin_type_ids:
            return 0

        count = 0
        for coin_type_id in coin_type_ids:
            rows = execute_delete(
                "DELETE FROM type_set_member WHERE set_id=? AND coin_type_id=?",
                (set_id, coin_type_id)
            )
            count += rows

        # Update modified date
        execute_update(
            "UPDATE type_set_metadata SET modified_date=? WHERE set_id=?",
            (datetime.now().isoformat(), set_id)
        )

        return count

    def get_type_set_progress(self, set_id: int) -> pd.DataFrame:
        """Get detailed progress for a type set using the new view."""
        query = """
            SELECT 
                coin_type_id,
                series,
                year,
                mint_mark,
                variety,
                is_proof,
                qty_on_hand,
                have_any,
                best_grade_company,
                best_grade_text,
                best_numeric_grade,
                has_slab_cert,
                required_grade_company,
                required_min_grade,
                required_max_grade,
                requires_slab,
                meets_requirements
            FROM v_type_set_progress_detailed
            WHERE set_id = ?
            ORDER BY series, year, mint_mark, variety
        """

        rows = execute_query_all(query, (set_id,))
        return pd.DataFrame(rows)

    def get_type_set_summary(self, set_id: int) -> Optional[TypeSetSummary]:
        """Get summary statistics for a type set."""
        query = "SELECT * FROM v_type_set_summary WHERE set_id = ?"
        result = execute_query_single(query, (set_id,))

        if result:
            return TypeSetSummary(
                total_coins=result.get('total_coins', 0),
                coins_owned=result.get('coins_owned', 0),
                coins_meeting_requirements=result.get('coins_meeting_requirements', 0),
                percent_complete=result.get('percent_complete', 0.0)
            )
        return None

    def get_type_set_value_data(self, set_id: int) -> TypeSetValue:
        """Get value and cost data for a type set"""
        query = """
            SELECT 
                COALESCE(SUM(l.qty_remaining * v.chosen_unit_value), 0) as total_est_value,
                COALESCE(SUM(l.qty_remaining * l.unit_cost), 0) as total_cost
            FROM type_set_member tsm
            JOIN lot l ON l.coin_type_id = tsm.coin_type_id AND l.qty_remaining > 0
            LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
            WHERE tsm.set_id = ?
        """
        result = execute_query_single(query, (set_id,))

        if result:
            return TypeSetValue(
                total_est_value=result.get('total_est_value', 0),
                total_cost=result.get('total_cost', 0)
            )
        return TypeSetValue(total_est_value=0, total_cost=0)

    def get_type_set_metadata(self, set_id: int) -> Dict[str, Any]:
        """Get metadata/criteria for a type set."""
        query = "SELECT * FROM type_set_metadata WHERE set_id=?"
        result = execute_query_single(query, (set_id,))

        if not result:
            return {}

        # Convert to more friendly format
        return {
            'grade_company': result['grade_company'],
            'min_grade': result['min_grade'],
            'max_grade': result['max_grade'],
            'min_numeric_grade': result['min_numeric_grade'],
            'max_numeric_grade': result['max_numeric_grade'],
            'require_slab': bool(result['require_slab']),
            'require_cac': bool(result['require_cac']),
            'proof_only': bool(result['proof_only']),
            'business_only': bool(result['business_only']),
            'include_varieties': bool(result['include_varieties']),
            'year_start': result['year_start'],
            'year_end': result['year_end'],
            'created_date': result['created_date'],
            'modified_date': result['modified_date']
        }

    def save_type_set_metadata(self, set_id: int, metadata: Dict[str, Any]) -> bool:
        """Save or update type set metadata/criteria."""
        from presentation.components.helpers.type_sets_helpers import get_grade_numeric_value

        # Convert grade text to numeric if needed
        min_numeric = None
        max_numeric = None

        if metadata.get('min_grade'):
            min_numeric = get_grade_numeric_value(metadata['min_grade'])
        if metadata.get('max_grade'):
            max_numeric = get_grade_numeric_value(metadata['max_grade'])

        # Check if metadata exists
        existing = execute_query_single(
            "SELECT set_id FROM type_set_metadata WHERE set_id=?",
            (set_id,)
        )

        if existing:
            # Update existing
            query = """
                UPDATE type_set_metadata SET
                    grade_company=?, min_grade=?, max_grade=?,
                    min_numeric_grade=?, max_numeric_grade=?,
                    require_slab=?, require_cac=?,
                    proof_only=?, business_only=?,
                    include_varieties=?, year_start=?, year_end=?,
                    modified_date=?
                WHERE set_id=?
            """
            params = (
                metadata.get('grade_company'),
                metadata.get('min_grade'),
                metadata.get('max_grade'),
                min_numeric,
                max_numeric,
                1 if metadata.get('require_slab') else 0,
                1 if metadata.get('require_cac') else 0,
                1 if metadata.get('proof_only') else 0,
                1 if metadata.get('business_only') else 0,
                1 if metadata.get('include_varieties', True) else 0,
                metadata.get('year_start'),
                metadata.get('year_end'),
                datetime.now().isoformat(),
                set_id
            )
            execute_update(query, params)
        else:
            # Insert new
            query = """
                INSERT INTO type_set_metadata(
                    set_id, grade_company, min_grade, max_grade,
                    min_numeric_grade, max_numeric_grade,
                    require_slab, require_cac, proof_only, business_only,
                    include_varieties, year_start, year_end,
                    created_date, modified_date
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """
            params = (
                set_id,
                metadata.get('grade_company'),
                metadata.get('min_grade'),
                metadata.get('max_grade'),
                min_numeric,
                max_numeric,
                1 if metadata.get('require_slab') else 0,
                1 if metadata.get('require_cac') else 0,
                1 if metadata.get('proof_only') else 0,
                1 if metadata.get('business_only') else 0,
                1 if metadata.get('include_varieties', True) else 0,
                metadata.get('year_start'),
                metadata.get('year_end'),
                datetime.now().isoformat(),
                datetime.now().isoformat()
            )
            execute_insert(query, params)

        return True

    def get_type_set_upgrade_targets(self, set_id: int) -> List[Dict[str, Any]]:
        """Get coins that need upgrading to meet set requirements."""
        query = """
            SELECT * FROM v_type_set_upgrade_targets
            WHERE set_id = ?
            ORDER BY series, year, mint_mark
        """
        return execute_query_all(query, (set_id,))

    def get_type_set_best_candidates(self, set_id: int, coin_type_id: int) -> List[Dict[str, Any]]:
        """Get best candidate coins from inventory for a specific type set need."""
        query = """
            SELECT * FROM v_type_set_best_candidates
            WHERE set_id = ? AND coin_type_id = ?
            ORDER BY match_score DESC
            LIMIT 5
        """
        return execute_query_all(query, (set_id, coin_type_id))

    def search_coin_types_catalog(self, series: Optional[List[str]] = None,
                                  year_range: Optional[Tuple[int, int]] = None,
                                  proof_filter: str = "Any",
                                  include_varieties: bool = True) -> List[CoinType]:
        """
        Search the coin catalog (all coin_types, not just what's on hand).
        This is used to define what SHOULD be in a type set.
        """
        conditions = []
        params = []

        # Series filter
        if series:
            placeholders = ",".join("?" for _ in series)
            conditions.append(f"cm.series IN ({placeholders})")
            params.extend(series)

        # Year range filter
        if year_range:
            start, end = year_range
            conditions.append("ct.year BETWEEN ? AND ?")
            params.extend([start, end])

        # Proof filter
        if proof_filter == "Proofs only":
            conditions.append("ct.is_proof = 1")
        elif proof_filter == "Business strikes only":
            conditions.append("(ct.is_proof IS NULL OR ct.is_proof = 0)")

        # Variety filter
        if not include_varieties:
            conditions.append("(ct.variety IS NULL OR ct.variety = '')")

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
            SELECT 
                ct.id,
                cm.series,
                ct.year,
                ct.mint_mark,
                COALESCE(ct.variety, '') AS variety,
                ct.is_proof,
                cm.country,
                cm.denomination
            FROM coin_type ct
            JOIN coin_master cm ON cm.id = ct.master_id
            {where_clause}
            ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety
        """

        results = execute_query_all(query, tuple(params))
        return [CoinType(**row) for row in results]

    def search_coin_types(self, series: Optional[List[str]] = None,
                          year_range: Optional[Tuple[int, int]] = None,
                          proof_filter: str = "Any") -> List[CoinType]:
        """Basic search for coin types (backward compatibility)."""
        return self.search_coin_types_catalog(series, year_range, proof_filter, True)

    def get_all_series(self) -> List[str]:
        """Get all unique series from coin masters."""
        query = "SELECT DISTINCT series FROM coin_master ORDER BY series"
        results = execute_query_all(query)
        return [r['series'] for r in results]

    def analyze_missing_coins(self, set_id: int) -> pd.DataFrame:
        """Get coins that are missing or don't meet requirements."""
        query = """
            SELECT 
                coin_type_id,
                series,
                year,
                mint_mark,
                variety,
                CASE 
                    WHEN qty_on_hand = 0 THEN 'Need to acquire'
                    WHEN NOT meets_requirements THEN upgrade_needed
                    ELSE NULL
                END as status
            FROM v_type_set_progress_detailed p
            LEFT JOIN v_type_set_upgrade_targets u 
                ON u.set_id = p.set_id AND u.coin_type_id = p.coin_type_id
            WHERE p.set_id = ? AND (p.qty_on_hand = 0 OR p.meets_requirements = 0)
            ORDER BY series, year, mint_mark
        """

        rows = execute_query_all(query, (set_id,))
        return pd.DataFrame(rows)
