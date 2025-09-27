# presentation/components/helpers/coin_registry_helpers.py
"""Helper functions for coin registry data formatting."""
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple


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


def format_specimen_full_details(details: 'SpecimenFullDetails') -> Dict[
    str, List[Tuple[str, str, str]]]:
    """Format full specimen details into categorized sections for display.

    Returns a dictionary with section names as keys and lists of (label, value, format_type) tuples.
    format_type can be: 'text', 'currency', 'number', 'boolean', 'date'
    """
    if not details:
        return {}

    sections = {
        "Basic Information": [],
        "Acquisition Details": [],
        "Grading Information": [],
        "Value Analysis": [],
        "Metal Content": [],
        "Certification": [],
        "Transaction Details": [],
        "Status": [],
        "Notes": []
    }

    # Basic Information
    sections["Basic Information"].extend([
        ("Flip Code", details.code or "—", "text"),
        ("Series", details.series or "—", "text"),
        ("Year", str(details.year) if details.year else "—", "text"),
        ("Mint Mark", details.mint_mark or "—", "text"),
        ("Variety", details.variety or "—", "text"),
        ("Country", details.country or "USA", "text"),
        ("Denomination", details.denomination or "—", "text"),
        ("Lot ID", str(details.lot_id) if details.lot_id else "—", "text"),
    ])

    # Acquisition Details
    sections["Acquisition Details"].extend([
        ("Acquired From", details.acquired_from or "—", "text"),
        ("Acquisition Date", details.acquired_date or "—", "date"),
        ("Unit Cost", details.unit_cost, "currency"),
        ("Total Lot Cost", details.total_lot_cost, "currency"),
        ("Quantity in Lot", str(details.quantity_in_lot) if details.quantity_in_lot else "—",
         "text"),
    ])

    # Grading Information
    if details.purchase_grade_text or details.estimated_grade_text:
        sections["Grading Information"].extend([
            ("Purchase Grade", details.purchase_grade_text or "—", "text"),
            ("Purchase Numeric",
             str(details.purchase_numeric_grade) if details.purchase_numeric_grade else "—",
             "number"),
            ("Grading Company", details.purchase_grade_company or "—", "text"),
            ("Estimated Grade", details.estimated_grade_text or "—", "text"),
            ("Estimated Numeric",
             str(details.estimated_numeric_grade) if details.estimated_numeric_grade else "—",
             "number"),
        ])
    else:
        sections["Grading Information"].append(("Grade", "Ungraded/Raw", "text"))

    # Value Analysis
    sections["Value Analysis"].extend([
        ("Estimated Value", details.estimated_value, "currency"),
        ("Value Source", details.chosen_value_source or "—", "text"),
        ("PCGS Value", details.pcgs_value, "currency"),
        ("NGC Value", details.ngc_value, "currency"),
        ("Red Book Value", details.redbook_value, "currency"),
    ])

    # Add profit/loss calculation if both cost and value exist
    if details.unit_cost and details.estimated_value:
        profit_loss = details.estimated_value - details.unit_cost
        profit_pct = (profit_loss / details.unit_cost) * 100 if details.unit_cost > 0 else 0
        sections["Value Analysis"].extend([
            ("Profit/Loss", profit_loss, "currency_colored"),
            ("Profit %", f"{profit_pct:.1f}%", "percent_colored"),
        ])

    # Metal Content (for precious metals)
    if details.metal_type:
        sections["Metal Content"].extend([
            ("Metal Type", details.metal_type or "—", "text"),
        ])

        # Add weight/content info if available
        if details.metal_content:
            sections["Metal Content"].append(
                ("Weight", f"{details.metal_content:.2f} grams", "text")
            )

        if details.current_metal_price:
            sections["Metal Content"].append(
                ("Current Spot Price", f"${details.current_metal_price:.2f}/oz", "text")
            )

        if details.melt_value:
            sections["Metal Content"].append(
                ("Melt Value", details.melt_value, "currency")
            )

        # Add premium over melt if applicable
        if details.melt_value and details.estimated_value:
            premium = ((details.estimated_value - details.melt_value) / details.melt_value) * 100
            sections["Metal Content"].append(
                ("Premium over Melt", f"{premium:.1f}%", "percent")
            )

    # Certification
    if details.slab_cert:
        sections["Certification"].extend([
            ("Certificate #", details.slab_cert or "—", "text"),
            ("CAC Approved", "Yes ✓" if details.cac_approved else "No", "boolean"),
            ("Plus Grade", "Yes +" if details.plus_grade else "No", "boolean"),
        ])

    # Transaction Details
    if details.transaction_id:
        sections["Transaction Details"].extend([
            ("Transaction ID", str(details.transaction_id), "text"),
            ("Transaction Date", details.transaction_date or "—", "date"),
            ("Transaction Type", details.transaction_type or "—", "text"),
            ("Invoice #", details.invoice_number or "—", "text"),
        ])

    # Status
    if details.is_sold:
        sections["Status"].extend([
            ("Status", "SOLD", "text_red"),
            ("Sold To", details.sold_to or "—", "text"),
            ("Sold Date", details.sold_date or "—", "date"),
            ("Sold Price", details.sold_price, "currency"),
        ])

        # Calculate profit on sale
        if details.sold_price and details.unit_cost:
            sale_profit = details.sold_price - details.unit_cost
            sale_profit_pct = (sale_profit / details.unit_cost) * 100
            sections["Status"].extend([
                ("Sale Profit", sale_profit, "currency_colored"),
                ("Sale Profit %", f"{sale_profit_pct:.1f}%", "percent_colored"),
            ])
    else:
        sections["Status"].append(("Status", "In Collection", "text_green"))

    # Notes
    if details.notes or details.lot_notes:
        if details.notes:
            sections["Notes"].append(("Specimen Notes", details.notes, "text"))
        if details.lot_notes:
            sections["Notes"].append(("Lot Notes", details.lot_notes, "text"))

    # Remove empty sections
    sections = {k: v for k, v in sections.items() if v}

    return sections


