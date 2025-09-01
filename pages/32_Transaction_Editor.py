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

    # For BUY transactions, get combined line + lot info
    # For SELL transactions, just get line info
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
                -- Line grade info (purchase grades)
                tl.grade_company AS purchase_grade_company,
                tl.grade_text AS purchase_grade_text,
                tl.numeric_grade AS purchase_numeric_grade,
                tl.slab_cert,
                tl.condition_notes,
                -- Lot info (if exists)
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
                tl.condition_notes,
                NULL AS lot_id,
                NULL AS qty_remaining,
                NULL AS unit_cost,
                NULL AS estimated_grade_text,
                NULL AS estimated_numeric_grade,
                NULL AS valuation_method,
                NULL AS manual_est_unit_value,
                NULL AS storage_location_id,
                '' AS storage_name,
                NULL AS lot_notes
            FROM tx_line tl
            JOIN coin_type ct ON ct.id = tl.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE tl.tx_id = ?
            ORDER BY tl.id
        """

    items = execute_query_all(items_query, (tx_id,))

    return {
        'header': header,
        'items': items
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


def update_item_details(line_id: int, lot_id: Optional[int], updates: Dict[str, Any]) -> bool:
    """Update both line and lot details in one go."""
    try:
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
        st.error(f"Failed to update item: {e}")
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
    items = details['items']

    st.subheader(f"Editing {header['tx_type']} Transaction #{tx_id}")

    # Header editing
    with st.expander("Transaction Details", expanded=True):
        col1, col2, col3 = st.columns(3)

        new_date = col1.date_input("Date", value=pd.to_datetime(header['tx_date']).date(),
                                   key=f"edit_date_{tx_id}")
        new_party = col2.text_input("Party", value=header['party_name'], key=f"edit_party_{tx_id}")
        new_currency = col3.text_input("Currency", value=header['currency'],
                                       key=f"edit_currency_{tx_id}")

        col1, col2, col3 = st.columns(3)
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
            shipping_val = safe_float(new_shipping)
            tax_val = safe_float(new_tax)
            fees_val = safe_float(new_fees)

            if update_transaction_header(tx_id, new_date.isoformat(), new_party,
                                         new_currency, shipping_val, tax_val, fees_val, new_notes):
                st.success("Transaction details updated!")
                st.rerun()

    # Items (combined line + lot info for BUY transactions)
    st.subheader("Items")

    # Get storage locations once
    storage_locations = get_storage_locations() if header['tx_type'] == 'BUY' else []
    storage_options = {loc['name']: loc['id'] for loc in storage_locations}

    for i, item in enumerate(items):
        # Create a more descriptive header
        item_label = f"Item {i + 1}: {item['series']} {item['year']}"
        if item['mint_mark']:
            item_label += f" {item['mint_mark']}"
        if item['variety']:
            item_label += f" • {item['variety']}"
        if header['tx_type'] == 'BUY' and item['qty_remaining'] is not None:
            item_label += f" (Remaining: {item['qty_remaining']}/{abs(item['quantity'])})"

        with st.expander(item_label, expanded=False):
            # Basic coin info (read-only)
            st.write(f"**Quantity:** {abs(item['quantity'])}")

            # Proof status (affects coin_type globally)
            col1, col2 = st.columns(2)
            is_proof = col1.checkbox("Is Proof", value=bool(item['is_proof']),
                                     key=f"proof_{item['line_id']}")

            if col2.button("Update Proof Status", key=f"update_proof_{item['line_id']}"):
                if update_coin_type_proof_status(item['coin_type_id'], is_proof):
                    st.success("Proof status updated!")
                    st.rerun()

            st.divider()

            # Purchase Information
            st.markdown("**Purchase Information**")
            col1, col2 = st.columns(2)
            new_price = col1.text_input("Unit Price",
                                        value=format_float(item['unit_price']),
                                        key=f"price_{item['line_id']}")
            new_condition = col2.text_input("Condition Notes",
                                            value=item['condition_notes'] or '',
                                            key=f"condition_{item['line_id']}")

            # Grade Information
            st.markdown("**Grade Information**")
            col1, col2, col3 = st.columns(3)
            new_grade_co = col1.selectbox("Grade Company", [""] + GRADE_COMPANIES,
                                          index=GRADE_COMPANIES.index(
                                              item['purchase_grade_company']) + 1
                                          if item[
                                                 'purchase_grade_company'] in GRADE_COMPANIES else 0,
                                          key=f"grade_co_{item['line_id']}")
            new_purchase_grade = col2.text_input("Purchase Grade",
                                                 value=item['purchase_grade_text'] or '',
                                                 key=f"purchase_grade_{item['line_id']}")
            new_purchase_numeric = col3.text_input("Purchase Numeric",
                                                   value=format_float(
                                                       item['purchase_numeric_grade'], 1)
                                                   if item['purchase_numeric_grade'] else "0.0",
                                                   key=f"purchase_numeric_{item['line_id']}")

            new_slab_cert = st.text_input("Slab Certificate #",
                                          value=item['slab_cert'] or '',
                                          key=f"slab_cert_{item['line_id']}")

            # For BUY transactions, show additional lot-specific fields
            if header['tx_type'] == 'BUY' and item['lot_id']:
                st.divider()
                st.markdown("**Current Evaluation**")

                col1, col2 = st.columns(2)
                new_est_grade = col1.text_input("Estimated Grade",
                                                value=item['estimated_grade_text'] or '',
                                                key=f"est_grade_{item['line_id']}")
                new_est_numeric = col2.text_input("Estimated Numeric",
                                                  value=format_float(
                                                      item['estimated_numeric_grade'], 1)
                                                  if item['estimated_numeric_grade'] else "0.0",
                                                  key=f"est_numeric_{item['line_id']}")

                st.markdown("**Valuation & Storage**")
                col1, col2 = st.columns(2)
                new_val_method = col1.selectbox("Valuation Method", VALUATION_METHODS,
                                                index=VALUATION_METHODS.index(
                                                    item['valuation_method'])
                                                if item[
                                                       'valuation_method'] in VALUATION_METHODS else 0,
                                                key=f"val_method_{item['line_id']}")
                new_manual_val = col2.text_input("Manual Value (if MANUAL)",
                                                 value=format_float(item['manual_est_unit_value'])
                                                 if item['manual_est_unit_value'] else "0.00",
                                                 key=f"manual_val_{item['line_id']}")

                # Storage location
                current_storage = item['storage_name']
                storage_idx = 0
                if current_storage and current_storage in storage_options:
                    storage_names = list(storage_options.keys())
                    storage_idx = storage_names.index(current_storage) + 1  # +1 for empty option

                new_storage = st.selectbox("Storage Location",
                                           [""] + list(storage_options.keys()),
                                           index=storage_idx,
                                           key=f"storage_{item['line_id']}")

                new_lot_notes = st.text_area("Lot Notes",
                                             value=item['lot_notes'] or '',
                                             key=f"lot_notes_{item['line_id']}")

            # Single update button for everything
            if st.button("Update Item", type="primary", key=f"update_item_{item['line_id']}"):
                updates = {
                    'unit_price': safe_float(new_price),
                    'grade_company': new_grade_co if new_grade_co else None,
                    'grade_text': new_purchase_grade if new_purchase_grade else None,
                    'numeric_grade': safe_float(
                        new_purchase_numeric) if new_purchase_numeric else None,
                    'slab_cert': new_slab_cert if new_slab_cert else None,
                    'condition_notes': new_condition if new_condition else None,
                }

                # Add lot-specific fields if this is a BUY transaction
                if header['tx_type'] == 'BUY' and item['lot_id']:
                    updates.update({
                        'estimated_grade_text': new_est_grade if new_est_grade else None,
                        'estimated_numeric_grade': safe_float(
                            new_est_numeric) if new_est_numeric else None,
                        'valuation_method': new_val_method,
                        'manual_est_unit_value': safe_float(
                            new_manual_val) if new_manual_val else None,
                        'storage_location_id': storage_options.get(
                            new_storage) if new_storage else None,
                        'lot_notes': new_lot_notes if new_lot_notes else None,
                    })

                if update_item_details(item['line_id'], item['lot_id'], updates):
                    st.success("Item updated!")
                    st.rerun()


# ---------------------------------
# Main UI
# ---------------------------------
selected_tx_id = render_transaction_selector()

if selected_tx_id:
    st.divider()
    render_transaction_editor(selected_tx_id)

st.info(
    "💡 **Tip:** Changes to proof status affect the coin type globally (all instances of that coin). " +
    "All other changes only affect this specific transaction/lot.")
