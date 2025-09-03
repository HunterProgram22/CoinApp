# pages/15_World_Coins.py
import streamlit as st
from auth_utils import require_auth

# Check authentication first
require_auth()
import streamlit as st
import pandas as pd
from db_operations import execute_query_all, execute_query_single

st.header("World Coins")

# ---------------------------------
# Data Access Functions
# ---------------------------------
def get_countries_on_hand():
    """Get list of countries with inventory on hand."""
    query = """
        SELECT DISTINCT COALESCE(cm.country, '') AS country
        FROM lot l
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        WHERE l.qty_remaining > 0 AND COALESCE(cm.country, '') <> ''
        ORDER BY country
    """
    results = execute_query_all(query)
    return [r["country"] for r in results]


def check_asset_category_support():
    """Check if coin_master table has asset_category column."""
    try:
        result = execute_query_single(
            "SELECT 1 FROM pragma_table_info('coin_master') WHERE name='asset_category'"
        )
        return bool(result)
    except Exception:
        return False


def get_world_coins_summary(country, want_proofs=False, want_slabbed=False, asset_category=None):
    """Get summary data for world coins by series."""
    where_conditions = ["cm.country = ?", "l.qty_remaining > 0"]
    params = [country]
    
    if want_proofs:
        where_conditions.append("ct.is_proof = 1")
    
    if want_slabbed:
        where_conditions.append(
            "(COALESCE(l.slab_cert, '') <> '' OR "
            "UPPER(COALESCE(l.purchase_grade_company, '')) IN ('PCGS','NGC','ANACS','ICG'))"
        )
    
    if asset_category and asset_category != "All":
        where_conditions.append("cm.asset_category = ?")
        params.append(asset_category)
    
    where_clause = " AND ".join(where_conditions)
    
    # Check if v_lot_value_details view exists
    view_check = execute_query_single(
        "SELECT 1 FROM sqlite_master WHERE type='view' AND name='v_lot_value_details'"
    )
    
    if view_check:
        query = f"""
            SELECT
                cm.series AS Series,
                SUM(v.qty_remaining) AS Coins,
                ROUND(SUM(v.qty_remaining * COALESCE(v.melt_unit_value, 0)), 2) AS "Melt Value (USD)",
                ROUND(SUM(v.qty_remaining * COALESCE(v.chosen_unit_value, 0)), 2) AS "Est. Value (USD)"
            FROM v_lot_value_details v
            JOIN lot l ON l.id = v.lot_id
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE {where_clause}
            GROUP BY cm.series
            ORDER BY "Est. Value (USD)" DESC, cm.series
        """
    else:
        # Fallback without valuation view
        query = f"""
            SELECT
                cm.series AS Series,
                SUM(l.qty_remaining) AS Coins,
                NULL AS "Melt Value (USD)",
                NULL AS "Est. Value (USD)"
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE {where_clause}
            GROUP BY cm.series
            ORDER BY Coins DESC, cm.series
        """
    
    return execute_query_all(query, params)


