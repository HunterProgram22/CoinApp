# pages/10_Inventory.py
import streamlit as st
import pandas as pd
from db_operations import execute_query_all, execute_query_single

st.header("Inventory")

# ---------------------------
# Data Access Functions
# ---------------------------
def get_inventory_by_type():
    """Get inventory grouped by coin type."""
    query = """
        SELECT
            ct.id AS coin_type_id,
            cm.series,
            ct.year,
            ct.mint_mark,
            COALESCE(ct.variety, '') AS variety,
            SUM(l.qty_remaining) AS coins_on_hand
        FROM lot l
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        WHERE l.qty_remaining > 0
        GROUP BY ct.id, cm.series, ct.year, ct.mint_mark, ct.variety
        ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety
    """
    return execute_query_all(query)


def get_inventory_by_series():
    """Get inventory summary by series using v_lot_value_details view."""
    # Check if view exists first
    view_check = execute_query_single(
        "SELECT 1 FROM sqlite_master WHERE type='view' AND name='v_lot_value_details'"
    )
    
    if view_check:
        query = """
            SELECT
                series,
                SUM(qty_remaining) AS coins,
                ROUND(SUM(qty_remaining * COALESCE(chosen_unit_value, 0)), 2) AS est_value_usd
            FROM v_lot_value_details
            GROUP BY series
            ORDER BY est_value_usd DESC, series
        """
    else:
        # Fallback if view doesn't exist
        query = """
            SELECT 
                cm.series AS series, 
                SUM(l.qty_remaining) AS coins, 
                NULL AS est_value_usd
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE l.qty_remaining > 0
            GROUP BY cm.series
            ORDER BY coins DESC, cm.series
        """
    
    return execute_query_all(query)


def get_series_list():
    """Get list of available series."""
    query = "SELECT DISTINCT series FROM coin_master ORDER BY series"
    results = execute_query_all(query)
    return [r['series'] for r in results]


def get_inventory_by_series_detail(series_name):
    """Get detailed inventory for a specific series."""
    # Check for specimen table and columns
    specimen_check = execute_query_single(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='specimen'"
    )
    
    flip_cte = ""
    flip_join = ""
    flip_select = "'' AS \"Flip IDs\","
    
    if specimen_check:
        # Check if specimen_code column exists
        code_check = execute_query_single(
            "SELECT 1 FROM pragma_table_info('specimen') WHERE name='specimen_code'"
        )
        
        if code_check:
            # Check if sold_line_id column exists
            sold_check = execute_query_single(
                "SELECT 1 FROM pragma_table_info('specimen') WHERE name='sold_line_id'"
            )
            
            where_unsold = " WHERE sold_line_id IS NULL" if sold_check else ""
            flip_cte = f"""
                WITH flip AS (
                    SELECT lot_id, GROUP_CONCAT(specimen_code, ', ') AS flip_ids
                    FROM specimen{where_unsold}
                    GROUP BY lot_id
                )
            """
            flip_join = "LEFT JOIN flip f ON f.lot_id = l.id"
            flip_select = "COALESCE(f.flip_ids, '') AS \"Flip IDs\","
    
    query = f"""
        {flip_cte}
        SELECT
            cm.series AS Series,
            ct.year AS Year,
            ct.mint_mark AS "Mint Mark",
            COALESCE(ct.variety, '') AS Variety,
            l.id AS lot_id,
            t.tx_date AS Acquired,
            COALESCE(p.name, '') AS Party,
            l.qty_remaining AS Qty,
            ROUND(l.unit_cost, 2) AS "Unit Cost (USD)",
            ROUND(v.melt_unit_value, 4) AS "Melt Unit Value",
            ROUND(v.chosen_unit_value, 2) AS "Chosen Unit Value",
            ROUND(l.qty_remaining * COALESCE(v.chosen_unit_value, 0), 2) AS "Lot Est. Value",
            COALESCE(l.estimated_grade_text, l.purchase_grade_text, '') AS Grade,
            {flip_select}
            COALESCE(l.slab_cert, '') AS "Cert #"
        FROM lot l
        JOIN tx_line tl ON tl.id = l.acquisition_line_id
        JOIN tx t ON t.id = tl.tx_id
        LEFT JOIN party p ON p.id = t.party_id
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
        {flip_join}
        WHERE l.qty_remaining > 0 AND cm.series = ?
        ORDER BY ct.year, ct.mint_mark, ct.variety, l.id
    """
    
    return execute_query_all(query, (series_name,))


