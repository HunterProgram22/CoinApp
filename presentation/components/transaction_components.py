# presentation/components/transaction_components.py
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from typing import Optional, List, Dict, Any
from infrastructure.database.repositories.transaction_repository import (
    TransactionDataRepository, TransactionHeader
)
from presentation.components.helpers.transaction_helpers import (
    calculate_date_range, format_coin_type_label, format_storage_label,
    format_transaction_dataframe, safe_float, format_float,
    format_transaction_label, format_item_label
)
from core.constants import GRADE_COMPANIES, VALUATION_METHODS
from core.queries import create_buy_transaction, create_sell_transaction


# Cache decorator for expensive queries
@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_cached_coin_types(repo_id):
    """Cache coin types to avoid repeated queries - ttl=300 means refresh every 5 minutes"""
    from infrastructure.database.database_executor import DatabaseExecutor
    from infrastructure.database.repositories.transaction_repository import TransactionRepository
    repo = TransactionRepository(DatabaseExecutor())
    return repo.get_all_coin_types()


@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_cached_storage_locations(repo_id):
    """Cache storage locations to avoid repeated queries"""
    from infrastructure.database.database_executor import DatabaseExecutor
    from infrastructure.database.repositories.transaction_repository import TransactionRepository
    repo = TransactionRepository(DatabaseExecutor())
    return repo.get_storage_locations()


@st.cache_data(ttl=60)  # Cache for 1 minute (shorter since this might change frequently)
def get_cached_parties(repo_id):
    """Cache parties list to avoid repeated queries"""
    from infrastructure.database.database_executor import DatabaseExecutor
    from infrastructure.database.repositories.transaction_repository import TransactionRepository
    repo = TransactionRepository(DatabaseExecutor())
    return repo.get_parties()


