# presentation/components/helpers/type_sets_helpers.py
import pandas as pd
import re
from typing import Dict, List, Optional, Any, Tuple


def get_grade_numeric_value(grade_text: str) -> float:
    """Convert grade text to numeric value for comparison."""
    if not grade_text:
        return 0.0

    # Handle numeric grades directly (MS-63, PF-70, etc.)
    match = re.match(r'[A-Z]+-?(\d+)', grade_text.upper())
    if match:
        return float(match.group(1))

    # Map text grades to numeric
    grade_map = {
        'P-1': 1, 'FR-2': 2, 'AG-3': 3, 'G-4': 4, 'G-6': 6,
        'VG-8': 8, 'VG-10': 10, 'F-12': 12, 'F-15': 15,
        'VF-20': 20, 'VF-25': 25, 'VF-30': 30, 'VF-35': 35,
        'XF-40': 40, 'XF-45': 45, 'AU-50': 50, 'AU-53': 53,
        'AU-55': 55, 'AU-58': 58, 'MS-60': 60, 'MS-61': 61,
        'MS-62': 62, 'MS-63': 63, 'MS-64': 64, 'MS-65': 65,
        'MS-66': 66, 'MS-67': 67, 'MS-68': 68, 'MS-69': 69,
        'MS-70': 70, 'PF-60': 60, 'PF-61': 61, 'PF-62': 62,
        'PF-63': 63, 'PF-64': 64, 'PF-65': 65, 'PF-66': 66,
        'PF-67': 67, 'PF-68': 68, 'PF-69': 69, 'PF-70': 70
    }

    return grade_map.get(grade_text.upper(), 0.0)


def format_coin_type_label(coin_type: Dict[str, Any], include_id: bool = False) -> str:
    """Format a coin type for display."""
    label = f"{coin_type['series']} {coin_type['year']}"
    if coin_type.get('mint_mark'):
        label += f" {coin_type['mint_mark']}"
    if coin_type.get('variety'):
        label += f" • {coin_type['variety']}"
    if coin_type.get('is_proof'):
        label += " (Proof)"
    if include_id:
        label += f" (#{coin_type.get('coin_type_id', coin_type.get('id'))})"
    return label


def format_progress_display_dataframe(progress_df: pd.DataFrame) -> pd.DataFrame:
    """Format progress DataFrame for display with icons and formatting"""
    if progress_df.empty:
        return progress_df

    display_df = progress_df.copy()

    # Add status icons
    display_df['have'] = display_df.apply(
        lambda r: '✅' if r['meets_requirements'] else (
            '🔶' if r['qty_on_hand'] > 0 else '❌'),
        axis=1
    )

    # Format proof indicator
    display_df['is_proof'] = display_df['is_proof'].apply(lambda x: '✓' if x else '')

    # Format grade information
    display_df['grade_info'] = display_df.apply(
        lambda r: f"{r['best_grade_company']}/{r['best_grade_text']}"
        if r['best_grade_company'] and r['best_grade_text'] else "",
        axis=1
    )

    return display_df


def filter_progress_data(progress_df: pd.DataFrame, filter_type: str) -> pd.DataFrame:
    """Filter progress data based on filter type"""
    if progress_df.empty:
        return progress_df

    if filter_type == "Have":
        return progress_df[progress_df['meets_requirements'] == 1]
    elif filter_type == "Need":
        return progress_df[progress_df['qty_on_hand'] == 0]
    elif filter_type == "Need Upgrade":
        return progress_df[
            (progress_df['qty_on_hand'] > 0) & (progress_df['meets_requirements'] == 0)
            ]
    else:  # "All"
        return progress_df


