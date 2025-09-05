# pages/10_Inventory.py
import streamlit as st
from auth_utils import require_auth

# Check authentication first
require_auth()

import pandas as pd
from db_operations import execute_query_all, execute_query_single
from inventory_helpers import (
    get_inventory_by_series_detail,
    get_inventory_by_flags,
    format_year_columns_for_display,
    format_money_columns,
    create_download_button
)

st.header("Inventory")


# ---------------------------
# Simple Data Access Functions (staying in main file)
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


# ---------------------------
# UI Tabs
# ---------------------------
tab_series, tab_type, tab_series_detail, tab_flags = st.tabs(
    ["By Series (summary)", "By Type", "Filter by Series (detail)", "Filter by Flags"]
)

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
        st.dataframe(display_df, width='stretch', hide_index=True)
        create_download_button("Download CSV (Series Summary)", csv_df,
                               "inventory_by_series_summary.csv")

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
        column_order = [c for c in ["series", "year", "mint_mark", "variety", "coins_on_hand"] if
                        c in df.columns]
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
        st.dataframe(display_df, width='stretch', hide_index=True)
        create_download_button("Download CSV (By Type)", df, "inventory_by_type.csv")

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
            # Hide the lot_id column for display
            if "lot_id" in df.columns:
                csv_df = df.copy()  # Keep lot_id in CSV
                df = df.drop(columns=["lot_id"])
            else:
                csv_df = df.copy()

            # Format year columns
            display_df = format_year_columns_for_display(df)

            # Format money columns - all currency columns should have $ and 2 decimals
            # except Melt Unit Value which should have 4 decimals
            money_columns = ["Unit Cost (USD)", "Melt Unit Value", "Chosen Unit Value",
                             "Lot Est. Value"]
            display_df, _ = format_money_columns(display_df, money_columns,
                                                 keep_melt_precision=True)

            st.dataframe(display_df, width='stretch', hide_index=True)
            filename = f"{selected_series}_detail.csv".replace(" ", "_")
            create_download_button("Download CSV (Series Detail)", csv_df, filename)

# ===== Filter by Flags =====
with tab_flags:
    col1, col2 = st.columns(2)
    want_proofs = col1.checkbox("Proofs only", value=False, key="inv_flag_proofs")
    want_slabbed = col2.checkbox("Slabbed only (has cert or PCGS/NGC/ANACS/ICG)", value=False,
                                 key="inv_flag_slabbed")

    rows = get_inventory_by_flags(want_proofs, want_slabbed)
    df = pd.DataFrame(rows)

    if df.empty:
        st.info("No lots matched those flags.")
    else:
        # Hide the lot_id column for display
        if "lot_id" in df.columns:
            csv_df = df.copy()  # Keep lot_id in CSV
            df = df.drop(columns=["lot_id"])
        else:
            csv_df = df.copy()

        # Format year columns
        display_df = format_year_columns_for_display(df)

        # Format money columns with proper precision
        money_columns = ["Unit Cost (USD)", "Melt Unit Value", "Chosen Unit Value",
                         "Lot Est. Value"]
        display_df, _ = format_money_columns(display_df, money_columns, keep_melt_precision=True)

        st.dataframe(display_df, width='stretch', hide_index=True)
        create_download_button("Download CSV (Flags)", csv_df, "inventory_filter_flags.csv")
