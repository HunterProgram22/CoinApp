# presentation/components/helpers/proof_sets_helpers.py
"""Helper functions for proof sets data formatting."""
import pandas as pd
from typing import List, Tuple, Optional


def format_money_columns(df: pd.DataFrame, columns: List[str]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Format money columns for display.

    Args:
        df: DataFrame to format
        columns: List of column names to format as money

    Returns:
        Tuple of (display_df with formatted money, csv_df with raw values)
    """
    if df is None or df.empty:
        return df, df

    display_df = df.copy()
    csv_df = df.copy()

    for col in columns:
        if col in display_df.columns:
            display_df[col] = pd.to_numeric(display_df[col], errors='coerce').apply(
                lambda x: f"${float(x):,.2f}" if pd.notna(x) and x is not None else "$0.00"
            )

    return display_df, csv_df


def format_percentage_column(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Format percentage column for display.

    Args:
        df: DataFrame to format
        column: Column name to format as percentage

    Returns:
        DataFrame with formatted percentage column
    """
    if df is None or df.empty or column not in df.columns:
        return df

    df[column] = pd.to_numeric(df[column], errors='coerce').apply(
        lambda x: f"{float(x):.1f}%" if pd.notna(x) and x is not None else ""
    )
    return df


def prepare_inventory_summary_dataframe(summary_list: List) -> pd.DataFrame:
    """Convert inventory summary data to DataFrame.

    Args:
        summary_list: List of InventorySummary dataclass instances

    Returns:
        DataFrame ready for display
    """
    if not summary_list:
        return pd.DataFrame()

    df = pd.DataFrame([{
        'country': item.country,
        'year': item.year,
        'set_type': item.set_type,
        'sets_owned': item.sets_owned,
        'sets_on_hand': item.sets_on_hand,
        'sealed_sets': item.sealed_sets,
        'total_cost': item.total_cost,
        'total_current_value': item.total_current_value,
        'avg_cost': item.avg_cost,
        'min_cost': item.min_cost,
        'max_cost': item.max_cost
    } for item in summary_list])

    return df


def prepare_inventory_details_dataframe(details_list: List) -> pd.DataFrame:
    """Convert inventory details data to DataFrame.

    Args:
        details_list: List of ProofSetInventory dataclass instances

    Returns:
        DataFrame ready for display
    """
    if not details_list:
        return pd.DataFrame()

    df = pd.DataFrame([{
        'id': item.id,
        'country': item.country,
        'year': item.year,
        'set_type': item.set_type,
        'set_name': item.set_name,
        'coin_count': item.coin_count,
        'includes_silver': item.includes_silver,
        'acquisition_date': item.acquisition_date,
        'acquisition_price': item.acquisition_price,
        'acquired_from': item.acquired_from,
        'condition': item.condition,
        'has_coa': item.has_coa,
        'has_original_box': item.has_original_box,
        'storage_location': item.storage_location,
        'current_value': item.current_value,
        'value_as_of': item.value_as_of,
        'unrealized_gain_loss': item.unrealized_gain_loss,
        'gain_loss_percent': item.gain_loss_percent,
        'sold_date': item.sold_date,
        'sold_price': item.sold_price,
        'realized_gain_loss': item.realized_gain_loss
    } for item in details_list])

    return df


def prepare_masters_dataframe(masters_list: List) -> pd.DataFrame:
    """Convert proof set masters data to DataFrame.

    Args:
        masters_list: List of ProofSetMaster dataclass instances

    Returns:
        DataFrame ready for display
    """
    if not masters_list:
        return pd.DataFrame()

    df = pd.DataFrame([{
        'id': master.id,
        'country': master.country,
        'year': master.year,
        'set_type': master.set_type,
        'set_name': master.set_name,
        'coin_count': master.coin_count,
        'includes_silver': master.includes_silver,
        'original_mint_price': master.original_mint_price
    } for master in masters_list])

    return df


def create_download_csv(df: pd.DataFrame) -> bytes:
    """Create CSV bytes for download.

    Args:
        df: DataFrame to convert to CSV

    Returns:
        CSV file as bytes
    """
    if df is None or df.empty:
        return b""

    return df.to_csv(index=False).encode('utf-8')
