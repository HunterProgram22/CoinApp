# pages/32_Transaction_Editor.py
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from typing import Optional, List, Dict, Any
from db_operations import execute_query_all, execute_query_single, execute_update, execute_delete
from constants import ASSET_CATEGORIES, VALUATION_METHODS, GRADE_COMPANIES

st.header("Transaction Editor")

# ---------------------------------
# Data Access Functions
# ---------------------------------
def get_recent_transactions(limit: int = 100) -> List[Dict[str, Any]]:
    """Get recent transactions for editing."""
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
        GROUP BY t.id, t.tx_date, t.tx_type, p.name, t.currency, t.shipping, t.tax, t.fees, t.notes
        ORDER BY t.tx_date DESC, t.id DESC
        LIMIT ?
    """
    return execute_query_all(query, (limit,))


def get_transaction_details(tx_id: int) -> Dict[str, Any]:
    """Get detailed transaction information."""
    # Header info
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
    
    # Line items
    lines_query = """
        SELECT 
            tl.id AS line_id,
            tl.coin_type_id,
            cm.series, ct.year, ct.mint_mark, 
            COALESCE(ct.variety, '') AS variety,
            ct.is_proof,
            tl.quantity,
            tl.unit_price,
            tl.grade_company,
            tl.grade_text,
            tl.numeric_grade,
            tl.slab_cert,
            tl.condition_notes
        FROM tx_line tl
        JOIN coin_type ct ON ct.id = tl.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        WHERE tl.tx_id = ?
        ORDER BY tl.id
    """
    lines = execute_query_all(lines_query, (tx_id,))
    
    # For BUY transactions, get lot details
    lots = []
    if header['tx_type'] == 'BUY':
        lots_query = """
            SELECT 
                l.id AS lot_id,
                l.acquisition_line_id,
                l.qty_remaining,
                l.unit_cost,
                l.purchase_grade_company,
                l.purchase_grade_text,
                l.purchase_numeric_grade,
                l.slab_cert,
                l.estimated_grade_text,
                l.estimated_numeric_grade,
                l.valuation_method,
                l.manual_est_unit_value,
                l.storage_location_id,
                COALESCE(sl.name, '') AS storage_name,
                l.notes AS lot_notes
            FROM lot l
            JOIN tx_line tl ON tl.id = l.acquisition_line_id
            LEFT JOIN storage_location sl ON sl.id = l.storage_location_id
            WHERE tl.tx_id = ?
            ORDER BY l.id
        """
        lots = execute_query_all(lots_query, (tx_id,))
    
    return {
        'header': header,
        'lines': lines,
        'lots': lots
    }


def get_storage_locations() -> List[Dict[str, Any]]:
    """Get all storage locations."""
    query = "SELECT id, name, category FROM storage_location ORDER BY name"
    return execute_query_all(query)


def update_transaction_header(tx_id: int, tx_date: str, party_name: str, 
                            currency: str, shipping: float, tax: float, 
                            fees: float, notes: str) -> bool:
    """Update transaction header information."""
    try:
        # Find or create party
        party_id = None
        if party_name:
            party = execute_query_single("SELECT id FROM party WHERE name = ?", (party_name,))
            if party:
                party_id = party['id']
            else:
                from db_operations import execute_insert
                party_id = execute_insert("INSERT INTO party(name) VALUES (?)", (party_name,))
        
        # Update transaction
        execute_update("""
            UPDATE tx 
            SET tx_date=?, party_id=?, currency=?, shipping=?, tax=?, fees=?, notes=?
            WHERE id=?
        """, (tx_date, party_id, currency, shipping, tax, fees, notes, tx_id))
        
        return True
    except Exception as e:
        st.error(f"Failed to update transaction: {e}")
        return False


def update_coin_type_proof_status(coin_type_id: int, is_proof: bool) -> bool:
    """Update the proof status of a coin type."""
    try:
        execute_update(
            "UPDATE coin_type SET is_proof = ? WHERE id = ?",
            (1 if is_proof else 0, coin_type_id)
        )
        return True
    except Exception as e:
        st.error(f"Failed to update proof status: {e}")
        return False


def update_lot_details(lot_id: int, **kwargs) -> bool:
    """Update lot details."""
    try:
        updates = []
        params = []
        
        for field, value in kwargs.items():
            if value is not None:
                updates.append(f"{field} = ?")
                params.append(value)
        
        if updates:
            params.append(lot_id)
            query = f"UPDATE lot SET {', '.join(updates)} WHERE id = ?"
            execute_update(query, tuple(params))
        
        return True
    except Exception as e:
        st.error(f"Failed to update lot: {e}")
        return False


def update_tx_line(line_id: int, unit_price: float, grade_company: str = None,
                   grade_text: str = None, numeric_grade: float = None,
                   slab_cert: str = None, condition_notes: str = None) -> bool:
    """Update transaction line details."""
    try:
        # Update tx_line
        execute_update("""
            UPDATE tx_line 
            SET unit_price=?, grade_company=?, grade_text=?, numeric_grade=?, 
                slab_cert=?, condition_notes=?
            WHERE id=?
        """, (unit_price, grade_company, grade_text, numeric_grade,
              slab_cert, condition_notes, line_id))

        # Also update the corresponding lot if this is from a BUY transaction
        # The lot.acquisition_line_id points to the tx_line
        execute_update("""
            UPDATE lot
            SET slab_cert=?, 
                purchase_grade_company=?, 
                purchase_grade_text=?, 
                purchase_numeric_grade=?
            WHERE acquisition_line_id=?
        """, (slab_cert, grade_company, grade_text, numeric_grade, line_id))

        return True
    except Exception as e:
        st.error(f"Failed to update transaction line: {e}")
        return False


# ---------------------------------
# Helper Functions
# ---------------------------------
def safe_float(value: str, default: float = 0.0) -> float:
    """Safely convert string to float."""
    try:
        return float(value) if value else default
    except (ValueError, TypeError):
        return default


def format_float(value: float, decimals: int = 2) -> str:
    """Format float for display in text input."""
    if value is None or value == 0:
        return "0.00" if decimals == 2 else "0.0"
    return f"{value:.{decimals}f}"


# ---------------------------------
# UI Components
# ---------------------------------
def render_transaction_selector():
    """Render transaction selection interface."""
    st.subheader("Select Transaction to Edit")
    
    transactions = get_recent_transactions(100)
    
    if not transactions:
        st.info("No transactions found.")
        return None
    
    # Create display options
    tx_options = []
    for tx in transactions:
        label = f"#{tx['id']} - {tx['tx_date']} - {tx['tx_type']} - {tx['party'] or 'No Party'} - {tx['total_quantity']} items"
        tx_options.append(label)
    
    selected_idx = st.selectbox("Select transaction", range(len(tx_options)), 
                               format_func=lambda x: tx_options[x], key="tx_select")
    
    return transactions[selected_idx]['id']


def render_transaction_editor(tx_id: int):
    """Render the transaction editing interface."""
    details = get_transaction_details(tx_id)
    
    if not details:
        st.error("Transaction not found.")
        return
    
    header = details['header']
    lines = details['lines']
    lots = details['lots']
    
    st.subheader(f"Editing Transaction #{tx_id}")
    
    # Header editing
    with st.expander("Transaction Details", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        new_date = col1.date_input("Date", value=pd.to_datetime(header['tx_date']).date(), 
                                  key=f"edit_date_{tx_id}")
        new_party = col2.text_input("Party", value=header['party_name'], key=f"edit_party_{tx_id}")
        new_currency = col3.text_input("Currency", value=header['currency'], key=f"edit_currency_{tx_id}")
        
        col1, col2, col3 = st.columns(3)
        # Use text inputs for money fields
        new_shipping = col1.text_input("Shipping", 
                                      value=format_float(header['shipping']), 
                                      key=f"edit_ship_{tx_id}")
        new_tax = col2.text_input("Tax", 
                                 value=format_float(header['tax']), 
                                 key=f"edit_tax_{tx_id}")
        new_fees = col3.text_input("Fees", 
                                  value=format_float(header['fees']), 
                                  key=f"edit_fees_{tx_id}")
        
        new_notes = st.text_area("Notes", value=header['notes'] or '', key=f"edit_notes_{tx_id}")
        
        if st.button("Update Transaction Details", key=f"update_header_{tx_id}"):
            # Validate numeric inputs
            shipping_val = safe_float(new_shipping)
            tax_val = safe_float(new_tax)
            fees_val = safe_float(new_fees)
            
            if update_transaction_header(tx_id, new_date.isoformat(), new_party, 
                                       new_currency, shipping_val, tax_val, fees_val, new_notes):
                st.success("Transaction details updated!")
                st.rerun()
    
    # Line items editing
    st.subheader("Line Items")
    
    for i, line in enumerate(lines):
        with st.expander(f"Line {i+1}: {line['series']} {line['year']} {line['mint_mark']} {line['variety']}", 
                        expanded=False):
            
            # Coin type details (read-only)
            st.write(f"**Coin:** {line['series']} {line['year']} {line['mint_mark']} {line['variety']}")
            st.write(f"**Quantity:** {abs(line['quantity'])}")
            
            # Editable proof status
            col1, col2 = st.columns(2)
            is_proof = col1.checkbox("Is Proof", value=bool(line['is_proof']), 
                                    key=f"proof_{line['line_id']}")
            
            if col2.button("Update Proof Status", key=f"update_proof_{line['line_id']}"):
                if update_coin_type_proof_status(line['coin_type_id'], is_proof):
                    st.success("Proof status updated!")
                    st.rerun()
            
            # Editable line details
            col1, col2, col3 = st.columns(3)
            # Use text input for unit price
            new_price = col1.text_input("Unit Price", 
                                       value=format_float(line['unit_price']), 
                                       key=f"price_{line['line_id']}")
            new_grade_co = col2.selectbox("Grade Company", [""] + GRADE_COMPANIES,
                                        index=GRADE_COMPANIES.index(line['grade_company']) + 1 
                                        if line['grade_company'] in GRADE_COMPANIES else 0,
                                        key=f"grade_co_{line['line_id']}")
            new_grade_text = col3.text_input("Grade Text", value=line['grade_text'] or '',
                                           key=f"grade_text_{line['line_id']}")
            
            col1, col2 = st.columns(2)
            # Use text input for numeric grade
            new_numeric_grade = col1.text_input("Numeric Grade", 
                                              value=format_float(line['numeric_grade'], 1) if line['numeric_grade'] else "0.0",
                                              key=f"numeric_grade_{line['line_id']}")
            new_slab_cert = col2.text_input("Slab Cert", value=line['slab_cert'] or '',
                                          key=f"slab_cert_{line['line_id']}")
            
            new_condition = st.text_area("Condition Notes", value=line['condition_notes'] or '',
                                       key=f"condition_{line['line_id']}")
            
            if st.button("Update Line Item", key=f"update_line_{line['line_id']}"):
                # Validate numeric inputs
                price_val = safe_float(new_price)
                numeric_grade_val = safe_float(new_numeric_grade)
                
                if update_tx_line(line['line_id'], price_val, 
                                 new_grade_co if new_grade_co else None,
                                 new_grade_text if new_grade_text else None,
                                 numeric_grade_val if numeric_grade_val else None,
                                 new_slab_cert if new_slab_cert else None,
                                 new_condition if new_condition else None):
                    st.success("Line item updated!")
                    st.rerun()
    
    # Lot details editing (for BUY transactions)
    if header['tx_type'] == 'BUY' and lots:
        st.subheader("Lot Details")
        storage_locations = get_storage_locations()
        storage_options = {loc['name']: loc['id'] for loc in storage_locations}
        
        for i, lot in enumerate(lots):
            with st.expander(f"Lot {lot['lot_id']} - Remaining: {lot['qty_remaining']}", 
                            expanded=False):
                
                col1, col2 = st.columns(2)
                
                # Estimated grades
                new_est_grade_text = col1.text_input("Estimated Grade", 
                                                   value=lot['estimated_grade_text'] or '',
                                                   key=f"est_grade_{lot['lot_id']}")
                # Use text input for estimated numeric grade
                new_est_numeric = col2.text_input("Estimated Numeric", 
                                                value=format_float(lot['estimated_numeric_grade'], 1) if lot['estimated_numeric_grade'] else "0.0",
                                                key=f"est_numeric_{lot['lot_id']}")
                
                # Valuation
                col1, col2 = st.columns(2)
                new_val_method = col1.selectbox("Valuation Method", VALUATION_METHODS,
                                              index=VALUATION_METHODS.index(lot['valuation_method'])
                                              if lot['valuation_method'] in VALUATION_METHODS else 0,
                                              key=f"val_method_{lot['lot_id']}")
                # Use text input for manual value
                new_manual_val = col2.text_input("Manual Value", 
                                               value=format_float(lot['manual_est_unit_value']) if lot['manual_est_unit_value'] else "0.00",
                                               key=f"manual_val_{lot['lot_id']}")
                
                # Storage
                current_storage = lot['storage_name']
                storage_idx = 0
                if current_storage and current_storage in storage_options:
                    storage_names = list(storage_options.keys())
                    storage_idx = storage_names.index(current_storage)
                
                new_storage = st.selectbox("Storage Location", 
                                         [""] + list(storage_options.keys()),
                                         index=storage_idx,
                                         key=f"storage_{lot['lot_id']}")
                
                new_lot_notes = st.text_area("Lot Notes", value=lot['lot_notes'] or '',
                                            key=f"lot_notes_{lot['lot_id']}")
                
                if st.button("Update Lot", key=f"update_lot_{lot['lot_id']}"):
                    # Validate numeric inputs
                    est_numeric_val = safe_float(new_est_numeric)
                    manual_val = safe_float(new_manual_val)
                    
                    updates = {
                        'estimated_grade_text': new_est_grade_text if new_est_grade_text else None,
                        'estimated_numeric_grade': est_numeric_val if est_numeric_val else None,
                        'valuation_method': new_val_method,
                        'manual_est_unit_value': manual_val if manual_val else None,
                        'storage_location_id': storage_options.get(new_storage) if new_storage else None,
                        'notes': new_lot_notes if new_lot_notes else None
                    }
                    
                    if update_lot_details(lot['lot_id'], **updates):
                        st.success("Lot updated!")
                        st.rerun()


# ---------------------------------
# Main UI
# ---------------------------------
selected_tx_id = render_transaction_selector()

if selected_tx_id:
    st.divider()
    render_transaction_editor(selected_tx_id)

st.info("💡 **Tip:** Changes to proof status affect the coin type permanently. " + 
        "Changes to grades and valuations only affect this specific lot.")
