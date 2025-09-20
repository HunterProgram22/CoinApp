# infrastructure/database/repositories/admin_repository.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd


@dataclass
class CoinMaster:
    """Coin master data"""
    id: int
    country: str
    denomination: str
    series: str
    metal: Optional[str] = None
    fineness: Optional[float] = None
    weight_grams: Optional[float] = None
    diameter_mm: Optional[float] = None
    thickness_mm: Optional[float] = None
    edge: Optional[str] = None
    years_start: Optional[int] = None
    years_end: Optional[int] = None
    asset_category: str = 'COIN'
    numista_url: Optional[str] = None
    ngc_url: Optional[str] = None
    pcgs_url: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class CoinType:
    """Coin type data"""
    id: int
    master_id: int
    country: str
    denomination: str
    series: str
    year: int
    mint_mark: str = ''
    variety: str = ''
    mintage: Optional[int] = None
    is_proof: bool = False


@dataclass
class MetalPrice:
    """Metal price data"""
    metal: str
    price_per_oz_usd: float
    quoted_at_utc: str


@dataclass
class Transaction:
    """Transaction summary for maintenance"""
    id: int
    tx_date: str
    tx_type: str
    party: Optional[str]
    currency: str
    shipping: float
    tax: float
    fees: float


@dataclass
class Lot:
    """Lot data for maintenance"""
    id: int
    series: str
    year: int
    qty_acquired: int
    qty_remaining: int
    acquired_date: str


class AdminDataRepository(ABC):
    """Abstract interface for admin data access"""

    # Coin Master operations
    @abstractmethod
    def get_coin_masters(self) -> List[CoinMaster]:
        """Get all coin masters"""
        pass

    @abstractmethod
    def create_coin_master(self, master: CoinMaster) -> int:
        """Create a new coin master"""
        pass

    @abstractmethod
    def update_coin_master(self, master: CoinMaster) -> int:
        """Update an existing coin master"""
        pass

    # Coin Type operations
    @abstractmethod
    def get_coin_types(self) -> List[CoinType]:
        """Get all coin types with master info"""
        pass

    @abstractmethod
    def create_coin_type(self, coin_type: CoinType) -> int:
        """Create a new coin type"""
        pass

    @abstractmethod
    def update_coin_type(self, coin_type: CoinType) -> int:
        """Update an existing coin type"""
        pass

    # Metal Price operations
    @abstractmethod
    def get_latest_metal_prices(self) -> List[MetalPrice]:
        """Get latest metal prices"""
        pass

    @abstractmethod
    def create_metal_price(self, price: MetalPrice) -> int:
        """Add a new metal price"""
        pass

    # Maintenance operations
    @abstractmethod
    def get_recent_transactions(self, limit: int = 100) -> List[Transaction]:
        """Get recent transactions for maintenance"""
        pass

    @abstractmethod
    def void_transaction(self, tx_id: int) -> int:
        """Void (delete) a transaction"""
        pass

    @abstractmethod
    def get_open_lots(self) -> List[Lot]:
        """Get open lots for maintenance"""
        pass

    @abstractmethod
    def delete_lot(self, lot_id: int) -> bool:
        """Delete a lot if no relief records exist"""
        pass


    @abstractmethod
    def delete_coin_type(self, type_id: int) -> bool:
        """Delete a coin type if no lots exist"""
        pass

    # Database operations
    @abstractmethod
    def reset_database(self) -> bool:
        """Reset the database"""
        pass


