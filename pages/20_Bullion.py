# pages/20_Bullion.py
import streamlit as st
from infrastructure.auth.auth_utils import require_auth

# Check authentication first
require_auth()
import streamlit as st
import pandas as pd
from infrastructure.database.db_operations import execute_query_all, execute_query_single

st.header("Bullion Overview (Bars, Rounds, Bullion Coins and Junk Silver)")


# ---------------------------------
# Data Access Functions
# ---------------------------------
def get_latest_spot_prices():
    """Get latest metal spot prices."""
    query = "SELECT metal, price_per_oz_usd FROM v_latest_spot ORDER BY metal"
    return execute_query_all(query)


def get_bullion_by_category():
    """Get bullion summary by category and metal using the schema view."""
    query = """
        SELECT 
            category, 
            metal, 
            units_on_hand, 
            gross_oz, 
            fine_oz, 
            melt_value_usd
        FROM v_inventory_bullion_by_category
        ORDER BY category, metal
    """
    return execute_query_all(query)


def get_bullion_by_series():
    """Get bullion summary by series using the schema view."""
    query = """
        SELECT 
            category, 
            metal, 
            series, 
            unit_troy_oz, 
            unit_fine_oz, 
            units_on_hand, 
            gross_oz, 
            fine_oz, 
            melt_value_usd
        FROM v_inventory_bullion_by_series
        ORDER BY category, metal, series
    """
    return execute_query_all(query)


def get_bullion_totals():
    """Get total bullion statistics including constitutional silver."""
    query = """
        WITH bullion_totals AS (
            SELECT 
                SUM(units_on_hand) as total_units,
                SUM(fine_oz) as total_fine_oz,
                SUM(melt_value_usd) as total_value
            FROM v_inventory_bullion_by_category
        ),
        constitutional_totals AS (
            SELECT 
                SUM(quantity) as total_units,
                SUM(total_fine_oz) as total_fine_oz,
                SUM(total_melt_value) as total_value
            FROM v_junk_silver
        )
        SELECT 
            COALESCE(b.total_units, 0) + COALESCE(c.total_units, 0) as total_units,
            COALESCE(b.total_fine_oz, 0) + COALESCE(c.total_fine_oz, 0) as total_fine_oz,
            COALESCE(b.total_value, 0) + COALESCE(c.total_value, 0) as total_value
        FROM bullion_totals b
        CROSS JOIN constitutional_totals c
    """
    return execute_query_single(query)


def get_constitutional_silver_by_category():
    """Get constitutional silver summary."""
    query = """
        SELECT 
            'Constitutional (Junk Silver)' as category,
            'Ag' as metal,
            SUM(quantity) as units_on_hand,
            SUM(total_fine_oz / 0.9) as gross_oz,  -- Approximate gross from fine for 90% silver
            SUM(total_fine_oz) as fine_oz,
            SUM(total_melt_value) as melt_value_usd
        FROM v_junk_silver
    """
    result = execute_query_single(query)
    return [result] if result and result['units_on_hand'] else []


def get_constitutional_silver_by_series():
    """Get constitutional silver by series."""
    query = """
        SELECT 
            'Constitutional (Junk Silver)' as category,
            'Ag' as metal,
            cm.series,
            ROUND((cm.weight_grams / 31.1034768), 4) as unit_troy_oz,
            ROUND((cm.weight_grams * cm.fineness) / 31.1034768, 4) as unit_fine_oz,
            SUM(l.qty_remaining) as units_on_hand,
            ROUND(SUM(l.qty_remaining * cm.weight_grams / 31.1034768), 4) as gross_oz,
            ROUND(SUM(l.qty_remaining * (cm.weight_grams * cm.fineness) / 31.1034768), 4) as fine_oz,
            ROUND(SUM(l.qty_remaining * v.melt_unit_value), 2) as melt_value_usd
        FROM lot l
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        JOIN v_lot_value_details v ON v.lot_id = l.id
        WHERE l.valuation_method = 'MELT_ONLY'
            AND l.qty_remaining > 0
            AND cm.metal = 'Ag'
            AND cm.asset_category = 'COIN'
        GROUP BY cm.series, cm.weight_grams, cm.fineness
        ORDER BY cm.series
    """
    return execute_query_all(query)


# ---------------------------------
# Helper Functions
# ---------------------------------
def safe_format_dataframe(df, format_spec):
    """Apply formatting to dataframe, handling None/NULL values."""
    if df.empty:
        return df

    # Replace None values with 0 for numeric columns before formatting
    for col in format_spec.keys():
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    try:
        return df.style.format(format_spec)
    except Exception as e:
        st.warning(f"Could not apply formatting: {e}")
        return df


def create_download_button(label, df, filename):
    """Create a CSV download button."""
    st.download_button(
        label,
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
    )


# ---------------------------------
# UI: Main Content
# ---------------------------------