def create_specimen_details_dataframe(
        sections: Dict[str, List[Tuple[str, str, str]]]) -> pd.DataFrame:
    """Convert sectioned specimen details into a single DataFrame for display."""
    rows = []

    for section_name, items in sections.items():
        # Add section header
        rows.append({
            'Category': f'**{section_name}**',
            'Field': '',
            'Value': ''
        })

        # Add items
        for label, value, format_type in items:
            formatted_value = format_value_for_display(value, format_type)
            rows.append({
                'Category': '',
                'Field': label,
                'Value': formatted_value
            })

    return pd.DataFrame(rows)


def format_value_for_display(value: Any, format_type: str) -> str:
    """Format a value based on its type for display."""
    if value is None or (isinstance(value, str) and value == "—"):
        return "—"

    if format_type == "currency":
        if isinstance(value, (int, float)) and value > 0:
            return f"${value:,.2f}"
        return "—"

    elif format_type == "currency_colored":
        if isinstance(value, (int, float)):
            if value > 0:
                return f"🟢 ${value:,.2f}"
            elif value < 0:
                return f"🔴 ${abs(value):,.2f}"
            else:
                return "$0.00"
        return "—"

    elif format_type == "percent_colored":
        if isinstance(value, str) and '%' in value:
            pct_val = float(value.replace('%', ''))
            if pct_val > 0:
                return f"🟢 {value}"
            elif pct_val < 0:
                return f"🔴 {value}"
            else:
                return value
        return value

    elif format_type == "number":
        if isinstance(value, (int, float)):
            return f"{value:.1f}" if value % 1 else str(int(value))
        return str(value)

    elif format_type == "boolean":
        return value  # Already formatted with Yes/No

    elif format_type == "date":
        if value and isinstance(value, str) and len(value) >= 10:
            # Format date as MM/DD/YYYY if it's in ISO format
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(value[:10])
                return dt.strftime("%m/%d/%Y")
            except:
                return value
        return value

    elif format_type == "text_red":
        return f"🔴 {value}"

    elif format_type == "text_green":
        return f"🟢 {value}"

    else:  # text or any other format
        return str(value) if value else "—"