class AdminRepository(AdminDataRepository):
    """Concrete implementation of admin repository"""

    def __init__(self, db_executor):
        self.db = db_executor

    def get_coin_masters(self) -> List[CoinMaster]:
        """Get all coin masters"""
        try:
            from infrastructure.database.db_operations import execute_query_all

            query = """
                SELECT id, country, denomination, series, metal, fineness, weight_grams,
                    diameter_mm, thickness_mm, edge, 
                    years_start, years_end, asset_category,
                    numista_url, ngc_url, pcgs_url, notes
                FROM coin_master
                ORDER BY country, denomination, series
            """
            results = execute_query_all(query)

            masters = []
            for r in results:
                masters.append(CoinMaster(
                    id=r['id'],
                    country=r['country'],
                    denomination=r['denomination'],
                    series=r['series'],
                    metal=r.get('metal'),
                    fineness=float(r['fineness']) if r.get('fineness') else None,
                    weight_grams=float(r['weight_grams']) if r.get('weight_grams') else None,
                    diameter_mm=float(r['diameter_mm']) if r.get('diameter_mm') else None,
                    thickness_mm=float(r['thickness_mm']) if r.get('thickness_mm') else None,
                    edge=r.get('edge'),
                    years_start=r.get('years_start'),
                    years_end=r.get('years_end'),
                    asset_category=r.get('asset_category', 'COIN'),
                    numista_url=r.get('numista_url'),
                    ngc_url=r.get('ngc_url'),
                    pcgs_url=r.get('pcgs_url'),
                    notes=r.get('notes')
                ))
            return masters
        except Exception as e:
            print(f"Error getting coin masters: {e}")
            return []

    def create_coin_master(self, master: CoinMaster) -> int:
        """Create a new coin master"""
        try:
            from core.queries import create_or_update_coin_master

            return create_or_update_coin_master(
                master.country, master.denomination, master.series,
                metal=master.metal,
                fineness=master.fineness,
                weight_grams=master.weight_grams,
                diameter_mm=master.diameter_mm,
                thickness_mm=master.thickness_mm,
                edge=master.edge,
                years_start=master.years_start,
                years_end=master.years_end,
                asset_category=master.asset_category,
                numista_url=master.numista_url,
                ngc_url=master.ngc_url,
                pcgs_url=master.pcgs_url,
                notes=master.notes
            )
        except Exception as e:
            print(f"Error creating coin master: {e}")
            raise

    def update_coin_master(self, master: CoinMaster) -> int:
        """Update an existing coin master"""
        try:
            from infrastructure.database.db_operations import execute_update

            query = """
                UPDATE coin_master
                SET country=?, denomination=?, series=?, metal=?, fineness=?, 
                    weight_grams=?, diameter_mm=?, thickness_mm=?, edge=?,
                    years_start=?, years_end=?, asset_category=?, 
                    numista_url=?, ngc_url=?, pcgs_url=?, notes=?
                WHERE id=?
            """
            params = (
                master.country,
                master.denomination,
                master.series,
                master.metal,
                master.fineness or 0.0,
                master.weight_grams or 0.0,
                master.diameter_mm or 0.0,
                master.thickness_mm or 0.0,
                master.edge,
                master.years_start or 0,
                master.years_end or 0,
                master.asset_category,
                master.numista_url,
                master.ngc_url,
                master.pcgs_url,
                master.notes,
                master.id
            )
            return execute_update(query, params)
        except Exception as e:
            print(f"Error updating coin master: {e}")
            raise

    def get_coin_types(self) -> List[CoinType]:
        """Get all coin types with master info"""
        try:
            from infrastructure.database.db_operations import execute_query_all

            query = """
                SELECT ct.id, cm.country, cm.denomination, cm.series, ct.year,
                       COALESCE(ct.mint_mark,'') AS mint_mark, 
                       COALESCE(ct.variety,'') AS variety,
                       ct.mintage, ct.is_proof, ct.master_id
                FROM coin_type ct
                JOIN coin_master cm ON cm.id = ct.master_id
                ORDER BY cm.country, cm.denomination, cm.series, ct.year, ct.mint_mark, ct.variety
            """
            results = execute_query_all(query)

            types = []
            for r in results:
                types.append(CoinType(
                    id=r['id'],
                    master_id=r['master_id'],
                    country=r['country'],
                    denomination=r['denomination'],
                    series=r['series'],
                    year=r['year'],
                    mint_mark=r['mint_mark'] or '',
                    variety=r['variety'] or '',
                    mintage=r.get('mintage'),
                    is_proof=bool(r.get('is_proof'))
                ))
            return types
        except Exception as e:
            print(f"Error getting coin types: {e}")
            return []

    def create_coin_type(self, coin_type: CoinType) -> int:
        """Create a new coin type"""
        try:
            from core.queries import create_or_update_coin_type

            return create_or_update_coin_type(
                coin_type.master_id,
                coin_type.year,
                coin_type.mint_mark,
                coin_type.variety,
                mintage=coin_type.mintage,
                is_proof=1 if coin_type.is_proof else 0
            )
        except Exception as e:
            print(f"Error creating coin type: {e}")
            raise

    def delete_coin_type(self, type_id: int) -> bool:
        """Delete a coin type if no lots exist"""
        try:
            from infrastructure.database.db_operations import execute_query_single, execute_delete

            # Check if any lots exist for this coin type
            lot_check = execute_query_single(
                "SELECT COUNT(*) as count FROM lot WHERE coin_type_id=?",
                (type_id,)
            )

            if lot_check and lot_check['count'] > 0:
                return False  # Cannot delete - lots exist

            execute_delete("DELETE FROM coin_type WHERE id=?", (type_id,))
            return True
        except Exception as e:
            print(f"Error deleting coin type: {e}")
            raise

    def update_coin_type(self, coin_type: CoinType) -> int:
        """Update an existing coin type"""
        try:
            from infrastructure.database.db_operations import execute_update

            query = """
                UPDATE coin_type
                SET year=?, mint_mark=?, variety=?, mintage=?, is_proof=?
                WHERE id=?
            """
            params = (
                coin_type.year,
                coin_type.mint_mark or '',
                coin_type.variety or '',
                coin_type.mintage or 0,
                1 if coin_type.is_proof else 0,
                coin_type.id
            )
            return execute_update(query, params)
        except Exception as e:
            print(f"Error updating coin type: {e}")
            raise

    def get_latest_metal_prices(self) -> List[MetalPrice]:
        """Get latest metal prices"""
        try:
            from core.queries import get_latest_metal_prices

            results = get_latest_metal_prices()
            prices = []
            for r in results:
                prices.append(MetalPrice(
                    metal=r['metal'],
                    price_per_oz_usd=float(r['price_per_oz_usd']),
                    quoted_at_utc=r.get('quoted_at_utc', '')
                ))
            return prices
        except Exception as e:
            print(f"Error getting metal prices: {e}")
            return []

    def create_metal_price(self, price: MetalPrice) -> int:
        """Add a new metal price"""
        try:
            from core.queries import create_metal_price

            return create_metal_price(
                price.metal,
                price.price_per_oz_usd,
                price.quoted_at_utc
            )
        except Exception as e:
            print(f"Error creating metal price: {e}")
            raise

    def get_recent_transactions(self, limit: int = 100) -> List[Transaction]:
        """Get recent transactions for maintenance"""
        try:
            from core.queries import get_recent_transactions

            results = get_recent_transactions(limit)
            transactions = []
            for r in results:
                transactions.append(Transaction(
                    id=r['id'],
                    tx_date=r['tx_date'],
                    tx_type=r['tx_type'],
                    party=r.get('party'),
                    currency=r.get('currency', 'USD'),
                    shipping=float(r.get('shipping', 0)),
                    tax=float(r.get('tax', 0)),
                    fees=float(r.get('fees', 0))
                ))
            return transactions
        except Exception as e:
            print(f"Error getting transactions: {e}")
            return []

    def void_transaction(self, tx_id: int) -> int:
        """Void (delete) a transaction"""
        try:
            from infrastructure.database.db_operations import execute_delete

            return execute_delete("DELETE FROM tx WHERE id=?", (tx_id,))
        except Exception as e:
            print(f"Error voiding transaction: {e}")
            raise

    def get_open_lots(self) -> List[Lot]:
        """Get open lots for maintenance"""
        try:
            from core.queries import get_open_lots

            results = get_open_lots()
            lots = []
            for r in results:
                lots.append(Lot(
                    id=r['id'],
                    series=r['series'],
                    year=r['year'],
                    qty_acquired=r['qty_acquired'],
                    qty_remaining=r['qty_remaining'],
                    acquired_date=r['acquired_date']
                ))
            return lots
        except Exception as e:
            print(f"Error getting lots: {e}")
            return []

    def delete_lot(self, lot_id: int) -> bool:
        """Delete a lot if no relief records exist"""
        try:
            from infrastructure.database.db_operations import execute_query_single, execute_delete

            # Check for relief records
            relief_check = execute_query_single(
                "SELECT COUNT(*) as count FROM lot_relief WHERE lot_id=?",
                (lot_id,)
            )

            if relief_check and relief_check['count'] > 0:
                return False  # Cannot delete

            execute_delete("DELETE FROM lot WHERE id=?", (lot_id,))
            return True
        except Exception as e:
            print(f"Error deleting lot: {e}")
            raise

    def reset_database(self) -> bool:
        """Reset the database"""
        try:
            import os
            from infrastructure.database.db import init_db, DB_PATH

            if os.path.exists(DB_PATH):
                os.remove(DB_PATH)
            init_db()
            return True
        except Exception as e:
            print(f"Error resetting database: {e}")
            raise
