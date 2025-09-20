# presentation/helpers/coin_catalog_helpers.py
"""Coin catalog helper functions - Single Responsibility: Data formatting and transformation"""
import pandas as pd
from typing import Dict, Any


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


def prepare_master_display_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Prepare coin master dataframe for display."""
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


def prepare_types_display_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Prepare coin types dataframe for display."""
    # Select and order columns
    columns = ["denomination", "series", "year", "mint_mark", "variety", "mintage", "is_proof"]

    # Only include columns that exist
    present_columns = [col for col in columns if col in df.columns]
    df = df[present_columns]

    # Rename columns for display
    df = df.rename(columns={
        "denomination": "Denomination",
        "series": "Series",
        "year": "Year",
        "mint_mark": "Mint Mark",
        "variety": "Variety",
        "mintage": "Mintage",
        "is_proof": "Proof"
    })

    # Format proof column
    if "Proof" in df.columns:
        df["Proof"] = df["Proof"].apply(lambda x: "✓" if x else "")

    # Format mintage with commas
    if "Mintage" in df.columns:
        df["Mintage"] = df["Mintage"].apply(lambda x: f"{int(x):,}" if x and x > 0 else "")

    return df
