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


def get_inventory_by_series(country_filter="All"):
    """Get inventory summary by series using v_lot_value_details view."""
    # Check if view exists first
    view_check = execute_query_single(
        "SELECT 1 FROM sqlite_master WHERE type='view' AND name='v_lot_value_details'"
    )

    # Build WHERE clause based on filter
    where_clause = ""
    if country_filter == "US Only":
        where_clause = "WHERE cm.country = 'USA'"
    elif country_filter == "World Only":
        where_clause = "WHERE cm.country != 'USA'"

    if view_check:
        query = f"""
            SELECT
                cm.series as series,
                cm.country,
                SUM(v.qty_remaining) AS coins,
                ROUND(SUM(v.qty_remaining * COALESCE(v.chosen_unit_value, 0)), 2) AS est_value_usd
            FROM v_lot_value_details v
            JOIN lot l ON l.id = v.lot_id
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            {where_clause}
            GROUP BY cm.series, cm.country
            ORDER BY est_value_usd DESC, cm.series
        """
    else:
        # Fallback if view doesn't exist
        query = f"""
            SELECT 
                cm.series AS series,
                cm.country,
                SUM(l.qty_remaining) AS coins, 
                NULL AS est_value_usd
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE l.qty_remaining > 0
            {' AND ' + where_clause.replace('WHERE ', '') if where_clause else ''}
            GROUP BY cm.series, cm.country
            ORDER BY coins DESC, cm.series
        """

    return execute_query_all(query)


def get_series_list():
    """Get list of available series."""
    query = "SELECT DISTINCT series FROM coin_master ORDER BY series"
    results = execute_query_all(query)
    return [r['series'] for r in results]


def get_countries_with_inventory():
    """Get list of countries that have inventory on hand."""
    query = """
        SELECT DISTINCT cm.country
        FROM lot l
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        WHERE l.qty_remaining > 0 AND cm.country IS NOT NULL
        ORDER BY cm.country
    """
    results = execute_query_all(query)
    return [r['country'] for r in results]


def get_series_list_for_country(country=None):
    """Get list of available series, optionally filtered by country."""
    if country:
        query = """
            SELECT DISTINCT cm.series 
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE l.qty_remaining > 0 AND cm.country = ?
            ORDER BY cm.series
        """
        results = execute_query_all(query, (country,))
    else:
        query = "SELECT DISTINCT series FROM coin_master ORDER BY series"
        results = execute_query_all(query)
    return [r['series'] for r in results]


# ---------------------------
# UI Tabs
# ---------------------------
tab_series, tab_series_detail, tab_flags = st.tabs(
    ["Series Summary", "Series Detail", "Filter by Flags"]
)

# ===== By Series (summary) =====
with tab_series:
    # Add country filter
    country_filter = st.radio(
        "Filter by:",
        ["All", "US Only", "World Only"],
        horizontal=True,
        key="series_country_filter"
    )

    rows = get_inventory_by_series(country_filter)
    df = pd.DataFrame(rows)

    if df.empty:
        filter_msg = f" ({country_filter.lower()})" if country_filter != "All" else ""
        st.info(f"No inventory yet{filter_msg}.")
    else:
        # Optionally show country column for "All" and "World Only" views
        show_country = country_filter in ["All", "World Only"]

        if not show_country and "country" in df.columns:
            df = df.drop(columns=["country"])

        df = df.rename(columns={
            "series": "Series",
            "country": "Country",
            "coins": "Coins",
            "est_value_usd": "Est. Value (USD)"
        })

        display_df, csv_df = format_money_columns(df, ["Est. Value (USD)"])
        st.dataframe(display_df, width='stretch', hide_index=True)

        # Add filter to filename
        filename_suffix = "_us" if country_filter == "US Only" else "_world" if country_filter == "World Only" else ""
        create_download_button(
            f"Download CSV (Series Summary{' - ' + country_filter if country_filter != 'All' else ''})",
            csv_df,
            f"inventory_by_series_summary{filename_suffix}.csv"
        )

# ===== Filter by Series (detail) =====
with tab_series_detail:
    # Get countries with inventory
    countries = get_countries_with_inventory()

    if not countries:
        st.info("No inventory found.")
    else:
        col1, col2 = st.columns(2)

        # Country dropdown (starts blank)
        selected_country = col1.selectbox(
            "Country",
            [""] + countries,
            index=0,
            key="inv_detail_country",
            help="Select a country to filter series"
        )

        # Series dropdown (dependent on country)
        if selected_country:
            series_list = get_series_list_for_country(selected_country)
            selected_series = col2.selectbox(
                "Series",
                [""] + series_list,
                index=0,
                key="inv_series_pick"
            )
        else:
            col2.selectbox(
                "Series",
                ["Select a country first"],
                index=0,
                key="inv_series_pick",
                disabled=True
            )
            selected_series = None

        # Only show results if both country and series are selected
        if selected_country and selected_series:
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
        elif selected_country:
            st.info("👆 Select a series above to view inventory details")
        else:
            st.info("👆 Select a country above to begin")

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
