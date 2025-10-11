# infrastructure/database/repositories/transaction_repository.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple
from datetime import date
import pandas as pd


@dataclass
class TransactionHeader:
    """Transaction header data"""
    id: int
    tx_date: str
    tx_type: str
    party_name: str
    currency: str
    shipping: float
    tax: float
    fees: float
    notes: Optional[str]
    party_id: Optional[int] = None
    line_count: Optional[int] = None
    total_quantity: Optional[int] = None


@dataclass
class TransactionLine:
    """Transaction line item data"""
    line_id: int
    coin_type_id: int
    series: str
    year: int
    mint_mark: Optional[str]
    variety: Optional[str]
    quantity: int
    unit_price: float
    grade_company: Optional[str] = None
    grade_text: Optional[str] = None
    numeric_grade: Optional[float] = None
    slab_cert: Optional[str] = None
    condition_notes: Optional[str] = None
    # Additional fields for BUY transactions
    lot_id: Optional[int] = None
    qty_remaining: Optional[int] = None
    unit_cost: Optional[float] = None
    estimated_grade_text: Optional[str] = None
    estimated_numeric_grade: Optional[float] = None
    valuation_method: Optional[str] = None
    manual_est_unit_value: Optional[float] = None
    storage_location_id: Optional[int] = None
    storage_name: Optional[str] = None
    lot_notes: Optional[str] = None
    is_proof: Optional[bool] = None


@dataclass
class InventoryLot:
    """Inventory lot details for availability checking"""
    lot_id: int
    qty_remaining: int
    acquired_date: str
    series: str
    year: int
    mint_mark: Optional[str]
    variety: Optional[str]


