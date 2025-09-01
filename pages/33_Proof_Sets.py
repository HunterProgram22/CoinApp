# pages/33_Proof_Sets.py
import streamlit as st
import pandas as pd
from datetime import date
from typing import List, Dict, Any, Optional
from db_operations import execute_query_all, execute_query_single, execute_insert, execute_update, \
    execute_delete
from db import get_conn
from input_helpers import safe_float, safe_int, format_float

st.header("🎁 Proof Sets & Mint Sets")


# ---------------------------------
# Data Access Functions
# ---------------------------------
def get_proof_set_masters() -> List[Dict[str, Any]]:
    """Get all proof set definitions."""
    query = """
        SELECT id, country, year, set_type, set_name, coin_count, 
               includes_silver, original_mint_price
        FROM proof_set_master
        ORDER BY country, year DESC, set_type
    """
    return execute_query_all(query)


def get_inventory_summary() -> pd.DataFrame:
    """Get summary of proof set inventory."""
    query = """
        SELECT * FROM v_proof_set_summary
        ORDER BY country, year DESC, set_type
    """
    results = execute_query_all(query)
    return pd.DataFrame(results) if results else pd.DataFrame()


def get_inventory_details(country: Optional[str] = None,
                          year: Optional[int] = None,
                          set_type: Optional[str] = None,
                          show_sold: bool = False) -> pd.DataFrame:
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
    return pd.DataFrame(results) if results else pd.DataFrame()


def add_proof_set_master(country: str, year: int, set_type: str, set_name: str, **kwargs) -> int:
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