def prepare_progress_display_columns(progress_df: pd.DataFrame) -> pd.DataFrame:
    """Prepare and rename columns for progress display"""
    if progress_df.empty:
        return pd.DataFrame()

    display_columns = ['have', 'series', 'year', 'mint_mark', 'variety', 'is_proof',
                       'qty_on_hand', 'grade_info']

    # Select only available columns
    available_columns = [col for col in display_columns if col in progress_df.columns]
    display_df = progress_df[available_columns].copy()

    # Rename columns for display
    column_rename_map = {
        'have': 'Have',
        'series': 'Series',
        'year': 'Year',
        'mint_mark': 'Mint Mark',
        'variety': 'Variety',
        'is_proof': 'Proof',
        'qty_on_hand': 'Qty on Hand',
        'grade_info': 'Grade Info'
    }

    return display_df.rename(columns=column_rename_map)


def format_summary_display_dataframe(summary_data: List[Dict[str, Any]]) -> pd.DataFrame:
    """Format summary data for display table"""
    if not summary_data:
        return pd.DataFrame()

    return pd.DataFrame(summary_data)


def build_criteria_text(metadata: Dict[str, Any]) -> List[str]:
    """Build criteria text from metadata for display"""
    criteria_text = []

    if metadata.get('series'):
        criteria_text.append(f"**Series:** {', '.join(metadata['series'])}")

    if metadata.get('year_start') or metadata.get('year_end'):
        if metadata.get('year_start') and metadata.get('year_end'):
            criteria_text.append(f"**Years:** {metadata['year_start']}-{metadata['year_end']}")
        elif metadata.get('year_start'):
            criteria_text.append(f"**Years:** {metadata['year_start']}+")
        elif metadata.get('year_end'):
            criteria_text.append(f"**Years:** up to {metadata['year_end']}")

    if metadata.get('grade_company'):
        criteria_text.append(f"**Grading Company:** {metadata['grade_company']}")

    if metadata.get('min_grade'):
        criteria_text.append(f"**Minimum Grade:** {metadata['min_grade']}")

    if metadata.get('max_grade'):
        criteria_text.append(f"**Maximum Grade:** {metadata['max_grade']}")

    if metadata.get('require_slab'):
        criteria_text.append("**Must be slabbed**")

    if metadata.get('require_cac'):
        criteria_text.append("**Must have CAC approval**")

    if metadata.get('proof_only'):
        criteria_text.append("**Proofs only**")
    elif metadata.get('business_only'):
        criteria_text.append("**Business strikes only**")

    return criteria_text


def calculate_summary_metrics(type_sets: List[Dict[str, Any]],
                              summaries: List[Optional[Dict[str, Any]]]) -> Dict[str, int]:
    """Calculate aggregate metrics across all type sets"""
    total_sets = len(type_sets)
    total_coins_needed = sum([s.get('total_coins', 0) if s else 0 for s in summaries])
    total_coins_owned = sum([s.get('coins_owned', 0) if s else 0 for s in summaries])

    return {
        'total_sets': total_sets,
        'total_coins_needed': total_coins_needed,
        'total_coins_owned': total_coins_owned
    }


def build_year_range_from_inputs(start_year: int, end_year: int) -> Optional[Tuple[int, int]]:
    """Build year range tuple from start/end year inputs"""
    if start_year > 0 and end_year > 0 and end_year >= start_year:
        return (start_year, end_year)
    elif start_year > 0:
        return (start_year, 9999)
    elif end_year > 0:
        return (0, end_year)
    return None


def format_coin_preview_dataframe(catalog_matches: List[Dict[str, Any]]) -> pd.DataFrame:
    """Format catalog matches for preview display"""
    if not catalog_matches:
        return pd.DataFrame()

    preview_df = pd.DataFrame(catalog_matches)

    # Create display column
    preview_df['coin'] = preview_df.apply(
        lambda
            r: f"{r['series']} {r['year']} {r.get('mint_mark', '')} {r.get('variety', '')}".strip(),
        axis=1
    )

    return preview_df


def build_coin_label_options(coins: List[Dict[str, Any]], include_id: bool = False) -> Dict[
    str, int]:
    """Build options dictionary for selectbox from coin data"""
    return {
        format_coin_type_label(coin, include_id=include_id): coin.get('id',
                                                                      coin.get('coin_type_id'))
        for coin in coins
    }


