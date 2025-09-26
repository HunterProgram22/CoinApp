# presentation/components/helpers/reports_helpers.py
import pandas as pd
import streamlit as st
from datetime import date, datetime, timedelta
from typing import Optional, List, Tuple, Dict, Any


def format_money_display(amount: float) -> str:
    """Format money amount for display"""
    return f"${amount:,.2f}"


def format_percentage_display(percentage: float) -> str:
    """Format percentage for display"""
    return f"{percentage:.1f}%"


def format_troy_oz_display(oz: float) -> str:
    """Format troy ounces for display"""
    return f"{oz:.4f}"


def format_money_columns(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    """Format money columns in DataFrame for display"""
    if df.empty:
        return df

    formatted_df = df.copy()
    for col in columns:
        if col in formatted_df.columns:
            formatted_df[col] = formatted_df[col].apply(lambda x: format_money_display(x))
    return formatted_df


def format_collection_summary_metrics(summary) -> Dict[str, Any]:
    """Format collection summary data for metric display"""
    return {
        'total_coins': f"{int(summary.total_coins):,}",
        'total_cost': format_money_display(summary.total_cost),
        'estimated_value': format_money_display(summary.total_estimated_value),
        'gain_loss': format_money_display(summary.unrealized_gain_loss),
        'gain_loss_percent': format_percentage_display(summary.gain_loss_percent),
        'delta_color': 'normal' if summary.unrealized_gain_loss >= 0 else 'inverse'
    }


def format_coin_display_name(coin_data: Dict[str, Any]) -> str:
    """Format coin data for display name"""
    parts = [coin_data['series'], str(coin_data['year'])]

    if coin_data.get('mint_mark'):
        parts.append(coin_data['mint_mark'])

    if coin_data.get('variety'):
        parts.append(f"• {coin_data['variety']}")

    return ' '.join(parts)


def format_category_dataframe(category_data: List[Any]) -> pd.DataFrame:
    """Format category value data for display"""
    if not category_data:
        return pd.DataFrame()

    df = pd.DataFrame([item.__dict__ for item in category_data])

    # Rename columns for proper display
    df = df.rename(columns={
        'asset_category': 'Asset Category',
        'count': 'Count',
        'cost': 'Cost',
        'melt_value': 'Melt Value',
        'estimated_value': 'Estimated Value',
        'unrealized_gl': 'Unrealized G/L'
    })

    # Format money columns
    money_cols = ['Cost', 'Melt Value', 'Estimated Value', 'Unrealized G/L']
    df = format_money_columns(df, money_cols)

    return df


def format_metal_dataframe(metal_data: List[Any]) -> pd.DataFrame:
    """Format metal value data for display"""
    if not metal_data:
        return pd.DataFrame()

    df = pd.DataFrame([item.__dict__ for item in metal_data])

    # Rename columns for proper display
    df = df.rename(columns={
        'metal': 'Metal',
        'count': 'Count',
        'troy_oz_fine': 'Troy Oz (Fine)',
        'cost': 'Cost',
        'melt_value': 'Melt Value',
        'estimated_value': 'Estimated Value',
        'unrealized_gl': 'Unrealized G/L'
    })

    # Format money columns
    money_cols = ['Cost', 'Melt Value', 'Estimated Value', 'Unrealized G/L']
    df = format_money_columns(df, money_cols)

    # Format troy ounces
    if 'Troy Oz (Fine)' in df.columns:
        df['Troy Oz (Fine)'] = df['Troy Oz (Fine)'].apply(lambda x: format_troy_oz_display(x))

    return df


def format_top_coins_dataframe(top_coins: List[Any]) -> pd.DataFrame:
    """Format top valued coins data for display"""
    if not top_coins:
        return pd.DataFrame()

    df = pd.DataFrame([coin.__dict__ for coin in top_coins])

    # Create display name
    df['Coin'] = df.apply(
        lambda r: format_coin_display_name(r.to_dict()),
        axis=1
    )

    # Select and rename columns for display
    display_df = df[['Coin', 'qty_remaining', 'grade', 'unit_cost',
                     'unit_value', 'total_value', 'unrealized_gl']].copy()

    # Rename remaining columns
    display_df = display_df.rename(columns={
        'qty_remaining': 'Qty',
        'grade': 'Grade',
        'unit_cost': 'Unit Cost',
        'unit_value': 'Unit Value',
        'total_value': 'Total Value',
        'unrealized_gl': 'Unrealized G/L'
    })

    # Format money columns
    money_cols = ['Unit Cost', 'Unit Value', 'Total Value', 'Unrealized G/L']
    display_df = format_money_columns(display_df, money_cols)

    return display_df


def format_seller_options(sellers: List[Any]) -> Dict[str, Tuple[int, str]]:
    """Format seller data for selectbox options"""
    seller_options = {}
    for seller in sellers:
        logical_count = seller.logical_transaction_count
        db_count = seller.db_transaction_count
        total_coins = seller.total_coins

        if logical_count != db_count:
            label = f"{seller.name} ({logical_count} dates, {total_coins} coins)"
        else:
            label = f"{seller.name} ({db_count} transactions, {total_coins} coins)"

        seller_options[label] = (seller.id, seller.name)

    return seller_options


def format_seller_summary_metrics(summary) -> Dict[str, Any]:
    """Format seller summary data for metric display"""
    gain_loss = summary.unrealized_gain_loss
    gain_loss_pct = summary.gain_loss_percent

    return {
        'transactions': int(summary.unique_transactions),
        'total_purchased': int(summary.total_coins_purchased),
        'still_held': int(summary.coins_still_held),
        'total_cost': format_money_display(summary.total_cost_usd),
        'unique_types': int(summary.unique_coin_types),
        'current_value': format_money_display(summary.total_current_value_usd),
        'gain_loss': format_money_display(gain_loss),
        'gain_loss_percent': format_percentage_display(gain_loss_pct),
        'delta_color': 'normal' if gain_loss >= 0 else 'inverse',
        'coins_sold': int(summary.coins_sold)
    }


def format_seller_coin_details_dataframe(details: List[Any]) -> pd.DataFrame:
    """Format seller coin details for display"""
    if not details:
        return pd.DataFrame()

    df = pd.DataFrame([detail.__dict__ for detail in details])

    # Rename columns for display
    display_df = df.rename(columns={
        'coin': 'Coin',
        'metal': 'Metal',
        'asset_category': 'Category',
        'total_purchased': 'Purchased',
        'qty_remaining': 'On Hand',
        'avg_purchase_price': 'Avg Price',
        'total_spent': 'Total Spent',
        'cost_of_remaining': 'Cost (On Hand)',
        'current_value': 'Current Value',
        'unrealized_gl': 'Unrealized G/L',
        'gl_percent': 'G/L %',
        'best_grade': 'Grade',
        'first_purchase': 'First Purchase',
        'last_purchase': 'Last Purchase'
    })

    # Format money columns
    money_cols = ['Avg Price', 'Total Spent', 'Cost (On Hand)', 'Current Value', 'Unrealized G/L']
    display_df = format_money_columns(display_df, money_cols)

    # Format percentage
    if 'G/L %' in display_df.columns:
        display_df['G/L %'] = display_df['G/L %'].apply(lambda x: format_percentage_display(x))

    return display_df


def format_seller_transactions_dataframe(transactions: List[Any],
                                         group_by_date: bool) -> pd.DataFrame:
    """Format seller transactions for display"""
    if not transactions:
        return pd.DataFrame()

    df = pd.DataFrame([tx.__dict__ for tx in transactions])

    # Modify column names based on grouping
    if group_by_date:
        rename_dict = {
            'tx_ids': 'TX IDs',
            'db_transaction_count': 'DB Entries',
            'tx_date': 'Date',
            'line_items': 'Items',
            'total_quantity': 'Qty',
            'subtotal': 'Subtotal',
            'shipping': 'Shipping',
            'tax': 'Tax',
            'fees': 'Fees',
            'total': 'Total',
            'notes': 'Notes'
        }
    else:
        rename_dict = {
            'tx_ids': 'TX#',
            'tx_date': 'Date',
            'line_items': 'Items',
            'total_quantity': 'Qty',
            'subtotal': 'Subtotal',
            'shipping': 'Shipping',
            'tax': 'Tax',
            'fees': 'Fees',
            'total': 'Total',
            'notes': 'Notes'
        }

    # Format for display
    display_df = df.rename(columns=rename_dict)

    # Remove the db_transaction_count column if not grouping
    if not group_by_date and 'DB Entries' in display_df.columns:
        display_df = display_df.drop(columns=['DB Entries'])

    # Format money columns
    money_cols = ['Subtotal', 'Shipping', 'Tax', 'Fees', 'Total']
    for col in money_cols:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(
                lambda x: format_money_display(x) if x else "$0.00")

    return display_df


# Spending Log Functions (moved from Transactions)
def calculate_spending_date_range(preset: str) -> Tuple[Optional[date], Optional[date]]:
    """Calculate date range for spending log"""
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


def format_spending_summary_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Format spending summary DataFrame for display"""
    if df.empty:
        return df

    display_df = df.copy()

    # Format money column
    if "Total_Spent_USD" in display_df.columns:
        display_df["Total_Spent_USD"] = display_df["Total_Spent_USD"].map(
            lambda x: format_money_display(x)
        )

    return display_df


def format_spending_period_display(start_date: Optional[date], end_date: Optional[date],
                                   preset: str = None) -> str:
    """Format spending period for display"""
    if preset == "All":
        return "All Time"
    elif start_date and end_date:
        return f"{start_date.strftime('%b %d, %Y')} - {end_date.strftime('%b %d, %Y')}"
    else:
        return "Selected Period"


def validate_spending_date_range(start_date: Optional[date], end_date: Optional[date]) -> Tuple[
    bool, str]:
    """Validate spending date range"""
    if start_date and end_date and start_date > end_date:
        return False, "Start date must be before end date"

    return True, ""


# Export Functions
def prepare_export_data(data_dict: Dict[str, Any]) -> pd.DataFrame:
    """Prepare data dictionary for export"""
    dataframes = []
    keys = []

    for key, data in data_dict.items():
        if data:
            if isinstance(data, pd.DataFrame):
                dataframes.append(data)
            elif isinstance(data, list):
                dataframes.append(pd.DataFrame(data))
            else:
                dataframes.append(pd.DataFrame([data]))
            keys.append(key)

    if dataframes:
        return pd.concat(
            dataframes,
            keys=keys,
            names=['Report Section', 'Row']
        )

    return pd.DataFrame()


def create_download_filename(report_type: str, timestamp: datetime, party_name: str = None) -> str:
    """Create filename for report download"""
    clean_type = report_type.lower().replace(' ', '_')
    date_str = timestamp.strftime('%Y%m%d')

    if party_name:
        clean_party = party_name.replace(' ', '_')
        return f"{clean_type}_report_{clean_party}_{date_str}.csv"
    else:
        return f"{clean_type}_report_{date_str}.csv"


def create_csv_download_data(df: pd.DataFrame) -> bytes:
    """Create CSV data for download"""
    return df.to_csv().encode('utf-8')


# Validation Functions
def validate_report_inputs(report_type: str, selected_value: Optional[str]) -> Tuple[bool, str]:
    """Validate report input parameters"""
    if report_type == "Seller Report" and not selected_value:
        return False, "Please select a seller to generate the report"

    return True, ""


def validate_top_coins_limit(limit: int) -> Tuple[bool, str]:
    """Validate top coins limit parameter"""
    if limit < 1:
        return False, "Limit must be at least 1"
    if limit > 1000:
        return False, "Limit cannot exceed 1000"

    return True, ""


# Data Conversion Functions
def convert_dataclass_to_dict(obj) -> Dict[str, Any]:
    """Convert a dataclass object to dictionary"""
    if hasattr(obj, '__dict__'):
        return obj.__dict__
    return obj


def convert_dataclass_list_to_dict_list(dataclass_list: List[Any]) -> List[Dict[str, Any]]:
    """Convert a list of dataclass objects to a list of dictionaries"""
    return [convert_dataclass_to_dict(obj) for obj in dataclass_list]


# Report Type Functions
def get_available_report_types() -> List[str]:
    """Get list of available report types"""
    return [
        "Collection Value Report",
        "Seller Report",
        "Spending Log",
        "All Coin Insurance Report",
    ]


def format_insurance_dataframe(coins: List) -> pd.DataFrame:
    """Format insurance coin details for display"""
    data = []
    for coin in coins:
        # Build coin description
        coin_desc = f"{coin.series} {coin.year}"
        if coin.mint_mark:
            coin_desc += f" {coin.mint_mark}"
        if coin.variety:
            coin_desc += f" • {coin.variety}"

        # Format grade
        grade_display = coin.grade
        if coin.is_slabbed:
            grade_display = f"🏆 {coin.grade}"  # Add icon for slabbed coins

        data.append({
            'Coin': coin_desc,
            'Metal': coin.metal,
            'Category': coin.asset_category,
            'Tx Date': coin.tx_date,
            'Seller': coin.seller,
            'Qty': coin.quantity,
            'Unit Cost': coin.unit_cost,
            'Total Cost': coin.total_cost,
            'Est. Value': coin.estimated_value,
            'G/L': coin.unrealized_gl,
            'G/L %': (coin.unrealized_gl / coin.total_cost * 100) if coin.total_cost > 0 else 0,
            'Grade': grade_display,
            'Location': coin.storage_location or 'Not specified',
            'Notes': coin.notes or ''
        })

    df = pd.DataFrame(data)

    # Format money columns
    money_cols = ['Unit Cost', 'Total Cost', 'Est. Value', 'G/L']
    for col in money_cols:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: f"${x:,.2f}")

    # Format percentage
    if 'G/L %' in df.columns:
        df['G/L %'] = df['G/L %'].apply(lambda x: f"{x:.1f}%")

    return df


def should_show_spending_metrics(total_spent: float) -> bool:
    """Determine if spending metrics should be displayed"""
    return total_spent > 0


def create_spending_info_message(total_spent: float, period_label: str) -> str:
    """Create spending info message for display"""
    return f"### Total Spent: {format_money_display(total_spent)}\n**Period:** {period_label}"
