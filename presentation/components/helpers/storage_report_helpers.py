# presentation/components/helpers/storage_report_helpers.py
"""Helper functions for storage report data formatting."""
import pandas as pd
from typing import List, Tuple, Optional


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


def format_money_columns(df: pd.DataFrame, columns: List[str]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Return display and CSV versions with money formatting.

    Args:
        df: DataFrame to format
        columns: List of column names to format as money

    Returns:
        Tuple of (display_df with formatted money, csv_df with raw values)
    """
    if df is None or df.empty:
        return df, df

    display_df = df.copy()
    for col in columns:
        if col in display_df.columns:
            display_df[col] = pd.to_numeric(display_df[col], errors="coerce").fillna(0.0).map(
                lambda x: f"${x:,.2f}"
            )

    return display_df, df


def prepare_storage_dataframe(locations: List) -> pd.DataFrame:
    """Convert storage location data to DataFrame for display.

    Args:
        locations: List of StorageLocation dataclass instances

    Returns:
        DataFrame ready for display
    """
    if not locations:
        return pd.DataFrame()

    df = pd.DataFrame([{
        "Storage Location": loc.name,
        "Category": loc.category or "",
        "Description": loc.description or "",
        "Lots": loc.lot_count,
        "Coins": loc.total_coins,
        "Total Cost (USD)": loc.total_cost_usd,
        "Total Value (USD)": loc.total_value_usd
    } for loc in locations])

    return df


def prepare_inventory_dataframe(inventory: List) -> pd.DataFrame:
    """Convert inventory data to DataFrame for display.

    Args:
        inventory: List of StorageInventory dataclass instances

    Returns:
        DataFrame ready for display
    """
    if not inventory:
        return pd.DataFrame()

    df = pd.DataFrame([{
        "Series": item.series,
        "Year": item.year,
        "Mint Mark": item.mint_mark or "",
        "Variety": item.variety or "",
        "Proof": item.is_proof,
        "Qty": item.quantity,
        "Acquired": item.acquired_date,
        "From": item.acquired_from or "",
        "Unit Cost (USD)": item.unit_cost_usd,
        "Lot Cost (USD)": item.lot_cost_usd,
        "Est. Value (USD)": item.est_value_usd,
        "Grade": item.grade or "",
        "Cert #": item.cert_number or "",
        "Val. Method": item.valuation_method or "",
        "Notes": item.notes or ""
    } for item in inventory])

    return df