class TransactionDataRepository(ABC):
    """Abstract interface for transaction data access"""

    @abstractmethod
    def get_parties(self) -> List[str]:
        """Get list of unique parties"""
        pass

    @abstractmethod
    def search_transactions(self, date_from: Optional[date], date_to: Optional[date],
                            tx_types: Optional[List[str]], party: Optional[str],
                            search_text: Optional[str]) -> pd.DataFrame:
        """Search transactions with filters"""
        pass

    @abstractmethod
    def search_transactions_for_edit(self, date_from: Optional[date], date_to: Optional[date],
                                     tx_types: Optional[List[str]], party: Optional[str],
                                     search_text: Optional[str]) -> List[TransactionHeader]:
        """Search transactions for editing with filters"""
        pass

    @abstractmethod
    def check_inventory_availability(self, coin_type_id: int,
                                     quantity: int) -> Tuple[bool, str, List[InventoryLot]]:
        """Check if enough inventory is available for sale"""
        pass

    @abstractmethod
    def get_recent_transactions(self, limit: int = 100) -> List[TransactionHeader]:
        """Get recent transactions for editing"""
        pass

    @abstractmethod
    def get_transaction_details(self, tx_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed transaction information"""
        pass

    @abstractmethod
    def update_transaction_header(self, tx_id: int, header: TransactionHeader) -> bool:
        """Update transaction header information"""
        pass

    @abstractmethod
    def update_coin_type_proof_status(self, coin_type_id: int, is_proof: bool) -> bool:
        """Update proof status of a coin type"""
        pass

    @abstractmethod
    def update_item_details(self, line_id: int, lot_id: Optional[int],
                            updates: Dict[str, Any]) -> bool:
        """Update transaction line and lot details"""
        pass


class TransactionRepository(TransactionDataRepository):
    """Concrete implementation of transaction repository"""

    def __init__(self, db_executor):
        self.db = db_executor

    def get_parties(self) -> List[str]:
        """Get list of unique parties from transactions"""
        try:
            from infrastructure.database.db_operations import execute_query_all

            query = """
                SELECT DISTINCT COALESCE(p.name, '') AS party
                FROM tx t 
                LEFT JOIN party p ON p.id = t.party_id
                WHERE COALESCE(p.name, '') <> ''
                ORDER BY party
            """
            results = execute_query_all(query)
            return [r['party'] for r in results] if results else []
        except Exception as e:
            print(f"Error getting parties: {e}")
            return []

    def search_transactions(self, date_from: Optional[date] = None,
                            date_to: Optional[date] = None,
                            tx_types: Optional[List[str]] = None,
                            party: Optional[str] = None,
                            search_text: Optional[str] = None) -> pd.DataFrame:
        """Search transactions with filters"""
        try:
            from infrastructure.database.db_operations import execute_query_all

            conditions = []
            params = []

            if date_from and date_to:
                conditions.append("DATE(t.tx_date) BETWEEN DATE(?) AND DATE(?)")
                params.extend([date_from.isoformat(), date_to.isoformat()])

            if tx_types and len(tx_types) < 2:  # Only filter if not both BUY and SELL
                conditions.append("t.tx_type = ?")
                params.append(tx_types[0])

            if party:
                conditions.append("COALESCE(p.name, '') = ?")
                params.append(party)

            if search_text:
                search_pattern = f"%{search_text.strip()}%"
                conditions.append(
                    "(cm.series LIKE ? OR ct.variety LIKE ? OR "
                    "COALESCE(p.name, '') LIKE ? OR COALESCE(t.notes, '') LIKE ?)"
                )
                params.extend([search_pattern] * 4)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            query = f"""
                SELECT
                    t.id AS tx_id,
                    t.tx_date,
                    t.tx_type,
                    COALESCE(p.name, '') AS party,
                    cm.country,
                    cm.denomination,
                    cm.series,
                    ct.year,
                    ct.mint_mark,
                    COALESCE(ct.variety, '') AS variety,
                    tl.quantity,
                    tl.unit_price,
                    t.currency,
                    t.shipping,
                    t.tax,
                    t.fees,
                    COALESCE(t.notes, '') AS tx_notes
                FROM tx t
                JOIN tx_line tl ON tl.tx_id = t.id
                LEFT JOIN party p ON p.id = t.party_id
                LEFT JOIN coin_type ct ON ct.id = tl.coin_type_id
                LEFT JOIN coin_master cm ON cm.id = ct.master_id
                {where_clause}
                ORDER BY DATE(t.tx_date) DESC, t.id DESC, tl.id ASC
            """

            results = execute_query_all(query, tuple(params))
            return pd.DataFrame(results) if results else pd.DataFrame()
        except Exception as e:
            print(f"Error searching transactions: {e}")
            return pd.DataFrame()

    def search_transactions_for_edit(self, date_from: Optional[date] = None,
                                     date_to: Optional[date] = None,
                                     tx_types: Optional[List[str]] = None,
                                     party: Optional[str] = None,
                                     search_text: Optional[str] = None) -> List[TransactionHeader]:
        """Search transactions for editing with filters"""
        try:
            from infrastructure.database.db_operations import execute_query_all

            conditions = []
            params = []

            if date_from and date_to:
                conditions.append("DATE(t.tx_date) BETWEEN DATE(?) AND DATE(?)")
                params.extend([date_from.isoformat(), date_to.isoformat()])

            if tx_types and len(tx_types) < 2:  # Only filter if not both BUY and SELL
                conditions.append("t.tx_type = ?")
                params.append(tx_types[0])

            if party:
                conditions.append("COALESCE(p.name, '') = ?")
                params.append(party)

            if search_text:
                search_pattern = f"%{search_text.strip()}%"
                conditions.append(
                    "(cm.series LIKE ? OR ct.variety LIKE ? OR "
                    "COALESCE(p.name, '') LIKE ? OR COALESCE(t.notes, '') LIKE ?)"
                )
                params.extend([search_pattern] * 4)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            query = f"""
                SELECT 
                    t.id, t.tx_date, t.tx_type, 
                    COALESCE(p.name, '') AS party,
                    t.currency, t.shipping, t.tax, t.fees, t.notes,
                    COUNT(DISTINCT tl.id) AS line_count,
                    SUM(ABS(tl.quantity)) AS total_quantity
                FROM tx t
                LEFT JOIN party p ON p.id = t.party_id
                LEFT JOIN tx_line tl ON tl.tx_id = t.id
                LEFT JOIN coin_type ct ON ct.id = tl.coin_type_id
                LEFT JOIN coin_master cm ON cm.id = ct.master_id
                {where_clause}
                GROUP BY t.id, t.tx_date, t.tx_type, p.name, t.currency, 
                         t.shipping, t.tax, t.fees, t.notes
                ORDER BY t.tx_date DESC, t.id DESC
            """

            results = execute_query_all(query, tuple(params))

            transactions = []
            for r in results:
                transactions.append(TransactionHeader(
                    id=r['id'],
                    tx_date=r['tx_date'],
                    tx_type=r['tx_type'],
                    party_name=r['party'] or '',
                    currency=r['currency'],
                    shipping=float(r['shipping'] or 0),
                    tax=float(r['tax'] or 0),
                    fees=float(r['fees'] or 0),
                    notes=r['notes'],
                    line_count=r['line_count'],
                    total_quantity=r['total_quantity']
                ))

            return transactions
        except Exception as e:
            print(f"Error searching transactions for edit: {e}")
            return []

    def check_inventory_availability(self, coin_type_id: int,
                                     quantity: int) -> Tuple[bool, str, List[InventoryLot]]:
        """Check if enough inventory is available for sale and return lot details"""
        try:
            from infrastructure.database.db_operations import execute_query_all

            query = """
                SELECT 
                    l.id as lot_id,
                    l.qty_remaining,
                    l.acquired_date,
                    cm.series,
                    ct.year,
                    ct.mint_mark,
                    ct.variety
                FROM lot l
                JOIN coin_type ct ON ct.id = l.coin_type_id
                JOIN coin_master cm ON cm.id = ct.master_id
                WHERE l.coin_type_id = ? AND l.qty_remaining > 0
                ORDER BY l.acquired_date ASC, l.id ASC
            """

            results = execute_query_all(query, (coin_type_id,))

            lots = []
            for r in results:
                lots.append(InventoryLot(
                    lot_id=r['lot_id'],
                    qty_remaining=r['qty_remaining'],
                    acquired_date=r['acquired_date'],
                    series=r['series'],
                    year=r['year'],
                    mint_mark=r['mint_mark'],
                    variety=r['variety']
                ))

            total_available = sum(lot.qty_remaining for lot in lots)

            if total_available < quantity:
                if lots:
                    coin_desc = f"{lots[0].series} {lots[0].year}"
                    if lots[0].mint_mark:
                        coin_desc += f" {lots[0].mint_mark}"
                    if lots[0].variety:
                        coin_desc += f" • {lots[0].variety}"
                else:
                    coin_desc = f"coin_type_id {coin_type_id}"

                return False, f"Insufficient inventory: Only {total_available} available for {coin_desc}, but trying to sell {quantity}", lots

            return True, "", lots
        except Exception as e:
            print(f"Error checking inventory: {e}")
            return False, f"Error checking inventory: {e}", []

    def get_recent_transactions(self, limit: int = 100) -> List[TransactionHeader]:
        """Get recent transactions for editing"""
        try:
            from infrastructure.database.db_operations import execute_query_all

            query = """
                SELECT 
                    t.id, t.tx_date, t.tx_type, 
                    COALESCE(p.name, '') AS party,
                    t.currency, t.shipping, t.tax, t.fees, t.notes,
                    COUNT(tl.id) AS line_count,
                    SUM(ABS(tl.quantity)) AS total_quantity
                FROM tx t
                LEFT JOIN party p ON p.id = t.party_id
                LEFT JOIN tx_line tl ON tl.tx_id = t.id
                GROUP BY t.id, t.tx_date, t.tx_type, p.name, t.currency, 
                         t.shipping, t.tax, t.fees, t.notes
                ORDER BY t.tx_date DESC, t.id DESC
                LIMIT ?
            """

            results = execute_query_all(query, (limit,))

            transactions = []
            for r in results:
                transactions.append(TransactionHeader(
                    id=r['id'],
                    tx_date=r['tx_date'],
                    tx_type=r['tx_type'],
                    party_name=r['party'] or '',
                    currency=r['currency'],
                    shipping=float(r['shipping'] or 0),
                    tax=float(r['tax'] or 0),
                    fees=float(r['fees'] or 0),
                    notes=r['notes'],
                    line_count=r['line_count'],
                    total_quantity=r['total_quantity']
                ))

            return transactions
        except Exception as e:
            print(f"Error getting recent transactions: {e}")
            return []

    def get_transaction_details(self, tx_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed transaction information"""
        try:
            from infrastructure.database.db_operations import execute_query_single, \
                execute_query_all

            # Get header info
            header_query = """
                SELECT 
                    t.id, t.tx_date, t.tx_type, t.party_id,
                    COALESCE(p.name, '') AS party_name,
                    t.currency, t.shipping, t.tax, t.fees, t.notes
                FROM tx t
                LEFT JOIN party p ON p.id = t.party_id
                WHERE t.id = ?
            """
            header = execute_query_single(header_query, (tx_id,))

            if not header:
                return None

            # Get line items with lot info for BUY transactions
            if header['tx_type'] == 'BUY':
                items_query = """
                    SELECT 
                        tl.id AS line_id,
                        tl.coin_type_id,
                        cm.series, 
                        ct.year, 
                        ct.mint_mark, 
                        COALESCE(ct.variety, '') AS variety,
                        ct.is_proof,
                        tl.quantity,
                        tl.unit_price,
                        tl.grade_company AS purchase_grade_company,
                        tl.grade_text AS purchase_grade_text,
                        tl.numeric_grade AS purchase_numeric_grade,
                        tl.slab_cert,
                        tl.condition_notes,
                        l.id AS lot_id,
                        l.qty_remaining,
                        l.unit_cost,
                        l.estimated_grade_text,
                        l.estimated_numeric_grade,
                        l.valuation_method,
                        l.manual_est_unit_value,
                        l.storage_location_id,
                        COALESCE(sl.name, '') AS storage_name,
                        l.notes AS lot_notes
                    FROM tx_line tl
                    JOIN coin_type ct ON ct.id = tl.coin_type_id
                    JOIN coin_master cm ON cm.id = ct.master_id
                    LEFT JOIN lot l ON l.acquisition_line_id = tl.id
                    LEFT JOIN storage_location sl ON sl.id = l.storage_location_id
                    WHERE tl.tx_id = ?
                    ORDER BY tl.id
                """
            else:
                # SELL transactions don't have lot details to edit
                items_query = """
                    SELECT 
                        tl.id AS line_id,
                        tl.coin_type_id,
                        cm.series, 
                        ct.year, 
                        ct.mint_mark, 
                        COALESCE(ct.variety, '') AS variety,
                        ct.is_proof,
                        tl.quantity,
                        tl.unit_price,
                        tl.grade_company AS purchase_grade_company,
                        tl.grade_text AS purchase_grade_text,
                        tl.numeric_grade AS purchase_numeric_grade,
                        tl.slab_cert,
                        tl.condition_notes
                    FROM tx_line tl
                    JOIN coin_type ct ON ct.id = tl.coin_type_id
                    JOIN coin_master cm ON cm.id = ct.master_id
                    WHERE tl.tx_id = ?
                    ORDER BY tl.id
                """

            items = execute_query_all(items_query, (tx_id,))

            # Convert to TransactionLine objects
            lines = []
            for item in items:
                lines.append(TransactionLine(
                    line_id=item['line_id'],
                    coin_type_id=item['coin_type_id'],
                    series=item['series'],
                    year=item['year'],
                    mint_mark=item.get('mint_mark'),
                    variety=item.get('variety'),
                    quantity=abs(item['quantity']),
                    unit_price=float(item['unit_price'] or 0),
                    grade_company=item.get('purchase_grade_company'),
                    grade_text=item.get('purchase_grade_text'),
                    numeric_grade=float(item['purchase_numeric_grade']) if item.get(
                        'purchase_numeric_grade') else None,
                    slab_cert=item.get('slab_cert'),
                    condition_notes=item.get('condition_notes'),
                    lot_id=item.get('lot_id'),
                    qty_remaining=item.get('qty_remaining'),
                    unit_cost=float(item['unit_cost']) if item.get('unit_cost') else None,
                    estimated_grade_text=item.get('estimated_grade_text'),
                    estimated_numeric_grade=float(item['estimated_numeric_grade']) if item.get(
                        'estimated_numeric_grade') else None,
                    valuation_method=item.get('valuation_method'),
                    manual_est_unit_value=float(item['manual_est_unit_value']) if item.get(
                        'manual_est_unit_value') else None,
                    storage_location_id=item.get('storage_location_id'),
                    storage_name=item.get('storage_name'),
                    lot_notes=item.get('lot_notes'),
                    is_proof=bool(item.get('is_proof'))
                ))

            # Convert header to TransactionHeader
            header_obj = TransactionHeader(
                id=header['id'],
                tx_date=header['tx_date'],
                tx_type=header['tx_type'],
                party_name=header['party_name'],
                currency=header['currency'],
                shipping=float(header['shipping'] or 0),
                tax=float(header['tax'] or 0),
                fees=float(header['fees'] or 0),
                notes=header['notes'],
                party_id=header['party_id']
            )

            return {'header': header_obj, 'items': lines}

        except Exception as e:
            print(f"Error getting transaction details: {e}")
            return None

    def update_transaction_header(self, tx_id: int, header: TransactionHeader) -> bool:
        """Update transaction header information"""
        try:
            from infrastructure.database.db_operations import execute_query_single, execute_update, \
                execute_insert

            # Find or create party
            party_id = None
            if header.party_name:
                party = execute_query_single("SELECT id FROM party WHERE name = ?",
                                             (header.party_name,))
                if party:
                    party_id = party['id']
                else:
                    party_id = execute_insert("INSERT INTO party(name) VALUES (?)",
                                              (header.party_name,))

            # Update transaction
            execute_update("""
                UPDATE tx 
                SET tx_date=?, party_id=?, currency=?, shipping=?, tax=?, fees=?, notes=?
                WHERE id=?
            """, (header.tx_date, party_id, header.currency, header.shipping,
                  header.tax, header.fees, header.notes, tx_id))

            # **FIX: Update lot acquired_date to match the new tx_date**
            execute_update("""
                UPDATE lot 
                SET acquired_date = ?
                WHERE acquisition_line_id IN (
                    SELECT id FROM tx_line WHERE tx_id = ?
                )
            """, (header.tx_date, tx_id))

            return True
        except Exception as e:
            print(f"Failed to update transaction: {e}")
            return False

    def update_coin_type_proof_status(self, coin_type_id: int, is_proof: bool) -> bool:
        """Update the proof status of a coin type"""
        try:
            from infrastructure.database.db_operations import execute_update

            execute_update(
                "UPDATE coin_type SET is_proof = ? WHERE id = ?",
                (1 if is_proof else 0, coin_type_id)
            )
            return True
        except Exception as e:
            print(f"Failed to update proof status: {e}")
            return False

    def update_item_details(self, line_id: int, lot_id: Optional[int],
                            updates: Dict[str, Any]) -> bool:
        """Update both line and lot details in one go"""
        try:
            from infrastructure.database.db_operations import execute_update

            # Update tx_line fields
            line_updates = []
            line_params = []

            line_fields = ['unit_price', 'grade_company', 'grade_text', 'numeric_grade',
                           'slab_cert', 'condition_notes']

            for field in line_fields:
                if field in updates and updates[field] is not None:
                    line_updates.append(f"{field} = ?")
                    line_params.append(updates[field])

            if line_updates:
                line_params.append(line_id)
                execute_update(
                    f"UPDATE tx_line SET {', '.join(line_updates)} WHERE id = ?",
                    tuple(line_params)
                )

            # Update lot fields (if lot exists)
            if lot_id:
                lot_updates = []
                lot_params = []

                # Map the fields appropriately
                lot_field_map = {
                    'unit_price': 'unit_cost',
                    'grade_company': 'purchase_grade_company',
                    'grade_text': 'purchase_grade_text',
                    'numeric_grade': 'purchase_numeric_grade',
                    'slab_cert': 'slab_cert',
                    'estimated_grade_text': 'estimated_grade_text',
                    'estimated_numeric_grade': 'estimated_numeric_grade',
                    'valuation_method': 'valuation_method',
                    'manual_est_unit_value': 'manual_est_unit_value',
                    'storage_location_id': 'storage_location_id',
                    'lot_notes': 'notes'
                }

                for ui_field, db_field in lot_field_map.items():
                    if ui_field in updates and updates[ui_field] is not None:
                        lot_updates.append(f"{db_field} = ?")
                        lot_params.append(updates[ui_field])

                if lot_updates:
                    lot_params.append(lot_id)
                    execute_update(
                        f"UPDATE lot SET {', '.join(lot_updates)} WHERE id = ?",
                        tuple(lot_params)
                    )

            return True
        except Exception as e:
            print(f"Failed to update item: {e}")
            return False

    def get_storage_locations(self) -> List[Dict[str, Any]]:
        """Get all storage locations"""
        try:
            from infrastructure.database.db_operations import execute_query_all
            query = "SELECT id, name, category FROM storage_location ORDER BY name"
            return execute_query_all(query) or []
        except Exception as e:
            print(f"Error getting storage locations: {e}")
            return []

    def get_all_coin_types(self) -> List[Dict[str, Any]]:
        """Get all coin types for selection"""
        try:
            from core.queries import get_all_coin_types
            return get_all_coin_types() or []
        except Exception as e:
            print(f"Error getting coin types: {e}")
            return []
