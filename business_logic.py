# business_logic.py
"""Business logic helpers for transactions and inventory operations."""
from typing import List, Dict, Any, Optional

from db import get_conn
from db_operations import execute_insert, execute_query_all, execute_query_single, execute_update


class CostAllocationCalculator:
    """Handles cost allocation for buy transactions."""
    
    @staticmethod
    def allocate_buy_costs(items: List[Dict[str, Any]], shipping: float, tax: float, fees: float) -> List[float]:
        """
        Proportionally allocate shipping+tax+fees across BUY lines based on line subtotal.
        
        Args:
            items: List of dicts with keys: quantity, unit_price
            shipping: Shipping cost to allocate
            tax: Tax to allocate
            fees: Fees to allocate
            
        Returns:
            List of per-coin add-ons to unit_price
        """
        total_to_allocate = float(shipping or 0) + float(tax or 0) + float(fees or 0)
        
        # Calculate subtotals for each line
        subtotals = []
        for item in items:
            quantity = item.get("quantity", 0)
            unit_price = item.get("unit_price", 0.0)
            subtotals.append(quantity * unit_price)
        
        transaction_subtotal = sum(subtotals)
        
        if total_to_allocate <= 0 or transaction_subtotal <= 0:
            return [0.0] * len(items)
        
        # Calculate per-coin allocation for each item
        allocations = []
        for subtotal, item in zip(subtotals, items):
            share = total_to_allocate * (subtotal / transaction_subtotal)
            quantity = item.get("quantity", 1)
            per_coin = share / quantity if quantity > 0 else 0.0
            allocations.append(per_coin)
        
        return allocations


class InventoryManager:
    """Handles inventory operations like FIFO selling."""
    
    @staticmethod
    def find_fifo_lots(coin_type_id: int, quantity_needed: int) -> List[Dict[str, Any]]:
        """Find lots for FIFO selling."""
        query = """
            SELECT id, qty_remaining 
            FROM lot
            WHERE coin_type_id = ? AND qty_remaining > 0
            ORDER BY acquired_date ASC, id ASC
        """
        return execute_query_all(query, (coin_type_id,))
    
    @staticmethod
    def validate_inventory_availability(coin_type_id: int, quantity_requested: int) -> bool:
        """Check if enough inventory is available for sale."""
        query = """
            SELECT SUM(qty_remaining) as available
            FROM lot
            WHERE coin_type_id = ? AND qty_remaining > 0
        """
        result = execute_query_single(query, (coin_type_id,))
        available = result['available'] if result and result['available'] else 0
        return available >= quantity_requested
    
    @staticmethod
    def create_lot_relief(lot_id: int, sell_line_id: int, quantity: int, proceeds_per_unit: float):
        """Create lot relief record for FIFO selling."""
        execute_insert(
            "INSERT INTO lot_relief(lot_id, sell_line_id, quantity, proceeds_per_unit) VALUES (?,?,?,?)",
            (lot_id, sell_line_id, quantity, proceeds_per_unit)
        )
    
    @staticmethod
    def update_lot_remaining_quantity(lot_id: int, quantity_to_subtract: int):
        """Update lot remaining quantity after sale."""
        execute_update(
            "UPDATE lot SET qty_remaining = qty_remaining - ? WHERE id = ?",
            (quantity_to_subtract, lot_id)
        )