def add_inventory_item(set_master_id: int, acquisition_date: str,
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


def update_current_value(inventory_id: int, current_value: float, value_date: str) -> bool:
    """Update current value of an inventory item."""
    query = """
        UPDATE proof_set_inventory 
        SET current_value = ?, value_as_of = ?
        WHERE id = ?
    """
    return execute_update(query, (current_value, value_date, inventory_id)) > 0


def record_sale(inventory_id: int, sold_date: str, sold_price: float,
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


def get_storage_locations() -> List[Dict[str, Any]]:
    """Get all storage locations."""
    query = "SELECT id, name, category FROM storage_location ORDER BY name"
    return execute_query_all(query)


def get_portfolio_summary() -> Dict[str, Any]:
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

    # Ensure we always return valid numbers, not None
    if result:
        return {
            'items': result.get('items') or 0,
            'total_cost': float(result.get('total_cost') or 0),
            'total_value': float(result.get('total_value') or 0),
            'unrealized_gl': float(result.get('unrealized_gl') or 0)
        }
    else:
        return {
            'items': 0,
            'total_cost': 0.0,
            'total_value': 0.0,
            'unrealized_gl': 0.0
        }


# ---------------------------------
# UI Tabs
# ---------------------------------
tabs = st.tabs(["📊 Overview", "➕ Add to Inventory", "📝 Manage Inventory",
                "🏷️ Define Set Types", "📈 Market Values"])

# ===== Overview Tab =====
with tabs[0]:
    st.subheader("Proof Set Portfolio Overview")

    # Portfolio summary
    portfolio = get_portfolio_summary()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Sets", portfolio['items'])
    col2.metric("Total Cost", f"${portfolio['total_cost']:,.2f}")
    col3.metric("Current Value", f"${portfolio['total_value']:,.2f}")

    gl = portfolio['unrealized_gl']
    gl_color = "normal" if gl >= 0 else "inverse"
    col4.metric("Unrealized G/L", f"${gl:,.2f}", delta_color=gl_color)

    # Summary table
    st.subheader("Inventory Summary")
    summary_df = get_inventory_summary()

    if not summary_df.empty:
        # Format columns - handle None values
        money_columns = ['total_cost', 'total_current_value', 'avg_cost', 'min_cost', 'max_cost']
        for col in money_columns:
            if col in summary_df.columns:
                summary_df[col] = summary_df[col].apply(
                    lambda x: f"${float(x):,.2f}" if pd.notna(x) and x is not None else "$0.00"
                )

        st.dataframe(summary_df, hide_index=True, width="stretch")
    else:
        st.info("No proof sets in inventory yet.")

    # Detailed inventory
    st.subheader("Detailed Inventory")

    # Filters
    col1, col2, col3, col4 = st.columns(4)

    countries = execute_query_all("SELECT DISTINCT country FROM proof_set_master ORDER BY country")
    country_filter = col1.selectbox("Country", ["All"] + [c['country'] for c in countries])

    years = execute_query_all("SELECT DISTINCT year FROM proof_set_master ORDER BY year DESC")
    year_filter = col2.selectbox("Year", ["All"] + [y['year'] for y in years])

    set_types = ['All', 'PROOF', 'SILVER_PROOF', 'MINT', 'PRESTIGE', 'PREMIER', 'DELUXE', 'OTHER']
    type_filter = col3.selectbox("Set Type", set_types)

    show_sold = col4.checkbox("Show Sold Sets", value=False)

    # Get filtered inventory
    details_df = get_inventory_details(
        country=country_filter if country_filter != "All" else None,
        year=year_filter if year_filter != "All" else None,
        set_type=type_filter if type_filter != "All" else None,
        show_sold=show_sold
    )

    if not details_df.empty:
        # Format display columns
        display_df = details_df.copy()

        # Format money columns - handle None values
        money_cols = ['acquisition_price', 'current_value', 'unrealized_gain_loss',
                      'sold_price', 'realized_gain_loss']
        for col in money_cols:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(
                    lambda x: f"${float(x):,.2f}" if pd.notna(x) and x is not None else ""
                )

        # Format percentage
        if 'gain_loss_percent' in display_df.columns:
            display_df['gain_loss_percent'] = display_df['gain_loss_percent'].apply(
                lambda x: f"{float(x):.1f}%" if pd.notna(x) and x is not None else ""
            )

        # Select columns to display
        display_cols = ['country', 'year', 'set_type', 'set_name', 'condition',
                        'acquisition_date', 'acquisition_price', 'current_value',
                        'unrealized_gain_loss', 'gain_loss_percent', 'storage_location']

        if show_sold:
            display_cols.extend(['sold_date', 'sold_price', 'realized_gain_loss'])

        display_cols = [c for c in display_cols if c in display_df.columns]

        st.dataframe(display_df[display_cols], hide_index=True, width="stretch")

        # Download button
        csv = details_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Download Inventory CSV",
            data=csv,
            file_name="proof_set_inventory.csv",
            mime="text/csv"
        )
    else:
        st.info("No sets match the selected filters.")

# ===== Add to Inventory Tab =====
with tabs[1]:
    st.subheader("Add Proof Set to Inventory")

    # Get master sets
    masters = get_proof_set_masters()

    if not masters:
        st.warning(
            "No proof set types defined yet. Please define set types in the 'Define Set Types' tab first.")
    else:
        # Select or create master
        master_options = {
            f"{m['country']} {m['year']} {m['set_type'].replace('_', ' ')}: {m['set_name']}": m[
                'id']
            for m in masters
        }

        selected_master = st.selectbox("Select Proof Set Type", list(master_options.keys()))
        set_master_id = master_options[selected_master]

        # Acquisition details
        st.markdown("### Acquisition Details")

        col1, col2 = st.columns(2)
        acq_date = col1.date_input("Acquisition Date", value=date.today())
        acq_price = col2.text_input("Acquisition Price ($)", value="0.00")

        col1, col2 = st.columns(2)
        party_name = col1.text_input("Acquired From (Dealer/Person)")
        condition = col2.selectbox("Condition", ['SEALED', 'OPENED', 'DAMAGED', 'PARTIAL'])

        col1, col2 = st.columns(2)
        has_coa = col1.checkbox("Has Certificate of Authenticity", value=True)
        has_box = col2.checkbox("Has Original Box/Packaging", value=True)

        # Storage
        storage_locations = get_storage_locations()
        storage_options = {f"{s['name']} ({s['category']})" if s['category']
                           else s['name']: s['id'] for s in storage_locations}
        storage_selection = st.selectbox("Storage Location",
                                         ["Not Assigned"] + list(storage_options.keys()))

        # Current value (optional)
        st.markdown("### Current Market Value (Optional)")
        col1, col2 = st.columns(2)
        current_value = col1.text_input("Current Value ($)", value="0.00")
        value_as_of = col2.date_input("Value As Of", value=date.today())

        # Notes
        purchase_notes = st.text_area("Purchase Notes")
        general_notes = st.text_area("General Notes")

        # Save button
        if st.button("Add to Inventory", type="primary"):
            acq_price_val = safe_float(acq_price)
            current_value_val = safe_float(current_value)

            if acq_price_val <= 0:
                st.error("Please enter an acquisition price.")
            else:
                storage_id = storage_options.get(
                    storage_selection) if storage_selection != "Not Assigned" else None

                inv_id = add_inventory_item(
                    set_master_id=set_master_id,
                    acquisition_date=acq_date.isoformat(),
                    acquisition_price=acq_price_val,
                    party_name=party_name,
                    condition=condition,
                    has_coa=has_coa,
                    has_original_box=has_box,
                    storage_location_id=storage_id,
                    purchase_notes=purchase_notes,
                    current_value=current_value_val if current_value_val > 0 else None,
                    value_as_of=value_as_of.isoformat() if current_value_val > 0 else None,
                    notes=general_notes
                )

                st.success(f"Proof set added to inventory! (ID: {inv_id})")
                st.rerun()

# ===== Manage Inventory Tab =====
with tabs[2]:
    st.subheader("Manage Inventory Items")

    # Get inventory items not sold
    inventory = get_inventory_details(show_sold=False)

    if inventory.empty:
        st.info("No proof sets in inventory.")
    else:
        # Select item to manage
        inv_options = {}
        for _, row in inventory.iterrows():
            price = float(row['acquisition_price']) if pd.notna(row['acquisition_price']) else 0.0
            label = f"{row['country']} {row['year']} {row['set_type']} - Acquired {row['acquisition_date']} - ${price:.2f}"
            inv_options[label] = row['id']

        selected_item = st.selectbox("Select Inventory Item", list(inv_options.keys()))
        inv_id = inv_options[selected_item]

        # Get full details
        item = inventory[inventory['id'] == inv_id].iloc[0]

        # Display current details
        st.markdown("### Current Details")
        col1, col2, col3 = st.columns(3)
        col1.write(f"**Set:** {item['set_name']}")
        col2.write(f"**Condition:** {item['condition']}")
        col3.write(f"**Storage:** {item['storage_location'] or 'Not Assigned'}")

        col1, col2, col3 = st.columns(3)
        acq_price = float(item['acquisition_price']) if pd.notna(item['acquisition_price']) else 0.0
        col1.write(f"**Cost:** ${acq_price:,.2f}")

        if pd.notna(item['current_value']) and item['current_value'] is not None:
            curr_val = float(item['current_value'])
            col2.write(f"**Current Value:** ${curr_val:,.2f}")
        else:
            col2.write("**Current Value:** Not Set")

        if pd.notna(item['unrealized_gain_loss']) and item['unrealized_gain_loss'] is not None:
            ugl = float(item['unrealized_gain_loss'])
            color = "🟢" if ugl >= 0 else "🔴"
            col3.write(f"**Unrealized G/L:** {color} ${ugl:,.2f}")

        # Actions
        st.markdown("### Actions")

        action = st.radio("Select Action", ["Update Value", "Record Sale", "Edit Details"],
                         key=f"action_radio_{inv_id}")

        if action == "Update Value":
            col1, col2 = st.columns(2)
            current_val = float(item['current_value']) if pd.notna(item['current_value']) and item[
                'current_value'] is not None else 0.0
            new_value = col1.text_input("New Current Value ($)",
                                       value=format_float(current_val),
                                       key=f"new_value_{inv_id}")
            new_value_date = col2.date_input("Value As Of",
                                            value=date.today(),
                                            key=f"value_date_{inv_id}")

            if st.button("Update Value", type="primary", key=f"update_value_btn_{inv_id}"):
                new_value_val = safe_float(new_value)
                if update_current_value(inv_id, new_value_val, new_value_date.isoformat()):
                    st.success("Value updated!")
                    st.rerun()

        elif action == "Record Sale":
            col1, col2, col3 = st.columns(3)
            sale_date = col1.date_input("Sale Date",
                                       value=date.today(),
                                       key=f"sale_date_{inv_id}")
            sale_price = col2.text_input("Sale Price ($)",
                                        value="0.00",
                                        key=f"sale_price_{inv_id}")
            sold_to = col3.text_input("Sold To",
                                     key=f"sold_to_{inv_id}")

            sale_price_val = safe_float(sale_price)
            if sale_price_val > 0:
                acq_price = float(item['acquisition_price']) if pd.notna(
                    item['acquisition_price']) else 0.0
                realized_gl = sale_price_val - acq_price
                color = "🟢" if realized_gl >= 0 else "🔴"
                st.write(f"**Realized Gain/Loss:** {color} ${realized_gl:,.2f}")

            if st.button("Record Sale", type="primary", key=f"record_sale_btn_{inv_id}"):
                if sale_price_val <= 0:
                    st.error("Please enter a sale price.")
                else:
                    if record_sale(inv_id, sale_date.isoformat(), sale_price_val, sold_to):
                        st.success("Sale recorded!")
                        st.rerun()

# ===== Define Set Types Tab =====
with tabs[3]:
    st.subheader("Define Proof Set Types")

    # Display existing masters
    masters_df = pd.DataFrame(get_proof_set_masters())

    if not masters_df.empty:
        st.markdown("### Existing Set Types")
        display_df = masters_df[['country', 'year', 'set_type', 'set_name',
                                 'coin_count', 'includes_silver', 'original_mint_price']].copy()
        display_df['includes_silver'] = display_df['includes_silver'].apply(
            lambda x: '✓' if x else '')
        display_df['original_mint_price'] = display_df['original_mint_price'].apply(
            lambda x: f"${float(x):,.2f}" if pd.notna(x) and x is not None else ""
        )
        st.dataframe(display_df, hide_index=True, width="stretch")

    # Add new master
    st.markdown("### Add New Set Type")

    with st.form("add_master_form"):
        col1, col2, col3 = st.columns(3)
        country = col1.text_input("Country*", value="United States")
        year = col2.number_input("Year*", min_value=1900, max_value=2100, value=date.today().year)
        set_type = col3.selectbox("Set Type*",
                                  ['PROOF', 'SILVER_PROOF', 'MINT', 'PRESTIGE',
                                   'PREMIER', 'DELUXE', 'OTHER'])

        set_name = st.text_input("Set Name*",
                                 placeholder="e.g., US Proof Set, Canadian Silver Proof Set")

        col1, col2, col3 = st.columns(3)
        mint_mark = col1.text_input("Mint Mark (if applicable)")
        coin_count = col2.number_input("Number of Coins", min_value=0, value=0)
        face_value = col3.text_input("Face Value ($)", value="0.00")

        col1, col2, col3 = st.columns(3)
        original_price = col1.text_input("Original Mint Price ($)", value="0.00")
        includes_silver = col2.checkbox("Contains Silver Coins")
        packaging = col3.text_input("Packaging Type", placeholder="e.g., Plastic Case, Wooden Box")

        special_features = st.text_input("Special Features",
                                         placeholder="e.g., 50 State Quarters, America the Beautiful")
        notes = st.text_area("Notes")

        if st.form_submit_button("Add Set Type", type="primary"):
            if not all([country, year, set_type, set_name]):
                st.error("Please fill in all required fields (marked with *)")
            else:
                face_value_val = safe_float(face_value)
                original_price_val = safe_float(original_price)

                master_id = add_proof_set_master(
                    country=country,
                    year=year,
                    set_type=set_type,
                    set_name=set_name,
                    mint_mark=mint_mark if mint_mark else None,
                    face_value=face_value_val if face_value_val > 0 else None,
                    original_mint_price=original_price_val if original_price_val > 0 else None,
                    coin_count=coin_count if coin_count > 0 else None,
                    includes_silver=includes_silver,
                    special_features=special_features if special_features else None,
                    packaging_type=packaging if packaging else None,
                    notes=notes if notes else None
                )
                st.success(f"Set type added! (ID: {master_id})")
                st.rerun()

# ===== Market Values Tab =====
with tabs[4]:
    st.subheader("Track Market Values")

    masters = get_proof_set_masters()

    if not masters:
        st.info("No proof set types defined yet.")
    else:
        # Select master
        master_options = {
            f"{m['country']} {m['year']} {m['set_type']}: {m['set_name']}": m['id']
            for m in masters
        }

        selected_master = st.selectbox("Select Set Type", list(master_options.keys()))
        master_id = master_options[selected_master]

        # Display value history
        value_history = execute_query_all("""
            SELECT value_date, source, condition, market_value, notes
            FROM proof_set_values
            WHERE set_master_id = ?
            ORDER BY value_date DESC
        """, (master_id,))

        if value_history:
            st.markdown("### Value History")
            history_df = pd.DataFrame(value_history)
            history_df['market_value'] = history_df['market_value'].apply(lambda x: f"${x:,.2f}")
            st.dataframe(history_df, hide_index=True, width="stretch")

        # Add new value
        st.markdown("### Add Market Value")

        col1, col2, col3 = st.columns(3)
        value_date = col1.date_input("Date", value=date.today())
        market_value = col2.text_input("Market Value ($)", value="0.00")
        source = col3.text_input("Source", placeholder="e.g., eBay, PCGS, Red Book")

        col1, col2 = st.columns(2)
        condition = col1.selectbox("Condition", ['SEALED', 'OPENED', 'ANY'])
        value_notes = col2.text_input("Notes")

        if st.button("Add Market Value", type="primary"):
            market_value_val = safe_float(market_value)
            if market_value_val <= 0:
                st.error("Please enter a market value.")
            elif not source:
                st.error("Please enter a source.")
            else:
                execute_insert("""
                    INSERT INTO proof_set_values 
                    (set_master_id, value_date, source, condition, market_value, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (master_id, value_date.isoformat(), source, condition,
                      market_value_val, value_notes if value_notes else None))

                st.success("Market value added!")
                st.rerun()

# Footer
st.markdown("---")
with st.expander("ℹ️ About Proof Sets"):
    st.markdown("""
    **Proof Set Types:**
    - **Proof Sets** - Regular proof sets with specially struck coins
    - **Silver Proof Sets** - Proof sets where some/all coins contain silver
    - **Mint Sets** - Uncirculated coins from that year (not proof finish)
    - **Prestige Sets** - Premium proof sets with commemorative coins
    - **Premier Sets** - Canadian premium proof sets
    - **Deluxe Sets** - Special packaging or additional coins

    **Tips:**
    - Track both sealed and opened sets separately
    - Update market values periodically to track performance
    - Note storage location for insurance purposes
    - Keep purchase receipts and certificates of authenticity
    """)