def get_inventory_by_flags(want_proofs=False, want_slabbed=False):
    """Get inventory filtered by flags (proofs, slabbed)."""
    where_conditions = ["l.qty_remaining > 0"]
    params = []
    
    if want_proofs:
        where_conditions.append("ct.is_proof = 1")
    
    if want_slabbed:
        where_conditions.append(
            "(COALESCE(l.slab_cert, '') <> '' OR "
            "UPPER(COALESCE(l.purchase_grade_company, '')) IN ('PCGS','NGC','ANACS','ICG'))"
        )
    
    query = f"""
        SELECT
            cm.series AS Series,
            ct.year AS Year,
            ct.mint_mark AS "Mint Mark",
            COALESCE(ct.variety, '') AS Variety,
            l.id AS lot_id,
            l.qty_remaining AS Qty,
            ROUND(l.unit_cost, 2) AS "Unit Cost (USD)",
            ROUND(v.melt_unit_value, 4) AS "Melt Unit Value",
            ROUND(v.chosen_unit_value, 2) AS "Chosen Unit Value",
            ROUND(l.qty_remaining * COALESCE(v.chosen_unit_value, 0), 2) AS "Lot Est. Value",
            CASE WHEN ct.is_proof = 1 THEN 'Yes' ELSE 'No' END AS Proof,
            CASE WHEN (COALESCE(l.slab_cert, '') <> '' OR 
                      UPPER(COALESCE(l.purchase_grade_company, '')) IN ('PCGS','NGC','ANACS','ICG'))
                 THEN 'Yes' ELSE 'No' END AS Slabbed
        FROM lot l
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
        WHERE {" AND ".join(where_conditions)}
        ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety, l.id
    """
    
    return execute_query_all(query, params)


# ---------------------------
# Helper Functions
# ---------------------------
def format_year_columns_for_display(df: pd.DataFrame) -> pd.DataFrame:
    """Format year columns for display (handle NaN values)."""
    if df is None or df.empty:
        return df
    
    out = df.copy()
    year_columns = [c for c in out.columns if c.lower() in {"year", "years_start", "years_end"}]
    
    for col in year_columns:
        out[col] = pd.to_numeric(out[col], errors="coerce").map(
            lambda x: "" if pd.isna(x) else f"{int(x)}"
        )
    
    return out


def format_money_columns(df: pd.DataFrame, columns):
    """Return display copy with currency formatting; original df stays numeric for CSV."""
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


# ---------------------------
# UI Tabs
# ---------------------------
tab_type, tab_series, tab_series_detail, tab_flags = st.tabs(
    ["By Type", "By Series (summary)", "Filter by Series (detail)", "Filter by Flags"]
)

# ===== By Type =====
with tab_type:
    rows = get_inventory_by_type()
    df = pd.DataFrame(rows)
    
    if df.empty:
        st.info("No inventory yet.")
    else:
        # Hide internal ID and reorder columns
        if "coin_type_id" in df.columns:
            df = df.drop(columns=["coin_type_id"])
        
        # Reorder columns
        column_order = [c for c in ["series", "year", "mint_mark", "variety", "coins_on_hand"] if c in df.columns]
        remaining_columns = [c for c in df.columns if c not in column_order]
        df = df[column_order + remaining_columns]

        # Apply friendly labels
        df = df.rename(columns={
            "series": "Series",
            "year": "Year", 
            "mint_mark": "Mint Mark",
            "variety": "Variety",
            "coins_on_hand": "Qty on Hand",
        })
        
        # Format for display
        display_df = format_year_columns_for_display(df)
        st.dataframe(display_df, width=None, hide_index=True)
        create_download_button("Download CSV (By Type)", df, "inventory_by_type.csv")

# ===== By Series (summary) =====
with tab_series:
    rows = get_inventory_by_series()
    df = pd.DataFrame(rows)
    
    if df.empty:
        st.info("No inventory yet.")
    else:
        df = df.rename(columns={
            "series": "Series",
            "coins": "Coins", 
            "est_value_usd": "Est. Value (USD)"
        })
        
        display_df, csv_df = format_money_columns(df, ["Est. Value (USD)"])
        st.dataframe(display_df, width=None, hide_index=True)
        create_download_button("Download CSV (Series Summary)", csv_df, "inventory_by_series_summary.csv")

# ===== Filter by Series (detail) =====
with tab_series_detail:
    series_list = get_series_list()
    
    if not series_list:
        st.info("No series found in catalog (coin_master).")
    else:
        selected_series = st.selectbox("Series", options=series_list, key="inv_series_pick")
        
        rows = get_inventory_by_series_detail(selected_series)
        df = pd.DataFrame(rows)
        
        if df.empty:
            st.info("No on-hand lots for this series.")
        else:
            display_df = format_year_columns_for_display(df)
            st.dataframe(display_df, width=None, hide_index=True)
            filename = f"{selected_series}_detail.csv".replace(" ", "_")
            create_download_button("Download CSV (Series Detail)", df, filename)

# ===== Filter by Flags =====
with tab_flags:
    col1, col2 = st.columns(2)
    want_proofs = col1.checkbox("Proofs only", value=False, key="inv_flag_proofs")
    want_slabbed = col2.checkbox("Slabbed only (has cert or PCGS/NGC/ANACS/ICG)", value=False, key="inv_flag_slabbed")
    
    rows = get_inventory_by_flags(want_proofs, want_slabbed)
    df = pd.DataFrame(rows)
    
    if df.empty:
        st.info("No lots matched those flags.")
    else:
        display_df = format_year_columns_for_display(df)
        money_columns = ["Unit Cost (USD)", "Chosen Unit Value", "Lot Est. Value"]
        display_df, csv_df = format_money_columns(display_df, money_columns)
        st.dataframe(display_df, width=None, hide_index=True)
        create_download_button("Download CSV (Flags)", df, "inventory_filter_flags.csv")