class TransactionRenderer:
    """UI rendering for transactions with dependency injection"""

    def __init__(self, repository: TransactionDataRepository):
        self.repository = repository

        # Initialize session state for line items if not exists
        # if 'buy_line_items' not in st.session_state:
        #     st.session_state.buy_line_items = []
        # if 'sell_line_items' not in st.session_state:
        #     st.session_state.sell_line_items = []

    def render_search_tab(self):
        """Render the Review/Search tab"""

        # Search filters
        col0, col1, col2, col3 = st.columns([2, 2, 2, 2])

        preset = col0.selectbox(
            "Quick range",
            ["30d", "7d", "90d", "YTD", "1y", "All"],
            index=0,
            key="tx_preset"
        )

        start_dt, end_dt = calculate_date_range(preset)

        # Use preset in the key to force new widgets when preset changes
        # This ensures date_input uses the fresh value parameter
        if preset != "All":
            start_dt = col1.date_input("Start", value=start_dt, key=f"tx_rev_start_{preset}")
            end_dt = col2.date_input("End", value=end_dt, key=f"tx_rev_end_{preset}")
        else:
            start_dt = col1.date_input(
                "Start",
                value=date.today() - timedelta(days=365 * 5),
                key=f"tx_rev_start_{preset}"
            )
            end_dt = col2.date_input("End", value=date.today(), key=f"tx_rev_end_{preset}")

        tx_types = col3.multiselect(
            "Type",
            ["BUY", "SELL"],
            default=["BUY", "SELL"],
            key="tx_rev_kinds"
        )

        col4, col5, col6 = st.columns([2, 2, 3])

        # Use cached parties to avoid repeated queries
        repo_id = id(self.repository)
        parties = get_cached_parties(repo_id)

        party_selection = col4.selectbox(
            "Party (optional)",
            ["(any)"] + parties,
            index=0,
            key="tx_rev_party"
        )
        party = None if party_selection == "(any)" else party_selection

        search_text = col5.text_input(
            "Search text (series/variety/party/notes)",
            key="tx_rev_search"
        )

        run_search = col6.button("Run Search", type="primary", key="tx_rev_run")

        if run_search:
            # Handle "All" preset
            if preset == "All":
                start_dt, end_dt = None, None

            df = self.repository.search_transactions(start_dt, end_dt, tx_types, party, search_text)

            if df.empty:
                st.info("No transactions matched your filters.")
            else:
                display_df = format_transaction_dataframe(df)
                st.dataframe(display_df, width='stretch', hide_index=True)

                # Download button
                st.download_button(
                    "Download CSV (Transactions)",
                    data=df.to_csv(index=False).encode("utf-8"),
                    file_name="transactions.csv",
                    mime="text/csv"
                )

    def _render_buy_form(self):
        """Render the buy transaction form"""
        # Ensure session state is initialized at the start of the method
        if 'buy_line_items' not in st.session_state:
            st.session_state.buy_line_items = []

        # USE CACHED DATA - this is the key change!
        # Use a unique repo ID to cache per instance
        repo_id = id(self.repository)
        coin_types = get_cached_coin_types(repo_id)
        storage_options = get_cached_storage_locations(repo_id)

        # Transaction Header
        st.subheader("Transaction Details")
        colA, colB, colC = st.columns(3)
        tx_date = colA.date_input("Date", value=date.today(), key="buy_date")
        party_name = colB.text_input("Counterparty (Dealer/Person)", key="buy_party")
        currency = colC.text_input("Currency", value="USD", key="buy_ccy")

        colA, colB, colC = st.columns(3)
        shipping = colA.text_input("Shipping", value="0.00", key="buy_ship")
        tax = colB.text_input("Tax", value="0.00", key="buy_tax")
        fees = colC.text_input("Fees", value="0.00", key="buy_fees")
        notes = st.text_area("Notes", height=70, key="buy_notes")

        st.divider()

        # Line Items Section
        st.subheader("Line Items")

        # Display current line items
        if st.session_state.buy_line_items:
            self._display_line_items("buy")

        st.divider()

        # Add new line item form
        with st.expander("➕ Add Line Item", expanded=True):
            self._render_add_buy_item_form(coin_types, storage_options)

        st.divider()

        # Save transaction button
        if st.button("💾 Save Transaction", type="primary", key="save_buy_tx"):
            if not st.session_state.buy_line_items:
                st.error("Please add at least one line item.")
            else:
                self._save_buy_transaction(tx_date, party_name, currency, shipping, tax, fees,
                                           notes)

    def _render_sell_form(self):
        """Render the sell transaction form"""
        # Ensure session state is initialized at the start of the method
        if 'sell_line_items' not in st.session_state:
            st.session_state.sell_line_items = []

        # USE CACHED DATA - this is the key change!
        repo_id = id(self.repository)
        coin_types = get_cached_coin_types(repo_id)

        # Transaction Header
        st.subheader("Transaction Details")
        colA, colB, colC = st.columns(3)
        tx_date = colA.date_input("Date", value=date.today(), key="sell_date")
        party_name = colB.text_input("Counterparty (Buyer)", key="sell_party")
        currency = colC.text_input("Currency", value="USD", key="sell_ccy")

        colA, colB, colC = st.columns(3)
        shipping = colA.text_input("Shipping", value="0.00", key="sell_ship")
        tax = colB.text_input("Tax", value="0.00", key="sell_tax")
        fees = colC.text_input("Fees", value="0.00", key="sell_fees")
        notes = st.text_area("Notes", height=70, key="sell_notes")

        st.divider()

        # Line Items Section
        st.subheader("Line Items to Sell")

        # Display current line items
        if st.session_state.sell_line_items:
            self._display_line_items("sell")

        st.divider()

        # Add new line item form
        with st.expander("➕ Add Line Item", expanded=True):
            self._render_add_sell_item_form(coin_types)

        st.divider()

        # Save transaction button
        if st.button("💾 Save Transaction (FIFO)", type="primary", key="save_sell_tx"):
            if not st.session_state.sell_line_items:
                st.error("Please add at least one line item.")
            else:
                self._save_sell_transaction(tx_date, party_name, currency, shipping, tax, fees,
                                            notes)
                
    def render_add_transaction_tab(self):
        """Render the Add Transaction tab"""
        try:
            tx_mode = st.segmented_control(
                "Transaction Type",
                options=["BUY", "SELL"],
                default="BUY",
                key="tx_mode"
            )
        except AttributeError:
            tx_mode = st.radio(
                "Transaction Type",
                ["BUY", "SELL"],
                index=0,
                horizontal=True,
                key="tx_mode"
            )

        if tx_mode == "BUY":
            self._render_buy_form()
        else:
            self._render_sell_form()

    def _display_line_items(self, tx_type: str):
        """Display current line items for buy or sell"""
        items = st.session_state.buy_line_items if tx_type == "buy" else st.session_state.sell_line_items

        st.write(f"**{len(items)} items added:**")

        # Create a summary table
        items_df = []
        for idx, item in enumerate(items):
            row = {
                'Index': idx,
                'Coin': item['display_label'],
                'Qty': item['quantity'],
                'Unit Price': f"${item['unit_price']:.2f}",
                'Total': f"${item['quantity'] * item['unit_price']:.2f}"
            }
            if tx_type == "buy":
                row['Grade'] = item.get('purchase_grade_text', '')
                row['Storage'] = item.get('storage_name', '')
            items_df.append(row)

        df = pd.DataFrame(items_df)
        st.dataframe(df.drop(columns=['Index']), width='stretch', hide_index=True)

        # Calculate totals
        subtotal = sum(item['quantity'] * item['unit_price'] for item in items)
        st.write(f"**Subtotal: ${subtotal:.2f}**")

        # Remove item functionality
        col1, col2 = st.columns([3, 1])
        with col1:
            remove_idx = st.selectbox(
                "Remove item:",
                options=range(len(items)),
                format_func=lambda x: items[x]['display_label'],
                key=f"remove_{tx_type}_item_select"
            )
        with col2:
            if st.button("Remove", key=f"remove_{tx_type}_item"):
                if tx_type == "buy":
                    st.session_state.buy_line_items.pop(remove_idx)
                else:
                    st.session_state.sell_line_items.pop(remove_idx)
                st.rerun()

        if st.button("Clear All Items", key=f"clear_{tx_type}_items"):
            if tx_type == "buy":
                st.session_state.buy_line_items = []
            else:
                st.session_state.sell_line_items = []
            st.rerun()

    def _render_add_buy_item_form(self, coin_types, storage_options):
        """Render form to add a buy line item"""
        if coin_types:
            selection = st.selectbox(
                "Coin Type",
                coin_types,
                format_func=format_coin_type_label,
                key="buy_ct_add"
            )
            coin_type_id = selection["id"] if selection else None
        else:
            st.warning("Add at least one Coin Type in Admin → Coin Types.")
            coin_type_id = None

        col1, col2 = st.columns(2)
        quantity = col1.number_input("Quantity", min_value=1, step=1, value=1, key="buy_qty_add")
        unit_price = col2.text_input("Unit Price (per coin)", value="0.00", key="buy_unit_add")

        with st.expander("Grades & Valuation (Optional)"):
            purchase_grade_company = st.text_input("Purchase Grade Company (PCGS/NGC/RAW)",
                                                   key="buy_pgc_add")
            purchase_grade_text = st.text_input("Purchase Grade Text (e.g., MS64)",
                                                key="buy_pgt_add")
            purchase_numeric_grade = st.number_input("Purchase Numeric Grade", min_value=0.0,
                                                     step=0.5, value=0.0, key="buy_png_add")
            slab_cert = st.text_input("Slab Cert #", key="buy_cert_add")

            estimated_grade_text = st.text_input("Estimated Grade (your current opinion)",
                                                 key="buy_egt_add")
            estimated_numeric_grade = st.number_input("Estimated Numeric Grade", min_value=0.0,
                                                      step=0.5, value=0.0, key="buy_eng_add")
            valuation_method = st.selectbox("Valuation Method",
                                            ["AUTO", "MELT_ONLY", "GUIDE_ONLY", "MANUAL"], index=0,
                                            key="buy_valm_add")
            manual_est_unit_value = st.text_input("Manual Unit Value (used only if MANUAL)",
                                                  value="0.00", key="buy_manual_add")

        with st.expander("Storage (Optional)"):
            storage_location_id = None
            storage_name = ""
            if storage_options:
                stg = st.selectbox(
                    "Storage Location",
                    [None] + storage_options,
                    format_func=lambda x: "None" if x is None else format_storage_label(x),
                    key="buy_storage_add"
                )
                if stg:
                    storage_location_id = stg["id"]
                    storage_name = stg["name"]
            else:
                st.info("No storage locations yet. Add some in Admin → Storage.")

            lot_notes = st.text_input("Lot Notes", key="buy_lot_notes_add")

        if st.button("Add Line Item", type="secondary", key="add_buy_line"):
            if not coin_type_id:
                st.error("Please select a Coin Type.")
            else:
                self._add_buy_line_item(
                    selection, coin_type_id, quantity, unit_price,
                    purchase_grade_company, purchase_grade_text, purchase_numeric_grade,
                    slab_cert, estimated_grade_text, estimated_numeric_grade,
                    valuation_method, manual_est_unit_value, storage_location_id,
                    storage_name, lot_notes
                )

    def _render_add_sell_item_form(self, coin_types):
        """Render form to add a sell line item"""
        if coin_types:
            selection = st.selectbox(
                "Coin Type",
                coin_types,
                format_func=format_coin_type_label,
                key="sell_ct_add"
            )
            coin_type_id = selection["id"] if selection else None

            # Show available inventory for selected coin
            if coin_type_id:
                has_inv, msg, lots = self.repository.check_inventory_availability(coin_type_id, 0)
                if lots:
                    total = sum(lot.qty_remaining for lot in lots)
                    st.info(f"**Available to sell: {total}**")

                    # Show lot breakdown in expander
                    with st.expander("View lot details"):
                        for lot in lots:
                            st.write(
                                f"• Lot #{lot.lot_id}: {lot.qty_remaining} units (acquired {lot.acquired_date})")
                else:
                    st.warning("No inventory available for this coin type")
        else:
            st.warning("Add at least one Coin Type in Admin → Coin Types.")
            coin_type_id = None

        col1, col2 = st.columns(2)
        quantity = col1.number_input("Quantity to SELL", min_value=1, step=1, value=1,
                                     key="sell_qty_add")
        unit_price = col2.text_input("Unit Price (per coin)", value="0.00", key="sell_unit_add")

        if st.button("Add Line Item", type="secondary", key="add_sell_line"):
            if not coin_type_id:
                st.error("Please select a Coin Type.")
            else:
                self._add_sell_line_item(selection, coin_type_id, quantity, unit_price)

    def _add_buy_line_item(self, selection, coin_type_id, quantity, unit_price,
                           purchase_grade_company, purchase_grade_text, purchase_numeric_grade,
                           slab_cert, estimated_grade_text, estimated_numeric_grade,
                           valuation_method, manual_est_unit_value, storage_location_id,
                           storage_name, lot_notes):
        """Add a buy line item to session state"""
        try:
            unit_price_val = safe_float(unit_price)
            manual_val = safe_float(manual_est_unit_value)

            st.session_state.buy_line_items.append({
                "coin_type_id": int(coin_type_id),
                "display_label": format_coin_type_label(selection),
                "quantity": int(quantity),
                "unit_price": unit_price_val,
                "purchase_grade_company": purchase_grade_company or None,
                "purchase_grade_text": purchase_grade_text or None,
                "purchase_numeric_grade": float(purchase_numeric_grade or 0) or None,
                "slab_cert": slab_cert or None,
                "estimated_grade_text": estimated_grade_text or None,
                "estimated_numeric_grade": float(estimated_numeric_grade or 0) or None,
                "valuation_method": valuation_method,
                "manual_est_unit_value": manual_val or None,
                "storage_location_id": storage_location_id,
                "storage_name": storage_name,
                "lot_notes": lot_notes or None,
            })
            st.success(f"Added {format_coin_type_label(selection)} to transaction")
            st.rerun()
        except ValueError:
            st.error("Please enter valid numbers for price fields")

    def _add_sell_line_item(self, selection, coin_type_id, quantity, unit_price):
        """Add a sell line item to session state"""
        try:
            unit_price_val = safe_float(unit_price)

            # Check inventory availability
            has_inventory, error_msg, lots = self.repository.check_inventory_availability(
                coin_type_id, quantity)
            if not has_inventory:
                st.error(error_msg)
            else:
                st.session_state.sell_line_items.append({
                    "coin_type_id": int(coin_type_id),
                    "display_label": format_coin_type_label(selection),
                    "quantity": int(quantity),
                    "unit_price": unit_price_val
                })
                st.success(f"Added {format_coin_type_label(selection)} to transaction")
                st.rerun()
        except ValueError:
            st.error("Please enter valid numbers for price fields")

    def _save_buy_transaction(self, tx_date, party_name, currency, shipping, tax, fees, notes):
        """Save a buy transaction"""
        try:
            shipping_val = safe_float(shipping)
            tax_val = safe_float(tax)
            fees_val = safe_float(fees)

            create_buy_transaction(
                tx_date=tx_date.isoformat(),
                party_name=party_name,
                currency=currency,
                shipping=shipping_val,
                tax=tax_val,
                fees=fees_val,
                notes=notes,
                items=st.session_state.buy_line_items
            )
            st.success(
                f"BUY transaction saved with {len(st.session_state.buy_line_items)} line items!")
            st.session_state.buy_line_items = []  # Clear after saving
            st.rerun()
        except ValueError as e:
            st.error(f"Validation error: {e}")
        except Exception as e:
            st.error(f"Error saving transaction: {e}")

    def _save_sell_transaction(self, tx_date, party_name, currency, shipping, tax, fees, notes):
        """Save a sell transaction"""
        try:
            shipping_val = safe_float(shipping)
            tax_val = safe_float(tax)
            fees_val = safe_float(fees)

            # Verify all items have inventory available
            all_available = True
            for item in st.session_state.sell_line_items:
                has_inv, error_msg, _ = self.repository.check_inventory_availability(
                    item['coin_type_id'], item['quantity']
                )
                if not has_inv:
                    st.error(f"Inventory check failed: {error_msg}")
                    all_available = False
                    break

            if all_available:
                create_sell_transaction(
                    tx_date=tx_date.isoformat(),
                    party_name=party_name,
                    currency=currency,
                    shipping=shipping_val,
                    tax=tax_val,
                    fees=fees_val,
                    notes=notes,
                    items=st.session_state.sell_line_items,
                    method='FIFO'
                )
                st.success(
                    f"SELL transaction saved with {len(st.session_state.sell_line_items)} line items (FIFO)!")
                st.session_state.sell_line_items = []  # Clear after saving
                st.rerun()
        except ValueError as e:
            st.error(f"Validation error: {e}")
        except Exception as e:
            st.error(f"Error saving transaction: {e}")

    def render_edit_transaction_tab(self):
        """Render the Edit Transaction tab with search filters"""

        st.subheader("Find Transaction to Edit")

        # Search filters
        col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

        preset = col1.selectbox(
            "Quick range",
            ["30d", "90d", "YTD", "1y", "All"],
            index=2,  # Default to YTD
            key="tx_edit_preset"
        )

        start_dt, end_dt = calculate_date_range(preset)

        # Use preset in the key to force new widgets when preset changes
        # This ensures date_input uses the fresh value parameter
        if preset != "All":
            start_dt = col2.date_input("Start", value=start_dt, key=f"tx_edit_start_{preset}")
            end_dt = col3.date_input("End", value=end_dt, key=f"tx_edit_end_{preset}")
        else:
            start_dt = col2.date_input(
                "Start",
                value=date.today() - timedelta(days=365 * 5),
                key=f"tx_edit_start_{preset}"
            )
            end_dt = col3.date_input("End", value=date.today(), key=f"tx_edit_end_{preset}")

        tx_types = col4.multiselect(
            "Type",
            ["BUY", "SELL"],
            default=["BUY", "SELL"],
            key="tx_edit_types"
        )

        col5, col6, col7 = st.columns([2, 2, 2])

        # Use cached parties to avoid repeated queries
        repo_id = id(self.repository)
        parties = get_cached_parties(repo_id)

        party_selection = col5.selectbox(
            "Party (optional)",
            ["(any)"] + parties,
            index=0,
            key="tx_edit_party"
        )
        party = None if party_selection == "(any)" else party_selection

        search_text = col6.text_input(
            "Search text",
            key="tx_edit_search",
            placeholder="series, variety, notes..."
        )

        run_search = col7.button("🔍 Search", type="primary", key="tx_edit_run")

        # Store search results in session state
        if 'edit_search_results' not in st.session_state:
            st.session_state.edit_search_results = None

        if run_search:
            # Handle "All" preset
            if preset == "All":
                search_start, search_end = None, None
            else:
                search_start, search_end = start_dt, end_dt

            # Get matching transactions
            st.session_state.edit_search_results = self.repository.search_transactions_for_edit(
                search_start, search_end, tx_types, party, search_text
            )

        st.divider()

        # Show results and selection
        if st.session_state.edit_search_results is not None:
            transactions = st.session_state.edit_search_results

            if not transactions:
                st.info("No transactions matched your filters. Try adjusting your search criteria.")
            else:
                st.success(f"Found {len(transactions)} transaction(s)")

                # Transaction selector
                selected_idx = st.selectbox(
                    "Select transaction to edit:",
                    range(len(transactions)),
                    format_func=lambda x: format_transaction_label(transactions[x]),
                    key="tx_edit_select"
                )

                selected_tx_id = transactions[selected_idx].id

                st.divider()
                self._render_transaction_editor(selected_tx_id)
        else:
            st.info("👆 Use the filters above to search for a transaction to edit")

    def _render_transaction_editor(self, tx_id: int):
        """Render the transaction editing interface"""
        details = self.repository.get_transaction_details(tx_id)

        if not details:
            st.error("Transaction not found.")
            return

        header = details['header']
        items = details['items']

        st.subheader(f"Editing {header.tx_type} Transaction #{tx_id}")

        # Header editing
        with st.expander("Transaction Details", expanded=True):
            col1, col2, col3 = st.columns(3)

            new_date = col1.date_input("Date", value=pd.to_datetime(header.tx_date).date(),
                                       key=f"edit_date_{tx_id}")
            new_party = col2.text_input("Party", value=header.party_name, key=f"edit_party_{tx_id}")
            new_currency = col3.text_input("Currency", value=header.currency,
                                           key=f"edit_currency_{tx_id}")

            col1, col2, col3 = st.columns(3)
            new_shipping = col1.text_input("Shipping", value=format_float(header.shipping),
                                           key=f"edit_ship_{tx_id}")
            new_tax = col2.text_input("Tax", value=format_float(header.tax),
                                      key=f"edit_tax_{tx_id}")
            new_fees = col3.text_input("Fees", value=format_float(header.fees),
                                       key=f"edit_fees_{tx_id}")

            new_notes = st.text_area("Notes", value=header.notes or '', key=f"edit_notes_{tx_id}")

            if st.button("Update Transaction Details", key=f"update_header_{tx_id}"):
                updated_header = TransactionHeader(
                    id=tx_id,
                    tx_date=new_date.isoformat(),
                    tx_type=header.tx_type,
                    party_name=new_party,
                    currency=new_currency,
                    shipping=safe_float(new_shipping),
                    tax=safe_float(new_tax),
                    fees=safe_float(new_fees),
                    notes=new_notes
                )

                if self.repository.update_transaction_header(tx_id, updated_header):
                    st.success("Transaction details updated!")
                    st.rerun()

        # Items
        st.subheader("Items")
        self._render_transaction_items(items, header.tx_type)

        st.info(
            "💡 **Tip:** Changes to proof status affect the coin type globally (all instances of that coin). " +
            "All other changes only affect this specific transaction/lot.")

    def _render_transaction_items(self, items, tx_type: str):
        """Render transaction items for editing"""
        storage_locations = self.repository.get_storage_locations() if tx_type == 'BUY' else []
        storage_options = {loc['name']: loc['id'] for loc in storage_locations}

        for i, item in enumerate(items):
            item_label = format_item_label(item, i, tx_type)

            with st.expander(item_label, expanded=False):
                # Basic coin info (read-only)
                st.write(f"**Quantity:** {item.quantity}")

                # Proof status
                col1, col2 = st.columns(2)
                is_proof = col1.checkbox("Is Proof", value=item.is_proof,
                                         key=f"proof_{item.line_id}")

                if col2.button("Update Proof Status", key=f"update_proof_{item.line_id}"):
                    if self.repository.update_coin_type_proof_status(item.coin_type_id, is_proof):
                        st.success("Proof status updated!")
                        st.rerun()

                st.divider()

                # Purchase Information
                st.markdown("**Purchase Information**")
                col1, col2 = st.columns(2)
                new_price = col1.text_input("Unit Price", value=format_float(item.unit_price),
                                            key=f"price_{item.line_id}")
                new_condition = col2.text_input("Condition Notes", value=item.condition_notes or '',
                                                key=f"condition_{item.line_id}")

                # Grade Information
                st.markdown("**Grade Information**")
                col1, col2, col3 = st.columns(3)

                grade_co_index = 0
                if item.grade_company and item.grade_company in GRADE_COMPANIES:
                    grade_co_index = GRADE_COMPANIES.index(item.grade_company) + 1

                new_grade_co = col1.selectbox("Grade Company", [""] + GRADE_COMPANIES,
                                              index=grade_co_index, key=f"grade_co_{item.line_id}")
                new_purchase_grade = col2.text_input("Purchase Grade", value=item.grade_text or '',
                                                     key=f"purchase_grade_{item.line_id}")
                new_purchase_numeric = col3.text_input("Purchase Numeric",
                                                       value=format_float(item.numeric_grade,
                                                                          1) if item.numeric_grade else "0.0",
                                                       key=f"purchase_numeric_{item.line_id}")

                new_slab_cert = st.text_input("Slab Certificate #", value=item.slab_cert or '',
                                              key=f"slab_cert_{item.line_id}")

                # For BUY transactions, show additional lot-specific fields
                if tx_type == 'BUY' and item.lot_id:
                    st.divider()
                    st.markdown("**Current Evaluation**")

                    col1, col2 = st.columns(2)
                    new_est_grade = col1.text_input("Estimated Grade",
                                                    value=item.estimated_grade_text or '',
                                                    key=f"est_grade_{item.line_id}")
                    new_est_numeric = col2.text_input("Estimated Numeric",
                                                      value=format_float(
                                                          item.estimated_numeric_grade,
                                                          1) if item.estimated_numeric_grade else "0.0",
                                                      key=f"est_numeric_{item.line_id}")

                    st.markdown("**Valuation & Storage**")
                    col1, col2 = st.columns(2)

                    val_method_index = 0
                    if item.valuation_method and item.valuation_method in VALUATION_METHODS:
                        val_method_index = VALUATION_METHODS.index(item.valuation_method)

                    new_val_method = col1.selectbox("Valuation Method", VALUATION_METHODS,
                                                    index=val_method_index,
                                                    key=f"val_method_{item.line_id}")
                    new_manual_val = col2.text_input("Manual Value (if MANUAL)",
                                                     value=format_float(
                                                         item.manual_est_unit_value) if item.manual_est_unit_value else "0.00",
                                                     key=f"manual_val_{item.line_id}")

                    # Storage location
                    storage_idx = 0
                    if item.storage_name and item.storage_name in storage_options:
                        storage_names = list(storage_options.keys())
                        storage_idx = storage_names.index(item.storage_name) + 1

                    new_storage = st.selectbox("Storage Location",
                                               [""] + list(storage_options.keys()),
                                               index=storage_idx, key=f"storage_{item.line_id}")
                    new_lot_notes = st.text_area("Lot Notes", value=item.lot_notes or '',
                                                 key=f"lot_notes_{item.line_id}")

                # Single update button for everything
                if st.button("Update Item", type="primary", key=f"update_item_{item.line_id}"):
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
                    if tx_type == 'BUY' and item.lot_id:
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

                    if self.repository.update_item_details(item.line_id, item.lot_id, updates):
                        st.success("Item updated!")
                        st.rerun()