# Show spot prices for context
spots = get_latest_spot_prices()
if spots:
    st.caption("Latest spot prices from your metal_price table:")
    spot_df = pd.DataFrame(spots).rename(columns={
        "metal": "Metal",
        "price_per_oz_usd": "Price per oz (USD)"
    })
    st.dataframe(spot_df, hide_index=True, width='stretch', column_config={
        "Metal": st.column_config.TextColumn(),
        "Price per oz (USD)": st.column_config.NumberColumn(format="$%.2f"),
    })
else:
    st.info("No spot prices found. Update them in Admin → Metal Prices.")

# Show bullion totals summary
totals = get_bullion_totals()
if totals and totals['total_units']:
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Units", f"{int(totals['total_units'] or 0):,}")
    col2.metric("Total Fine Oz", f"{float(totals['total_fine_oz'] or 0):,.2f}")
    col3.metric("Total Melt Value", f"${float(totals['total_value'] or 0):,.2f}")
    st.divider()

# Tabs for different views
tab_category, tab_series = st.tabs(["By Category", "By Series"])

# ===== By Category Tab =====
with tab_category:
    bullion_rows = get_bullion_by_category()
    constitutional_rows = get_constitutional_silver_by_category()

    rows = bullion_rows + constitutional_rows

    if not rows:
        st.info(
            "No bullion (ROUND/BAR/BULLION COIN) or Junk Silver (MELT_ONLY COINS) detected yet. "
            "Set 'asset_category' on your Coin Master records.")
    else:
        df = pd.DataFrame(rows)

        # Handle NULL values before renaming
        numeric_cols = ['units_on_hand', 'gross_oz', 'fine_oz', 'melt_value_usd']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        df = df.rename(columns={
            "category": "Category",
            "metal": "Metal",
            "units_on_hand": "Units",
            "gross_oz": "Gross oz",
            "fine_oz": "Fine oz",
            "melt_value_usd": "Melt Value (USD)"
        })

        # Format for display
        format_spec = {
            "Units": "{:,.0f}",
            "Gross oz": "{:.4f}",
            "Fine oz": "{:.4f}",
            "Melt Value (USD)": "${:,.2f}"
        }

        styled_df = safe_format_dataframe(df.copy(), format_spec)
        st.dataframe(styled_df, hide_index=True, width='stretch')

        create_download_button(
            "Download CSV (By Category)",
            df,
            "bullion_by_category.csv"
        )

# ===== By Series Tab =====
with tab_series:
    bullion_rows = get_bullion_by_series()
    constitutional_rows = get_constitutional_silver_by_series()

    rows = bullion_rows + constitutional_rows

    if not rows:
        st.info(
            "No bullion (ROUND/BAR/BULLION COIN) or Junk Silver (MELT ONLY COINS) detected yet. "
            "Set 'asset_category' on your Coin Master records.")
    else:
        df = pd.DataFrame(rows)

        # Handle NULL values before renaming
        numeric_cols = ['unit_troy_oz', 'unit_fine_oz', 'units_on_hand', 'gross_oz', 'fine_oz',
                        'melt_value_usd']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        df = df.rename(columns={
            "category": "Category",
            "metal": "Metal",
            "series": "Series",
            "unit_troy_oz": "Unit troy oz",
            "unit_fine_oz": "Unit fine oz",
            "units_on_hand": "Units",
            "gross_oz": "Gross oz",
            "fine_oz": "Fine oz",
            "melt_value_usd": "Melt Value (USD)"
        })

        # Format for display
        format_spec = {
            "Units": "{:,.0f}",
            "Unit troy oz": "{:.4f}",
            "Unit fine oz": "{:.4f}",
            "Gross oz": "{:.4f}",
            "Fine oz": "{:.4f}",
            "Melt Value (USD)": "${:,.2f}"
        }

        styled_df = safe_format_dataframe(df.copy(), format_spec)
        st.dataframe(styled_df, hide_index=True, width='stretch')

        create_download_button(
            "Download CSV (By Series)",
            df,
            "bullion_by_series.csv"
        )

# Footer information
st.markdown("---")
st.caption(
    "💡 **Tip:** Use your Coin Master editor to set **asset_category = ROUND, BAR, or BULLION COIN** "
    "on products like generic Buffalo rounds, APMEX bars, 10 oz bars, etc. "
    "Valuation uses your melt setup via weight × fineness × spot price."
)

# Show which asset categories are included
with st.expander("ℹ️ What counts as bullion?"):
    st.markdown("""
    This page shows items with the following asset_category values:
    - **ROUND** - Generic rounds, non-government issue
    - **BAR** - Bars of any size
    - **BULLION COIN** - Government-issued bullion coins (ASE, Maple Leaf, etc.)

    Regular **COIN** category items are not shown here - they appear in the main Inventory pages.
    """)

# Add diagnostic info
with st.expander("⚠️ Seeing $0 values?"):
    st.markdown("""
    If you're seeing $0 melt values, check that your coin_master records have:
    1. **metal** set (Ag, Au, Pt, Pd)
    2. **weight_grams** set (e.g., 31.103 for 1 troy oz)
    3. **fineness** set (e.g., 0.999 for .999 fine silver)
    4. **Metal prices** updated in Admin → Metal Prices

    You can update these in Admin → Coin Master Editor.
    """)
