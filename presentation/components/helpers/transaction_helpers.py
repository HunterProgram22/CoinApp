# presentation/components/helpers/transaction_helpers.py
import pandas as pd
from datetime import date, timedelta
from typing import Optional, Tuple, Dict, Any, List


def calculate_date_range(preset: str) -> Tuple[Optional[date], Optional[date]]:
    """Calculate date range based on preset selection"""
    if preset == "All":
        return None, None

    today = date.today()
    presets = {
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
        "1y": timedelta(days=365)
    }

    if preset == "YTD":
        return date(today.year, 1, 1), today
    elif preset in presets:
        return today - presets[preset], today
    else:
        return today - timedelta(days=30), today


def format_coin_type_label(ct: Dict[str, Any]) -> str:
    """Format coin type for display"""
    mint_mark = f" {ct['mint_mark']}" if ct.get('mint_mark') else ""
    variety = f" • {ct['variety']}" if ct.get('variety') else ""
    return f"{ct['series']} {ct['year']}{mint_mark}{variety}"


def format_storage_label(storage: Dict[str, Any]) -> str:
    """Format storage location for display"""
    category = f" ({storage['category']})" if storage.get('category') else ""
    return f"{storage['name']}{category}"


def format_transaction_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Format transaction dataframe for display"""
    if df.empty:
        return df

    display_df = df.copy()

    # Rename columns
    display_df = display_df.rename(columns={
        "tx_date": "Date",
        "tx_type": "Type",
        "party": "Party",
        "country": "Country",
        "denomination": "Denomination",
        "series": "Series",
        "year": "Year",
        "mint_mark": "Mint Mark",
        "variety": "Variety",
        "quantity": "Qty",
        "unit_price": "Unit Price (USD)",
        "currency": "Currency",
        "shipping": "Shipping",
        "tax": "Tax",
        "fees": "Fees",
        "tx_notes": "Notes",
    })

    # Format money columns
    money_columns = ["Unit Price (USD)", "Shipping", "Tax", "Fees"]
    for col in money_columns:
        if col in display_df.columns:
            display_df[col] = pd.to_numeric(display_df[col], errors="coerce").fillna(0.0).map(
                lambda x: f"${x:,.2f}"
            )

    # Format year column
    if "Year" in display_df.columns:
        display_df["Year"] = pd.to_numeric(display_df["Year"], errors="coerce").map(
            lambda x: "" if pd.isna(x) else f"{int(x)}"
        )

    return display_df


def safe_float(value: str, default: float = 0.0) -> float:
    """Safely convert string to float"""
    try:
        return float(value) if value else default
    except (ValueError, TypeError):
        return default


def format_float(value: float, decimals: int = 2) -> str:
    """Format float for display in text input"""
    if value is None or value == 0:
        return "0.00" if decimals == 2 else "0.0"
    return f"{value:.{decimals}f}"


def format_transaction_label(tx_header) -> str:
    """Format transaction for display in selector"""
    party = tx_header.party_name or 'No Party'
    return f"#{tx_header.id} - {tx_header.tx_date} - {tx_header.tx_type} - {party} - {tx_header.total_quantity} items"


def format_item_label(item, index: int, tx_type: str) -> str:
    """Format item label for expander header"""
    item_label = f"Item {index + 1}: {item.series} {item.year}"
    if item.mint_mark:
        item_label += f" {item.mint_mark}"
    if item.variety:
        item_label += f" • {item.variety}"
    if tx_type == 'BUY' and item.qty_remaining is not None:
        item_label += f" (Remaining: {item.qty_remaining}/{item.quantity})"
    return item_label
