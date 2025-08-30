# pages/25_Coin_Catalog.py
import streamlit as st
import pandas as pd
from typing import List, Optional, Dict, Any
from db_operations import execute_query_all

st.title("📚 Coin Catalog")
st.caption("Filter your Master Coins and jump to Numista, NGC, and PCGS references.")


# ---------------------------------
# Data Access Functions
# ---------------------------------
def get_distinct_values(column: str, filter_column: Optional[str] = None,
                        filter_value: Optional[str] = None) -> List[str]:
    """Get distinct values from coin_master table."""
    conditions = []
    params = []

    if filter_column and filter_value:
        conditions.append(f"{filter_column} = ?")
        params.append(filter_value)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT DISTINCT {column} AS value
        FROM coin_master
        {where_clause}
        ORDER BY value
    """

    results = execute_query_all(query, tuple(params))
    return [r['value'] for r in results if r['value']]  # Filter out None/NULL values


def search_coin_masters(
        country: Optional[str] = None,
        denomination: Optional[str] = None,
        series_search: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Search coin masters with filters."""
    conditions = []
    params = []

    if country and country != "All":
        conditions.append("country = ?")
        params.append(country)

    if denomination and denomination != "All":
        conditions.append("denomination = ?")
        params.append(denomination)

    if series_search and series_search.strip():
        conditions.append("LOWER(series) LIKE ?")
        params.append(f"%{series_search.strip().lower()}%")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT 
            id,
            country,
            denomination,
            series,
            years_start,
            years_end,
            metal,
            fineness,
            weight_grams,
            asset_category,
            COALESCE(numista_url, '') AS numista_url,
            COALESCE(ngc_url, '') AS ngc_url,
            COALESCE(pcgs_url, '') AS pcgs_url
        FROM coin_master
        {where_clause}
        ORDER BY country, denomination, series
    """

    return execute_query_all(query, tuple(params))


# ---------------------------------
# Helper Functions
# ---------------------------------
def format_year_range(row: Dict[str, Any]) -> str:
    """Format year range for display."""
    start = row.get("years_start")
    end = row.get("years_end")

    # Handle None/NULL values
    if pd.isna(start) and pd.isna(end):
        return ""

    # Try to convert to integers
    try:
        start_int = int(start) if not pd.isna(start) else None
    except (ValueError, TypeError):
        start_int = None

    try:
        end_int = int(end) if not pd.isna(end) else None
    except (ValueError, TypeError):
        end_int = None

    # Format based on what we have
    if start_int is None and end_int is None:
        return ""
    elif start_int is None:
        return f"–{end_int}"
    elif end_int is None:
        return f"{start_int}–"
    else:
        return f"{start_int}–{end_int}"


def prepare_display_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Prepare dataframe for display."""
    # Add formatted years column
    df["Years"] = df.apply(format_year_range, axis=1)

    # Select and order columns
    columns = [
        "country", "denomination", "series", "Years",
        "asset_category", "metal", "fineness", "weight_grams",
        "numista_url", "ngc_url", "pcgs_url"
    ]

    # Only include columns that exist in the dataframe
    present_columns = [col for col in columns if col in df.columns]
    df = df[present_columns]

    # Rename columns for display
    df = df.rename(columns={
        "country": "Country",
        "denomination": "Denomination",
        "series": "Series",
        "asset_category": "Category",
        "metal": "Metal",
        "fineness": "Fineness",
        "weight_grams": "Wt (g)",
        "numista_url": "Numista",
        "ngc_url": "NGC",
        "pcgs_url": "PCGS"
    })

    return df


def create_download_button(df: pd.DataFrame):
    """Create CSV download button."""
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download CSV",
        data=csv,
        file_name="coin_catalog.csv",
        mime="text/csv"
    )


# ---------------------------------
# UI Components
# ---------------------------------
def render_filters() -> tuple:
    """Render filter controls and return selected values."""
    col1, col2, col3 = st.columns([2, 2, 3])

    # Country filter
    countries = ["All"] + get_distinct_values("country")
    selected_country = col1.selectbox("Country", countries, index=0, key="cat_country")

    # Denomination filter (filtered by country if selected)
    if selected_country != "All":
        denominations = ["All"] + get_distinct_values("denomination", "country", selected_country)
    else:
        denominations = ["All"] + get_distinct_values("denomination")
    selected_denomination = col2.selectbox("Denomination", denominations, index=0, key="cat_denom")

    # Series search
    series_search = col3.text_input(
        "Search Series",
        placeholder="e.g., Morgan, Peace, Eagle",
        key="cat_search"
    )

    return selected_country, selected_denomination, series_search


def render_results(results: List[Dict[str, Any]]):
    """Render the results table."""
    if not results:
        st.info("No Master Coins found. Try relaxing the filters or import some masters first.")
        return

    df = pd.DataFrame(results)
    display_df = prepare_display_dataframe(df)

    # Configure column display with link columns for all three references
    column_config = {}

    # Add link columns for reference sites
    if "Numista" in display_df.columns:
        column_config["Numista"] = st.column_config.LinkColumn(
            "Numista",
            display_text="Open"
        )

    if "NGC" in display_df.columns:
        column_config["NGC"] = st.column_config.LinkColumn(
            "NGC",
            display_text="Open"
        )

    if "PCGS" in display_df.columns:
        column_config["PCGS"] = st.column_config.LinkColumn(
            "PCGS",
            display_text="Open"
        )

    # Add formatting for numeric columns
    if "Fineness" in display_df.columns:
        column_config["Fineness"] = st.column_config.NumberColumn(
            "Fineness",
            format="%.4f"
        )

    if "Wt (g)" in display_df.columns:
        column_config["Wt (g)"] = st.column_config.NumberColumn(
            "Wt (g)",
            format="%.3f"
        )

    # Display the dataframe
    st.dataframe(
        display_df,
        width='stretch',
        hide_index=True,
        column_config=column_config
    )

    # Add download button
    create_download_button(display_df)


# ---------------------------------
# Main UI
# ---------------------------------

# Render filters
selected_country, selected_denomination, series_search = render_filters()

# Execute search
results = search_coin_masters(selected_country, selected_denomination, series_search)

# Display result count
st.markdown(f"**Results:** {len(results):,} master coins")

# Render results
render_results(results)

# Add help information
with st.expander("ℹ️ About Reference Links"):
    st.markdown("""
    **Reference Links:**
    - **Numista** - Community-driven world coin catalog with detailed information
    - **NGC** - Numismatic Guaranty Company price guides and population reports
    - **PCGS** - Professional Coin Grading Service price guides and population reports

    Links will only appear if they've been added to the coin master records.
    You can add these URLs in Admin → Coin Master Editor.
    """)