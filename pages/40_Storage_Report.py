# pages/40_Storage_Report.py
import streamlit as st
from auth_utils import require_auth

# Check authentication first
require_auth()
# pages/40_Storage_Report.py
import streamlit as st
import pandas as pd
from typing import List, Dict, Any, Optional
from db_operations import execute_query_all, execute_query_single

st.header("📦 Storage Location Report")


# ---------------------------------
# Data Access Functions
# ---------------------------------
def get_storage_locations() -> List[Dict[str, Any]]:
    """Get all storage locations with inventory counts."""
    query = """
        SELECT 
            sl.id,
            sl.name,
            COALESCE(sl.category, '') AS category,
            COALESCE(sl.description, '') AS description,
            COUNT(l.id) AS lot_count,
            COALESCE(SUM(l.qty_remaining), 0) AS total_coins,
            COALESCE(SUM(l.qty_remaining * l.unit_cost), 0) AS total_cost_usd
        FROM storage_location sl
        LEFT JOIN lot l ON l.storage_location_id = sl.id AND l.qty_remaining > 0
        GROUP BY sl.id, sl.name, sl.category, sl.description
        ORDER BY sl.name
    """
    return execute_query_all(query)


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
# Tab Components
# ---------------------------------
def render_summary_tab():
    """Render the storage summary tab."""
    st.subheader("Storage Summary")

    # Overall summary metrics
    summary = get_storage_summary()

    if summary:
        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Total Storage Locations", int(summary.get('total_locations', 0)))
        col2.metric("Locations with Inventory", int(summary.get('locations_with_inventory', 0)))
        col3.metric("Unassigned Coins", int(summary.get('unassigned_coins', 0)))
        col4.metric("Unassigned Value", f"${float(summary.get('unassigned_value', 0)):,.2f}")

    st.divider()

    # Storage locations table
    st.markdown("### Storage Locations Overview")

    locations = get_storage_locations()

    if not locations:
        st.info("No storage locations defined. Add some in Admin → Storage.")
    else:
        # Convert to DataFrame for display
        df = pd.DataFrame(locations)

        # Drop the id column as requested
        if 'id' in df.columns:
            df = df.drop(columns=['id'])

        df = df.rename(columns={
            "name": "Storage Location",
            "category": "Category",
            "description": "Description",
            "lot_count": "Lots",
            "total_coins": "Coins",
            "total_cost_usd": "Total Cost (USD)"
        })

        # Format money columns
        display_df, csv_df = format_money_columns(df, ["Total Cost (USD)"])

        st.dataframe(display_df, width='stretch', hide_index=True,
                     column_config={
                         "Lots": st.column_config.NumberColumn(format="%d"),
                         "Coins": st.column_config.NumberColumn(format="%d"),
                     })

        # Download button for storage summary
        create_download_button(
            "📥 Download Storage Summary CSV",
            csv_df,
            "storage_summary.csv"
        )

    st.divider()

    # Unassigned Inventory Section
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
        - See the total value stored in each location
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


# ---------------------------------
# Main UI with Tabs
# ---------------------------------

tabs = st.tabs([
    "📊 Storage Summary",
    "📋 Storage Details"
])

with tabs[0]:
    render_summary_tab()

with tabs[1]:
    render_detail_tab()