class TransactionBuilder:
    """Builder pattern for creating transactions."""
    
    def __init__(self):
        self.tx_data = {}
        self.items = []
    
    def set_basic_info(self, tx_date: str, tx_type: str, party_name: str = None, currency: str = "USD"):
        """Set basic transaction information."""
        self.tx_data.update({
            'tx_date': tx_date,
            'tx_type': tx_type,
            'party_name': party_name,
            'currency': currency
        })
        return self
    
    def set_costs(self, shipping: float = 0.0, tax: float = 0.0, fees: float = 0.0):
        """Set transaction costs."""
        self.tx_data.update({
            'shipping': float(shipping or 0.0),
            'tax': float(tax or 0.0),
            'fees': float(fees or 0.0)
        })
        return self
    
    def set_notes(self, notes: str = None):
        """Set transaction notes."""
        self.tx_data['notes'] = notes
        return self
    
    def add_item(self, **item_data):
        """Add an item to the transaction."""
        self.items.append(item_data)
        return self
    
    def validate(self):
        """Validate transaction data."""
        required = ['tx_date', 'tx_type']
        for field in required:
            if field not in self.tx_data:
                raise ValueError(f"Missing required field: {field}")
        
        if not self.items:
            raise ValueError("Transaction must have at least one item")
        
        # Validate items have required fields
        for i, item in enumerate(self.items):
            if 'coin_type_id' not in item:
                raise ValueError(f"Item {i}: Missing coin_type_id")
            if 'quantity' not in item:
                raise ValueError(f"Item {i}: Missing quantity")
    
    def build_buy_transaction(self) -> bool:
        """Build and execute buy transaction with proper transaction handling."""
        self.validate()
        
        from db_operations import find_or_create_party
        
        party_id = find_or_create_party(self.tx_data.get('party_name')) if self.tx_data.get('party_name') else None
        
        with get_conn() as cx:
            try:
                cx.execute("BEGIN")
                
                # Create transaction header
                tx_id = execute_insert(
                    "INSERT INTO tx(tx_date, tx_type, party_id, currency, shipping, tax, fees, notes) VALUES (?,?,?,?,?,?,?,?)",
                    (
                        self.tx_data['tx_date'], 
                        self.tx_data['tx_type'],
                        party_id,
                        self.tx_data.get('currency', 'USD'),
                        self.tx_data.get('shipping', 0.0),
                        self.tx_data.get('tax', 0.0),
                        self.tx_data.get('fees', 0.0),
                        self.tx_data.get('notes')
                    )
                )
                
                # Calculate cost allocations
                allocations = CostAllocationCalculator.allocate_buy_costs(
                    self.items,
                    self.tx_data.get('shipping', 0.0),
                    self.tx_data.get('tax', 0.0),
                    self.tx_data.get('fees', 0.0)
                )
                
                # Create transaction lines and lots
                for item, allocation in zip(self.items, allocations):
                    line_id = execute_insert(
                        """
                        INSERT INTO tx_line(tx_id, coin_type_id, quantity, unit_price, grade_company, grade_text, numeric_grade, slab_cert, condition_notes)
                        VALUES (?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            tx_id, 
                            item["coin_type_id"], 
                            item["quantity"], 
                            item.get("unit_price"),
                            item.get("purchase_grade_company"), 
                            item.get("purchase_grade_text"), 
                            item.get("purchase_numeric_grade"),
                            item.get("slab_cert"), 
                            item.get("condition_notes")
                        )
                    )
                    
                    unit_cost = float(item.get("unit_price", 0.0)) + allocation

                    # Check asset category to determine valuation method
                    asset_cat_query = """
                                           SELECT cm.asset_category 
                                           FROM coin_master cm 
                                           JOIN coin_type ct ON ct.master_id = cm.id 
                                           WHERE ct.id = ?
                                       """
                    result = execute_query_single(asset_cat_query, (item["coin_type_id"],))
                    asset_category = result['asset_category'] if result else 'COIN'

                    # Override valuation method for bullion
                    if asset_category in ('BULLION COIN', 'ROUND', 'BAR'):
                        valuation_method = 'MELT_ONLY'
                    else:
                        valuation_method = item.get("valuation_method", 'AUTO')

                    execute_insert(
                        """
                        INSERT INTO lot(
                            acquisition_line_id, coin_type_id, acquired_date, qty_acquired, qty_remaining, unit_cost,
                            storage_location_id,
                            purchase_grade_company, purchase_grade_text, purchase_numeric_grade, slab_cert,
                            estimated_grade_text, estimated_numeric_grade,
                            valuation_method, manual_est_unit_value, status, notes
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            line_id, 
                            item["coin_type_id"], 
                            self.tx_data['tx_date'], 
                            item["quantity"], 
                            item["quantity"], 
                            unit_cost,
                            item.get("storage_location_id"),
                            item.get("purchase_grade_company"), 
                            item.get("purchase_grade_text"), 
                            item.get("purchase_numeric_grade"), 
                            item.get("slab_cert"),
                            item.get("estimated_grade_text"), 
                            item.get("estimated_numeric_grade"),
                            valuation_method,
                            item.get("manual_est_unit_value"),
                            'OPEN', 
                            item.get("lot_notes")
                        )
                    )
                
                cx.execute("COMMIT")
                return True
                
            except Exception as e:
                cx.execute("ROLLBACK")
                raise RuntimeError(f"Buy transaction failed: {str(e)}") from e
    
    def build_sell_transaction(self, method: str = 'FIFO') -> bool:
        """Build and execute sell transaction with proper transaction handling."""
        if method != 'FIFO':
            raise NotImplementedError("Only FIFO is implemented")
        
        self.validate()
        
        from db_operations import find_or_create_party
        
        party_id = find_or_create_party(self.tx_data.get('party_name')) if self.tx_data.get('party_name') else None
        
        with get_conn() as cx:
            try:
                cx.execute("BEGIN")
                
                # Create transaction header
                tx_id = execute_insert(
                    "INSERT INTO tx(tx_date, tx_type, party_id, currency, shipping, tax, fees, notes) VALUES (?,?,?,?,?,?,?,?)",
                    (
                        self.tx_data['tx_date'],
                        self.tx_data['tx_type'],
                        party_id,
                        self.tx_data.get('currency', 'USD'),
                        self.tx_data.get('shipping', 0.0),
                        self.tx_data.get('tax', 0.0),
                        self.tx_data.get('fees', 0.0),
                        self.tx_data.get('notes')
                    )
                )
                
                # Process each item
                for item in self.items:
                    coin_type_id = item["coin_type_id"]
                    quantity_requested = abs(item["quantity"])
                    
                    # Validate inventory availability
                    if not InventoryManager.validate_inventory_availability(coin_type_id, quantity_requested):
                        raise ValueError(f"Not enough inventory to sell {quantity_requested} of coin_type_id {coin_type_id}")
                    
                    # Create sell line
                    sell_line_id = execute_insert(
                        "INSERT INTO tx_line(tx_id, coin_type_id, quantity, unit_price) VALUES (?,?,?,?)",
                        (tx_id, coin_type_id, -quantity_requested, item.get("unit_price"))
                    )
                    
                    # FIFO relieve from oldest lots
                    lots = InventoryManager.find_fifo_lots(coin_type_id, quantity_requested)
                    remaining = quantity_requested
                    
                    for lot in lots:
                        if remaining <= 0:
                            break
                        
                        available = lot["qty_remaining"]
                        take = min(available, remaining)
                        
                        InventoryManager.create_lot_relief(
                            lot["id"], 
                            sell_line_id, 
                            take, 
                            item.get("unit_price", 0.0)
                        )
                        
                        # Update lot remaining quantity
                        # InventoryManager.update_lot_remaining_quantity(lot["id"], take)
                        
                        remaining -= take
                
                cx.execute("COMMIT")
                return True
                
            except Exception as e:
                cx.execute("ROLLBACK")
                raise RuntimeError(f"Sell transaction failed: {str(e)}") from e


# Factory functions for backward compatibility
def create_buy_transaction(tx_date: str, party_name: str, currency: str, shipping: float, 
                          tax: float, fees: float, notes: str, items: List[dict]) -> bool:
    """Factory function for buy transactions (backward compatibility)."""
    builder = TransactionBuilder()
    builder.set_basic_info(tx_date, 'BUY', party_name, currency)
    builder.set_costs(shipping, tax, fees)
    builder.set_notes(notes)
    
    for item in items:
        builder.add_item(**item)
    
    return builder.build_buy_transaction()


def create_sell_transaction(tx_date: str, party_name: str, currency: str, shipping: float,
                           tax: float, fees: float, notes: str, items: List[dict], method: str = 'FIFO') -> bool:
    """Factory function for sell transactions (backward compatibility)."""
    builder = TransactionBuilder()
    builder.set_basic_info(tx_date, 'SELL', party_name, currency)
    builder.set_costs(shipping, tax, fees)
    builder.set_notes(notes)
    
    for item in items:
        builder.add_item(**item)
    
    return builder.build_sell_transaction(method)