def get_world_coins_detail(country, want_proofs=False, want_slabbed=False, asset_category=None):
    """Get detailed data for world coins."""
    where_conditions = ["cm.country = ?", "l.qty_remaining > 0"]
    params = [country]
    
    if want_proofs:
        where_conditions.append("ct.is_proof = 1")
    
    if want_slabbed:
        where_conditions.append(
            "(COALESCE(l.slab_cert, '') <> '' OR "
            "UPPER(COALESCE(l.purchase_grade_company, '')) IN ('PCGS','NGC','ANACS','ICG'))"
        )
    
    if asset_category and asset_category != "All":
        where_conditions.append("cm.asset_category = ?")
        params.append(asset_category)
    
    where_clause = " AND ".join(where_conditions)
    
    # Check for specimen table and features
    specimen_check = execute_query_single(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='specimen'"
    )
    
    flip_cte = ""
    flip_join = ""
    flip_select = "'' AS \"Flip IDs\","
    
    if specimen_check:
        code_check = execute_query_single(
            "SELECT 1 FROM pragma_table_info('specimen') WHERE name='specimen_code'"
        )
        
        if code_check:
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
    
    # Check if v_lot_value_details view exists
    view_check = execute_query_single(
        "SELECT 1 FROM sqlite_master WHERE type='view' AND name='v_lot_value_details'"
    )
    
    if view_check:
        value_columns = """
            ROUND(v.melt_unit_value, 4) AS "Melt Unit Value",
            ROUND(v.chosen_unit_value, 2) AS "Chosen Unit Value",
            ROUND(l.qty_remaining * COALESCE(v.chosen_unit_value, 0), 2) AS "Lot Est. Value",
        """
        value_join = "LEFT JOIN v_lot_value_details v ON v.lot_id = l.id"
    else:
        value_columns = """
            NULL AS "Melt Unit Value",
            NULL AS "Chosen Unit Value", 
            NULL AS "Lot Est. Value",
        """
        value_join = ""
    
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
            {value_columns}
            COALESCE(l.estimated_grade_text, l.purchase_grade_text, '') AS Grade,
            {flip_select}
            COALESCE(l.slab_cert, '') AS "Cert #"
        FROM lot l
        JOIN tx_line tl ON tl.id = l.acquisition_line_id
        JOIN tx t ON t.id = tl.tx_id
        LEFT JOIN party p ON p.id = t.party_id
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        {value_join}
        {flip_join}
        WHERE {where_clause}
        ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety, l.id
    """
    
    return execute_query_all(query, params)


# ---------------------------------
# Helper Functions
# ---------------------------------
def format_year_columns_for_display(df):
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


def format_money_columns(df, money_columns, keep_precision_columns=None):
    """Return display and CSV versions. Display formats money, CSV keeps numeric."""
    if df is None or df.empty:
        return df, df
    
    display_df = df.copy()
    keep_precision = set(keep_precision_columns or [])
    
    for col in money_columns:
        if col in display_df.columns and col not in keep_precision:
            display_df[col] = pd.to_numeric(display_df[col], errors="coerce").fillna(0.0).map(
                lambda x: f"${x:,.2f}"
            )
    
    return display_df, df


def create_download_button(label, df, filename):
    """Create a CSV download button."""
    st.download_button(
        label,
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
    )


# ---------------------------------
# UI: Filters and Content
# ---------------------------------
countries = get_countries_on_hand()
if not countries:
    st.info("You currently have no on-hand world coins (country field empty).")
    st.stop()

col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
country = col1.selectbox("Country", options=countries, index=0, key="wc_country")
want_proofs = col2.checkbox("Proofs only", value=False, key="wc_proofs")
want_slabbed = col3.checkbox("Slabbed only", value=False, key="wc_slabbed")

# Optional asset category filter
has_asset_category = check_asset_category_support()
if has_asset_category:
    asset_category = col4.selectbox("Asset", options=["All", "COIN", "ROUND", "BAR"], index=0, key="wc_asset")
else:
    asset_category = "All"

tab_summary, tab_detail = st.tabs(["Summary", "Detail"])

# ===== Summary Tab =====
with tab_summary:
    rows = get_world_coins_summary(country, want_proofs, want_slabbed, asset_category)
    df = pd.DataFrame(rows)
    
    if df.empty:
        st.info("No on-hand inventory matched those filters.")
    else:
        money_columns = ["Melt Value (USD)", "Est. Value (USD)"]
        display_df, csv_df = format_money_columns(df, money_columns)
        st.dataframe(display_df, width='stretch', hide_index=True)
        
        filename = f"world_summary_{country}.csv".replace(" ", "_")
        create_download_button(f"Download CSV (Summary — {country})", csv_df, filename)



# ===== Detail Tab =====
with tab_detail:
    rows = get_world_coins_detail(country, want_proofs, want_slabbed, asset_category)
    df = pd.DataFrame(rows)
    
    if df.empty:
        st.info("No lots matched those filters.")
    else:
        # Format year columns
        display_df = format_year_columns_for_display(df)
        
        # Format money columns (keep 4 decimal places for Melt Unit Value)
        money_columns = ["Unit Cost (USD)", "Chosen Unit Value", "Lot Est. Value"]
        display_df, csv_df = format_money_columns(display_df, money_columns)
        
        # Special formatting for Melt Unit Value (4 decimal places)
        if "Melt Unit Value" in display_df.columns:
            display_df["Melt Unit Value"] = pd.to_numeric(display_df["Melt Unit Value"], errors="coerce").map(
                lambda x: "" if pd.isna(x) else f"{x:,.4f}"
            )
        
        st.dataframe(display_df, width='stretch', hide_index=True)
        
        filename = f"world_detail_{country}.csv".replace(" ", "_")
        create_download_button(f"Download CSV (Detail — {country})", csv_df, filename)

st.markdown(
    "For additional information on world coins including pictures and lists with KM numbers, see: "
    "[World Coins Gallery](https://worldcoingallery.com)"
)
