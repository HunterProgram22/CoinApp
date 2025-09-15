# pages/40_Storage_Report.py
import streamlit as st
from infrastructure.auth.auth_utils import require_auth

# Check authentication first
require_auth()
# pages/40_Storage_Report.py
import streamlit as st
import pandas as pd
from typing import List, Dict, Any, Optional
from db_operations import (execute_query_all, execute_query_single, execute_insert,
                           execute_update, execute_delete)

st.header("📦 Storage Location Report")


# ---------------------------------
# Data Access Functions
# ---------------------------------
def get_storage_locations(category_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get all storage locations with inventory counts, optionally filtered by category."""
    if category_filter and category_filter != "All":
        query = """
            SELECT 
                sl.id,
                sl.name,
                COALESCE(sl.category, '') AS category,
                COALESCE(sl.description, '') AS description,
                COUNT(l.id) AS lot_count,
                COALESCE(SUM(l.qty_remaining), 0) AS total_coins,
                COALESCE(SUM(l.qty_remaining * l.unit_cost), 0) AS total_cost_usd,
                COALESCE(SUM(l.qty_remaining * COALESCE(v.chosen_unit_value, l.unit_cost)), 0) AS total_value_usd
            FROM storage_location sl
            LEFT JOIN lot l ON l.storage_location_id = sl.id AND l.qty_remaining > 0
            LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
            WHERE sl.category = ?
            GROUP BY sl.id, sl.name, sl.category, sl.description
            ORDER BY sl.name
        """
        return execute_query_all(query, (category_filter,))
    else:
        query = """
            SELECT 
                sl.id,
                sl.name,
                COALESCE(sl.category, '') AS category,
                COALESCE(sl.description, '') AS description,
                COUNT(l.id) AS lot_count,
                COALESCE(SUM(l.qty_remaining), 0) AS total_coins,
                COALESCE(SUM(l.qty_remaining * l.unit_cost), 0) AS total_cost_usd,
                COALESCE(SUM(l.qty_remaining * COALESCE(v.chosen_unit_value, l.unit_cost)), 0) AS total_value_usd
            FROM storage_location sl
            LEFT JOIN lot l ON l.storage_location_id = sl.id AND l.qty_remaining > 0
            LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
            GROUP BY sl.id, sl.name, sl.category, sl.description
            ORDER BY sl.name
        """
        return execute_query_all(query)


def get_storage_categories() -> List[str]:
    """Get list of unique storage categories."""
    query = """
        SELECT DISTINCT category 
        FROM storage_location 
        WHERE category IS NOT NULL AND category != ''
        ORDER BY category
    """
    results = execute_query_all(query)
    return [r['category'] for r in results]


def get_category_summary(category: str) -> Dict[str, Any]:
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
    return result if result else {}


def get_inventory_by_storage(storage_id: int) -> List[Dict[str, Any]]:
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
            -- Add current estimated value using the view
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
    return execute_query_all(query, (storage_id,))


def get_unassigned_inventory() -> List[Dict[str, Any]]:
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
            -- Add current estimated value
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
    return execute_query_all(query)


def get_storage_summary() -> Dict[str, Any]:
    """Get overall storage summary statistics."""
    summary_query = """
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

    result = execute_query_single(summary_query)
    return result if result else {}


# ---------------------------------
# Helper Functions
# ---------------------------------
def format_year_columns_for_display(df: pd.DataFrame) -> pd.DataFrame:
    """Format year columns for display (handle NaN values)."""
    if df is None or df.empty:
        return df

    out = df.copy()
    if "year" in out.columns:
        out["year"] = pd.to_numeric(out["year"], errors="coerce").map(
            lambda x: "" if pd.isna(x) else f"{int(x)}"
        )
    return out


def format_money_columns(df: pd.DataFrame, columns: List[str]) -> tuple:
    """Return display and CSV versions with money formatting."""
    if df is None or df.empty:
        return df, df

    display_df = df.copy()
    for col in columns:
        if col in display_df.columns:
            display_df[col] = pd.to_numeric(display_df[col], errors="coerce").fillna(0.0).map(
                lambda x: f"${x:,.2f}"
            )

    return display_df, df


def create_download_button(label: str, df: pd.DataFrame, filename: str):
    """Create a CSV download button."""
    st.download_button(
        label,
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
    )


# ---------------------------------
# Storage Management Functions (NEW)
# ---------------------------------
def create_storage_location(name: str, category: str = None, description: str = None) -> int:
    """Create a new storage location."""
    query = "INSERT INTO storage_location (name, category, description) VALUES (?, ?, ?)"
    return execute_insert(query, (name, category, description))


def update_storage_location(storage_id: int, name: str, category: str = None,
                            description: str = None) -> int:
    """Update an existing storage location."""
    query = "UPDATE storage_location SET name = ?, category = ?, description = ? WHERE id = ?"
    return execute_update(query, (name, category, description, storage_id))


def delete_storage_location(storage_id: int) -> bool:
    """Delete a storage location if it has no inventory."""
    # Check if location has inventory
    check_query = "SELECT COUNT(*) as count FROM lot WHERE storage_location_id = ? AND qty_remaining > 0"
    result = execute_query_single(check_query, (storage_id,))

    if result and result['count'] > 0:
        return False  # Has inventory, cannot delete

    delete_query = "DELETE FROM storage_location WHERE id = ?"
    execute_delete(delete_query, (storage_id,))
    return True


def bulk_move_lots(lot_ids: List[int], new_storage_id: Optional[int]) -> int:
    """Move multiple lots to a new storage location."""
    if not lot_ids:
        return 0

    # Build the query with proper parameterization
    placeholders = ','.join('?' * len(lot_ids))
    query = f"UPDATE lot SET storage_location_id = ? WHERE id IN ({placeholders})"

    # Parameters: new_storage_id first, then all lot_ids
    params = [new_storage_id] + lot_ids
    return execute_update(query, tuple(params))


def get_lots_in_storage(storage_id: Optional[int]) -> List[Dict[str, Any]]:
    """Get all lots in a specific storage location (or unassigned if None)."""
    if storage_id is None:
        query = """
            SELECT 
                l.id,
                cm.series || ' ' || ct.year || 
                CASE WHEN ct.mint_mark != '' THEN ' ' || ct.mint_mark ELSE '' END ||
                CASE WHEN ct.variety != '' THEN ' • ' || ct.variety ELSE '' END AS description,
                l.qty_remaining,
                ROUND(l.unit_cost * l.qty_remaining, 2) as total_value
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE l.storage_location_id IS NULL AND l.qty_remaining > 0
            ORDER BY cm.series, ct.year
        """
        return execute_query_all(query)
    else:
        query = """
            SELECT 
                l.id,
                cm.series || ' ' || ct.year || 
                CASE WHEN ct.mint_mark != '' THEN ' ' || ct.mint_mark ELSE '' END ||
                CASE WHEN ct.variety != '' THEN ' • ' || ct.variety ELSE '' END AS description,
                l.qty_remaining,
                ROUND(l.unit_cost * l.qty_remaining, 2) as total_value
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE l.storage_location_id = ? AND l.qty_remaining > 0
            ORDER BY cm.series, ct.year
        """
        return execute_query_all(query, (storage_id,))


# ---------------------------------
# Tab Components
# ---------------------------------
def render_summary_tab():
    """Render the storage summary tab with category filtering."""
    st.subheader("Storage Summary")

    # Get available categories
    categories = get_storage_categories()
    category_options = ["All"] + categories

    # Category filter dropdown
    selected_category = st.selectbox(
        "Filter by Category:",
        category_options,
        index=0,
        key="storage_category_filter"
    )

    st.divider()

    # Show overall or category-specific metrics
    if selected_category == "All":
        # Overall summary metrics (existing code)
        summary = get_storage_summary()

        if summary:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Storage Locations", int(summary.get('total_locations', 0)))
            col2.metric("Locations with Inventory", int(summary.get('locations_with_inventory', 0)))
            col3.metric("Unassigned Coins", int(summary.get('unassigned_coins', 0)))
            col4.metric("Unassigned Value", f"${float(summary.get('unassigned_value', 0)):,.2f}")
    else:
        # Category-specific metrics
        category_summary = get_category_summary(selected_category)

        if category_summary:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric(f"Locations in '{selected_category}'",
                        int(category_summary.get('location_count', 0)))
            col2.metric("Total Coins", f"{int(category_summary.get('total_coins', 0)):,}")
            col3.metric("Total Cost", f"${float(category_summary.get('total_cost', 0)):,.2f}")
            col4.metric("Total Value", f"${float(category_summary.get('total_value', 0)):,.2f}")

    st.divider()

    # Storage locations table (filtered by category if selected)
    if selected_category == "All":
        st.markdown("### Storage Locations Overview")
    else:
        st.markdown(f"### Storage Locations in '{selected_category}'")

    locations = get_storage_locations(None if selected_category == "All" else selected_category)

    if not locations:
        if selected_category == "All":
            st.info("No storage locations defined. Add some in Admin → Storage.")
        else:
            st.info(f"No storage locations found in category '{selected_category}'.")
    else:
        # Convert to DataFrame for display
        df = pd.DataFrame(locations)

        # Drop the id column
        if 'id' in df.columns:
            df = df.drop(columns=['id'])

        df = df.rename(columns={
            "name": "Storage Location",
            "category": "Category",
            "description": "Description",
            "lot_count": "Lots",
            "total_coins": "Coins",
            "total_cost_usd": "Total Cost (USD)",
            "total_value_usd": "Total Value (USD)"
        })

        # Format money columns
        display_df, csv_df = format_money_columns(df, ["Total Cost (USD)", "Total Value (USD)"])

        st.dataframe(display_df, width='stretch', hide_index=True,
                     column_config={
                         "Lots": st.column_config.NumberColumn(format="%d"),
                         "Coins": st.column_config.NumberColumn(format="%d"),
                     })

        # Download button for storage summary
        filename = f"storage_summary_{selected_category.lower().replace(' ', '_')}.csv" if selected_category != "All" else "storage_summary.csv"
        create_download_button(
            f"📥 Download Storage Summary CSV ({selected_category})",
            csv_df,
            filename
        )

    st.divider()

    # Unassigned Inventory Section (only show when "All" is selected)
    if selected_category == "All":
        with st.expander("🚨 Unassigned Inventory", expanded=False):
            inventory = get_unassigned_inventory()

            if not inventory:
                st.info("✅ All inventory is assigned to storage locations.")
            else:
                st.warning(f"Found {len(inventory)} lots not assigned to any storage location.")

                # Summary
                total_coins = sum(item['quantity'] for item in inventory)
                total_cost = sum(item['lot_cost_usd'] for item in inventory)
                total_est_value = sum(item['est_value_usd'] for item in inventory)

                col1, col2, col3 = st.columns(3)
                col1.metric("Unassigned Coins", f"{total_coins:,}")
                col2.metric("Unassigned Cost", f"${total_cost:,.2f}")
                col3.metric("Unassigned Est. Value", f"${total_est_value:,.2f}")

                # Display table
                df = pd.DataFrame(inventory)

                # Hide lot_id and format display
                if "lot_id" in df.columns:
                    df = df.drop(columns=["lot_id"])

                # Rename columns
                df = df.rename(columns={
                    "series": "Series",
                    "year": "Year",
                    "mint_mark": "Mint Mark",
                    "variety": "Variety",
                    "is_proof": "Proof",
                    "quantity": "Qty",
                    "acquired_date": "Acquired",
                    "acquired_from": "From",
                    "unit_cost_usd": "Unit Cost (USD)",
                    "lot_cost_usd": "Lot Cost (USD)",
                    "est_value_usd": "Est. Value (USD)",
                    "grade": "Grade",
                    "cert_number": "Cert #",
                    "valuation_method": "Val. Method",
                    "notes": "Notes"
                })

                # Format for display
                display_df = format_year_columns_for_display(df)
                money_columns = ["Unit Cost (USD)", "Lot Cost (USD)", "Est. Value (USD)"]
                display_df, csv_df = format_money_columns(display_df, money_columns)

                st.dataframe(display_df, width='stretch', hide_index=True)

                # Download button
                create_download_button(
                    "Download Unassigned Inventory CSV",
                    csv_df,
                    "unassigned_inventory.csv"
                )

                st.info("💡 **Tip:** You can assign storage locations when editing transactions " +
                        "or by updating lots in the Admin section.")

    # Help section
    with st.expander("ℹ️ About Storage Reports"):
        st.markdown("""
        **Storage Location Reports help you:**
        - Track where your coins are physically stored
        - Filter by storage category (Safe, Bank Box, etc.)
        - See the total value stored in each location or category
        - Identify coins that haven't been assigned to a storage location
        - Generate lists for insurance or inventory purposes

        **To assign storage locations:**
        - Use the Transaction Editor to update existing transactions
        - Assign storage when adding new transactions
        - Update lot details in the Admin section

        **Tips:**
        - Set up storage locations in Admin → Storage first
        - Use descriptive names like "Home Safe", "Bank Box #123", etc.
        - Include category information to group similar storage types
        - Use the category filter to view specific types of storage
        """)


def render_detail_tab():
    """Render the storage detail tab."""
    st.subheader("Storage Location Details")

    # Get all storage locations for dropdown
    locations = get_storage_locations()

    if not locations:
        st.info("No storage locations defined. Add some in Admin → Storage.")
        return

    # Create dropdown options
    location_options = {
        f"{loc['name']}" + (f" ({loc['category']})" if loc['category'] else ""): loc['id']
        for loc in locations}

    # Add "Select a location" as the first option
    selected_location = st.selectbox(
        "Select storage location to view contents:",
        ["Select a location..."] + list(location_options.keys()),
        key="storage_detail_select"
    )

    if selected_location == "Select a location...":
        st.info("Please select a storage location from the dropdown above to view its contents.")
        return

    storage_id = location_options[selected_location]

    # Get location info
    location = execute_query_single(
        "SELECT name, category, description FROM storage_location WHERE id = ?",
        (storage_id,)
    )

    if not location:
        st.error("Storage location not found.")
        return

    st.divider()

    # Display location info
    st.markdown(f"### 📦 {location['name']}")
    if location['category']:
        st.caption(f"Category: {location['category']}")
    if location['description']:
        st.caption(f"Description: {location['description']}")

    # Get inventory
    inventory = get_inventory_by_storage(storage_id)

    if not inventory:
        st.info("No inventory found in this storage location.")
        return

    # Display summary stats
    total_coins = sum(item['quantity'] for item in inventory)
    total_cost = sum(item['lot_cost_usd'] for item in inventory)
    total_est_value = sum(item['est_value_usd'] for item in inventory)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Coins", f"{total_coins:,}")
    col2.metric("Total Cost", f"${total_cost:,.2f}")
    col3.metric("Est. Value", f"${total_est_value:,.2f}")

    st.divider()

    # Display inventory table
    df = pd.DataFrame(inventory)

    # Hide lot_id and format display
    if "lot_id" in df.columns:
        df = df.drop(columns=["lot_id"])

    # Rename columns for display
    df = df.rename(columns={
        "series": "Series",
        "year": "Year",
        "mint_mark": "Mint Mark",
        "variety": "Variety",
        "is_proof": "Proof",
        "quantity": "Qty",
        "acquired_date": "Acquired",
        "acquired_from": "From",
        "unit_cost_usd": "Unit Cost (USD)",
        "lot_cost_usd": "Lot Cost (USD)",
        "est_value_usd": "Est. Value (USD)",
        "grade": "Grade",
        "cert_number": "Cert #",
        "valuation_method": "Val. Method",
        "notes": "Notes"
    })

    # Format for display
    display_df = format_year_columns_for_display(df)
    money_columns = ["Unit Cost (USD)", "Lot Cost (USD)", "Est. Value (USD)"]
    display_df, csv_df = format_money_columns(display_df, money_columns)

    st.dataframe(display_df, width='stretch', hide_index=True)

    # Download button
    location_name = location['name'].replace(" ", "_").replace("/", "_")
    create_download_button(
        f"📥 Download CSV ({location['name']})",
        csv_df,
        f"storage_{location_name}_inventory.csv"
    )


def render_manage_storage_tab():
    """Render the manage storage locations tab."""
    st.subheader("Manage Storage Locations")

    # Add new storage location section
    with st.expander("➕ Add New Storage Location", expanded=False):
        with st.form("add_storage_form"):
            col1, col2 = st.columns(2)
            new_name = col1.text_input("Location Name*",
                                       placeholder="e.g., Home Safe, Bank Box #123")
            new_category = col2.text_input("Category", placeholder="e.g., Safe, Bank, Display")
            new_description = st.text_area("Description",
                                           placeholder="Optional description or notes", height=80)

            submitted = st.form_submit_button("Create Storage Location", type="primary")

            if submitted:
                if not new_name:
                    st.error("Location name is required.")
                else:
                    try:
                        storage_id = create_storage_location(
                            new_name,
                            new_category if new_category else None,
                            new_description if new_description else None
                        )
                        st.success(f"✅ Created storage location '{new_name}' (ID: {storage_id})")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to create storage location: {e}")

    st.divider()

    # Edit existing storage locations
    st.markdown("### Edit Existing Storage Locations")

    locations = get_storage_locations()

    if not locations:
        st.info("No storage locations defined yet. Add one above.")
    else:
        # Create a selectbox for choosing location to edit
        location_options = {
            f"{loc['name']}" + (f" ({loc['category']})" if loc['category'] else ""): loc
            for loc in locations
        }

        selected_location_name = st.selectbox(
            "Select location to edit:",
            list(location_options.keys()),
            key="edit_storage_select"
        )

        if selected_location_name:
            selected_location = location_options[selected_location_name]

            with st.form(f"edit_storage_{selected_location['id']}"):
                col1, col2 = st.columns(2)
                edit_name = col1.text_input("Location Name*", value=selected_location['name'])
                edit_category = col2.text_input("Category",
                                                value=selected_location['category'] or '')
                edit_description = st.text_area("Description",
                                                value=selected_location['description'] or '',
                                                height=80)

                # Show inventory count
                if selected_location['total_coins'] > 0:
                    st.info(
                        f"📦 This location contains {selected_location['total_coins']} coins in {selected_location['lot_count']} lots")

                col1, col2, col3 = st.columns(3)

                update_btn = col1.form_submit_button("💾 Update", type="primary")
                delete_btn = col2.form_submit_button("🗑️ Delete", type="secondary")

                if update_btn:
                    if not edit_name:
                        st.error("Location name is required.")
                    else:
                        try:
                            update_storage_location(
                                selected_location['id'],
                                edit_name,
                                edit_category if edit_category else None,
                                edit_description if edit_description else None
                            )
                            st.success(f"✅ Updated storage location '{edit_name}'")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to update: {e}")

                if delete_btn:
                    if selected_location['total_coins'] > 0:
                        st.error(
                            "Cannot delete location with inventory. Move or remove items first.")
                    else:
                        if delete_storage_location(selected_location['id']):
                            st.success(f"✅ Deleted storage location '{selected_location['name']}'")
                            st.rerun()
                        else:
                            st.error("Cannot delete location with inventory.")


def render_bulk_move_tab():
    """Render the bulk move items tab."""
    st.subheader("Bulk Move Items Between Storage Locations")

    # Get all storage locations
    locations = get_storage_locations()
    location_dict = {loc['name']: loc['id'] for loc in locations}
    location_options = ["Unassigned"] + list(location_dict.keys())

    col1, col2 = st.columns(2)

    # Source location
    source_location = col1.selectbox(
        "From Storage Location:",
        location_options,
        key="bulk_move_source"
    )

    # Destination location
    dest_location = col2.selectbox(
        "To Storage Location:",
        location_options,
        key="bulk_move_dest"
    )

    if source_location == dest_location:
        st.warning("⚠️ Source and destination locations are the same.")
        return

    # Get source location ID
    source_id = None if source_location == "Unassigned" else location_dict[source_location]

    # Get lots in source location
    lots = get_lots_in_storage(source_id)

    if not lots:
        st.info(f"No items found in '{source_location}'")
        return

    st.divider()

    # Display lots with checkboxes
    st.markdown(f"### Select items to move from '{source_location}' to '{dest_location}'")
    st.caption(f"Found {len(lots)} lots in {source_location}")

    # Use session state to track selections
    if 'selected_lot_ids' not in st.session_state:
        st.session_state.selected_lot_ids = []

    # Select/Deselect all buttons
    col1, col2, col3 = st.columns([1, 1, 4])
    if col1.button("Select All", key="select_all_btn"):
        st.session_state.selected_lot_ids = [lot['id'] for lot in lots]
    if col2.button("Deselect All", key="deselect_all_btn"):
        st.session_state.selected_lot_ids = []

    st.divider()

    # Display lots with checkboxes (outside of form for dynamic updates)
    selected_lots = []
    total_selected_items = 0
    total_selected_value = 0.0

    for i, lot in enumerate(lots):
        col1, col2, col3, col4 = st.columns([0.5, 4, 1, 1])

        # Checkbox with proper label
        is_selected = col1.checkbox(
            "Select",  # Provide a non-empty label
            value=(lot['id'] in st.session_state.selected_lot_ids),
            key=f"lot_select_{lot['id']}",
            label_visibility="collapsed"  # Hide the label but keep it for accessibility
        )

        if is_selected:
            if lot['id'] not in st.session_state.selected_lot_ids:
                st.session_state.selected_lot_ids.append(lot['id'])
            selected_lots.append(lot)
            total_selected_items += lot['qty_remaining']
            total_selected_value += lot['total_value']
        else:
            if lot['id'] in st.session_state.selected_lot_ids:
                st.session_state.selected_lot_ids.remove(lot['id'])

        # Description
        col2.write(lot['description'])

        # Quantity
        col3.write(f"Qty: {lot['qty_remaining']}")

        # Value
        col4.write(f"${lot['total_value']:,.2f}")

    st.divider()

    # Summary of selection
    if selected_lots:
        st.info(
            f"**Selected:** {len(selected_lots)} lots containing {total_selected_items} items worth ${total_selected_value:,.2f}")

        # Get destination ID
        dest_id = None if dest_location == "Unassigned" else location_dict[dest_location]

        # Move button (outside of form for immediate action)
        if st.button(
                f"🚚 Move {len(selected_lots)} Selected Items to '{dest_location}'",
                type="primary",
                key="move_items_btn"
        ):
            try:
                selected_lot_ids = [lot['id'] for lot in selected_lots]
                count = bulk_move_lots(selected_lot_ids, dest_id)
                st.success(
                    f"✅ Successfully moved {len(selected_lot_ids)} lots to '{dest_location}'")
                # Clear selections after successful move
                st.session_state.selected_lot_ids = []
                st.balloons()
                st.rerun()
            except Exception as e:
                st.error(f"Failed to move lots: {e}")
    else:
        st.info("Select items above to enable the move button")


# ---------------------------------
# Main UI with Tabs
# ---------------------------------

tabs = st.tabs([
    "📊 Storage Summary",
    "📋 Storage Details",
    "⚙️ Manage Storage",
    "📦 Bulk Move Items"
])

with tabs[0]:
    render_summary_tab()

with tabs[1]:
    render_detail_tab()

with tabs[2]:
    render_manage_storage_tab()

with tabs[3]:
    render_bulk_move_tab()