def filter_available_coins(all_coins: List[Dict[str, Any]],
                           current_member_ids: set) -> List[Dict[str, Any]]:
    """Filter out coins that are already members of the set"""
    return [coin for coin in all_coins if coin['id'] not in current_member_ids]


def build_new_set_metadata(grade_company_filter: str, min_grade_filter: str,
                           max_grade_filter: str, require_slab: bool,
                           proof_filter: str, specific_varieties: bool,
                           start_year: int, end_year: int) -> Dict[str, Any]:
    """Build metadata dictionary for new set creation"""
    return {
        'grade_company': grade_company_filter if grade_company_filter != "Any" else None,
        'min_grade': min_grade_filter if min_grade_filter != "Any" else None,
        'max_grade': max_grade_filter if max_grade_filter != "Any" else None,
        'require_slab': require_slab,
        'proof_only': proof_filter == "Proofs only",
        'business_only': proof_filter == "Business strikes only",
        'include_varieties': specific_varieties,
        'year_start': start_year if start_year > 0 else None,
        'year_end': end_year if end_year > 0 else None
    }


def format_value_display(value: float) -> str:
    """Format monetary value for display"""
    return f"${value:,.2f}"


def format_percentage_display(percentage: float) -> str:
    """Format percentage for display"""
    return f"{percentage:.1f}%"


def prepare_download_filename(set_id: int, file_type: str) -> str:
    """Generate download filename for type set data"""
    if file_type == "progress":
        return f"type_set_{set_id}_progress.csv"
    elif file_type == "summary":
        return "type_set_summary.csv"
    else:
        return f"type_set_{set_id}_data.csv"


def get_status_legend_text() -> str:
    """Get the status legend text for progress display"""
    return "✅ = Meets all requirements | 🔶 = Have but doesn't meet requirements | ❌ = Don't have"


def format_metadata_for_display(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Format metadata for display purposes"""
    if not metadata:
        return {}

    formatted = metadata.copy()

    # Convert year range to tuple for helpers that expect it
    if metadata.get('year_start') or metadata.get('year_end'):
        start = metadata.get('year_start', 0)
        end = metadata.get('year_end', 9999)
        formatted['year_range'] = (start, end)

    # Format series as list if it's a single string
    if metadata.get('series') and isinstance(metadata['series'], str):
        formatted['series'] = [metadata['series']]

    return formatted


def convert_dataclass_list_to_dict_list(dataclass_list: List[Any]) -> List[Dict[str, Any]]:
    """Convert a list of dataclass objects to a list of dictionaries"""
    return [obj.__dict__ for obj in dataclass_list]


def calculate_completion_percentage(owned: int, total: int) -> float:
    """Calculate completion percentage with safe division"""
    if total == 0:
        return 0.0
    return (owned / total) * 100.0


def format_grade_display(grade_company: Optional[str], grade_text: Optional[str]) -> str:
    """Format grade information for display"""
    if grade_company and grade_text:
        return f"{grade_company}/{grade_text}"
    elif grade_text:
        return grade_text
    elif grade_company:
        return grade_company
    else:
        return ""


def sort_type_sets_alphabetically(type_sets: List[Dict[str, Any]]) -> List[str]:
    """Sort type set names alphabetically"""
    return sorted([ts['name'] for ts in type_sets])


def prepare_type_set_options(type_sets: List[Any]) -> Dict[str, Any]:
    """Prepare type sets for selectbox options"""
    if hasattr(type_sets[0], '__dict__'):
        # Handle dataclass objects
        return {ts.name: ts for ts in type_sets}
    else:
        # Handle dictionaries
        return {ts['name']: ts for ts in type_sets}


def validate_set_name(name: str) -> bool:
    """Validate type set name"""
    return bool(name and name.strip())


def validate_year_range(start_year: int, end_year: int) -> bool:
    """Validate year range inputs"""
    if start_year <= 0 and end_year <= 0:
        return True  # No range specified is valid
    if start_year > 0 and end_year > 0:
        return end_year >= start_year
    return True  # One-sided ranges are valid
