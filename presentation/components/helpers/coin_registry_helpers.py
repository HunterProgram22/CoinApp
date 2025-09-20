# presentation/components/helpers/coin_registry_helpers.py
"""Helper functions for coin registry data formatting."""
import pandas as pd
from typing import List, Dict, Any, Optional


def format_lot_label(lot: Dict[str, Any]) -> str:
    """Format lot for display in selectbox."""
    label = f"[Lot {lot['id']}] {lot['series']} {lot['year']}"
    if lot.get('mint_mark'):
        label += f" {lot['mint_mark']}"
    if lot.get('variety'):
        label += f" - {lot['variety']}"
    label += f" - on hand: {lot['qty_remaining']}"
    return label


def parse_codes_input(text: str) -> List[str]:
    """Parse user input for specimen codes."""
    if not text:
        return []
    # Replace commas with newlines and split
    return [x.strip() for x in text.replace(",", "\n").splitlines() if x.strip()]


def prepare_slabbed_coins_dataframe(slabbed_coins: List) -> pd.DataFrame:
    """Convert slabbed coins data to DataFrame for display.

    Args:
        slabbed_coins: List of SlabbedCoin dataclass instances

    Returns:
        DataFrame ready for display
    """
    if not slabbed_coins:
        return pd.DataFrame()

    df = pd.DataFrame([{
        'series': coin.series,
        'year': coin.year,
        'mint_mark': coin.mint_mark,
        'variety': coin.variety,
        'quantity': coin.quantity,
        'grade_company': coin.grade_company,
        'grade': coin.grade,
        'numeric_grade': coin.numeric_grade,
        'cert_number': coin.cert_number,
        'cost': coin.cost,
        'acquired_date': coin.acquired_date,
        'acquired_from': coin.acquired_from
    } for coin in slabbed_coins])

    # Format year column
    df['year'] = df['year'].apply(lambda x: str(int(x)) if pd.notna(x) else '')

    # Rename columns for display
    df = df.rename(columns={
        'series': 'Series',
        'year': 'Year',
        'mint_mark': 'Mint',
        'variety': 'Variety',
        'quantity': 'Qty',
        'grade_company': 'Company',
        'grade': 'Grade',
        'numeric_grade': 'Numeric',
        'cert_number': 'Cert #',
        'cost': 'Cost',
        'acquired_date': 'Acquired',
        'acquired_from': 'From'
    })

    return df


def prepare_grading_company_dataframe(company_data: List) -> pd.DataFrame:
    """Convert grading company data to DataFrame.

    Args:
        company_data: List of GradingCompanySummary dataclass instances

    Returns:
        DataFrame ready for display
    """
    if not company_data:
        return pd.DataFrame()

    df = pd.DataFrame([{
        'Company': summary.company,
        'Slabs': summary.slab_count,
        'Coins': summary.coin_count,
        'Avg Grade': summary.avg_grade
    } for summary in company_data])

    return df


def prepare_specimens_dataframe(specimens: List) -> pd.DataFrame:
    """Convert specimen data to DataFrame.

    Args:
        specimens: List of Specimen dataclass instances

    Returns:
        DataFrame ready for display
    """
    if not specimens:
        return pd.DataFrame()

    df = pd.DataFrame([{
        'Code': spec.code,
        'Series': spec.series,
        'Year': spec.year,
        'Mint Mark': spec.mint_mark or '',
        'Variety': spec.variety or '',
        'Lot ID': spec.lot_id,
        'Notes': spec.notes or ''
    } for spec in specimens])

    # Format year column
    if 'Year' in df.columns:
        df['Year'] = df['Year'].apply(lambda x: str(int(x)) if pd.notna(x) else '')

    return df


def prepare_enhanced_specimens_dataframe(specimens: List) -> pd.DataFrame:
    """Convert enhanced specimen data to DataFrame.

    Args:
        specimens: List of SpecimenEnhanced dataclass instances

    Returns:
        DataFrame ready for display
    """
    if not specimens:
        return pd.DataFrame()

    df = pd.DataFrame([{
        'Code': spec.code,
        'Series': spec.series,
        'Year': spec.year,
        'Mint Mark': spec.mint_mark or '',
        'Variety': spec.variety or '',
        'Lot ID': spec.lot_id,
        'Acquired Date': spec.acquired_date or '',
        'Acquired From': spec.acquired_from or '',
        'Cost (USD)': spec.unit_cost,
        'Estimated Grade': spec.grade or '',
        'Est. Value (USD)': spec.est_value
    } for spec in specimens])

    # Format year column
    if 'Year' in df.columns:
        df['Year'] = df['Year'].apply(lambda x: str(int(x)) if pd.notna(x) else '')

    # Format money columns for display
    money_columns = ['Cost (USD)', 'Est. Value (USD)']
    for col in money_columns:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: f"${x:,.2f}" if pd.notna(x) and x is not None and x > 0 else ""
            )

    return df


def format_specimen_details(specimen_dict: Dict[str, Any]) -> Dict[str, str]:
    """Format specimen details for display.

    Args:
        specimen_dict: Dictionary with specimen data

    Returns:
        Formatted dictionary for display
    """
    if not specimen_dict:
        return {}

    return {
        "Code": specimen_dict.get("code", ""),
        "Series": specimen_dict.get("series", ""),
        "Year": str(specimen_dict.get("year", "")) if specimen_dict.get("year") else "",
        "Mint Mark": specimen_dict.get("mint_mark") or "-",
        "Variety": specimen_dict.get("variety") or "-",
        "Lot ID": str(specimen_dict.get("lot_id", "")) if specimen_dict.get("lot_id") else "",
    }


def calculate_specimens_summary(specimens: List) -> Dict[str, Any]:
    """Calculate summary statistics for specimens.

    Args:
        specimens: List of SpecimenEnhanced dataclass instances

    Returns:
        Dictionary with summary statistics
    """
    if not specimens:
        return {'total_specimens': 0, 'total_value': 0.0}

    total_value = sum(
        s.est_value for s in specimens
        if hasattr(s, 'est_value') and s.est_value is not None
    )

    return {
        'total_specimens': len(specimens),
        'total_value': total_value
    }
