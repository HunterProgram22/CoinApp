
# pages/type_sets_functions.py
# Temporary file for testing - extracted functions from original page

import streamlit as st
import pandas as pd
from presentation.components.helpers.type_sets_helpers import (
    get_all_type_sets, create_type_set, update_type_set, delete_type_set,
    get_type_set_members, add_type_set_members, remove_type_set_members,
    get_type_set_progress, get_type_set_summary, get_type_set_upgrade_targets,
    get_type_set_metadata, save_type_set_metadata, search_coin_types,
    get_all_series, format_coin_type_label, search_coin_types_catalog
)
from core.constants import GRADE_COMPANIES, GRADE_TEXT_VALUES
from infrastructure.database.db_operations import execute_query_all

def render_my_sets_tab():
    """Render the My Sets tab"""
    type_sets = get_all_type_sets()

    if not type_sets:
        return {"status": "no_sets"}

    # Simulate selectbox behavior
    set_options = {s['name']: s for s in type_sets}
    sorted_names = sorted(set_options.keys())

    # For testing, assume first set is selected
    if sorted_names:
        selected_set = set_options[sorted_names[0]]
        set_id = selected_set['id']

        # Get progress and summary data
        progress_df = get_type_set_progress(set_id)
        summary = get_type_set_summary(set_id)
        metadata = get_type_set_metadata(set_id) if 'get_type_set_metadata' in dir() else {}

        return {
            "status": "success",
            "selected_set": selected_set,
            "progress_df": progress_df,
            "summary": summary,
            "metadata": metadata
        }

    return {"status": "no_selection"}

def render_set_summary_tab():
    """Render the Set Summary tab"""
    type_sets = get_all_type_sets()

    if not type_sets:
        return {"status": "no_sets"}

    summary_data = []
    for type_set in type_sets:
        set_id = type_set['id']
        summary = get_type_set_summary(set_id)

        # Get value data
        value_query = """
            SELECT 
                COALESCE(SUM(l.qty_remaining * v.chosen_unit_value), 0) as total_est_value,
                COALESCE(SUM(l.qty_remaining * l.unit_cost), 0) as total_cost
            FROM type_set_member tsm
            JOIN lot l ON l.coin_type_id = tsm.coin_type_id AND l.qty_remaining > 0
            LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
            WHERE tsm.set_id = ?
        """
        value_result = execute_query_all(value_query, (set_id,))

        if value_result and value_result[0]:
            total_est_value = value_result[0].get('total_est_value', 0)
            total_cost = value_result[0].get('total_cost', 0)
        else:
            total_est_value = 0
            total_cost = 0

        summary_data.append({
            'Set Name': type_set['name'],
            'Total Coins': summary.get('total_coins', 0) if summary else 0,
            'Coins Owned': summary.get('coins_owned', 0) if summary else 0,
            'Percent Complete': f"{summary.get('percent_complete', 0):.1f}%" if summary else "0.0%",
            'Est. Value (USD)': f"${total_est_value:,.2f}",
            'Total Cost (USD)': f"${total_cost:,.2f}"
        })

    return {
        "status": "success",
        "summary_data": summary_data
    }

def render_define_set_tab():
    """Render the Define Set tab"""
    all_series = get_all_series()

    # Simulate form submission
    return {
        "status": "ready",
        "available_series": all_series
    }

def render_modify_set_tab():
    """Render the Modify Set tab"""
    type_sets = get_all_type_sets()

    if not type_sets:
        return {"status": "no_sets"}

    # For testing, assume first set selected
    selected_set = type_sets[0]
    work_set_id = selected_set['id']
    current_members = get_type_set_members(work_set_id)

    return {
        "status": "success",
        "selected_set": selected_set,
        "current_members": current_members
    }

def format_coin_display_label(coin_data, include_id=False):
    """Format coin data for display"""
    parts = [coin_data.get('series', '')]
    if coin_data.get('year'):
        parts.append(str(coin_data['year']))
    if coin_data.get('mint_mark'):
        parts.append(coin_data['mint_mark'])
    if coin_data.get('variety'):
        parts.append(coin_data['variety'])
    if coin_data.get('is_proof'):
        parts.append('Proof')

    label = ' '.join(filter(None, parts))

    if include_id and coin_data.get('id'):
        label = f"{label} (ID: {coin_data['id']})"

    return label

def calculate_progress_metrics(progress_df):
    """Calculate progress metrics from DataFrame"""
    if progress_df.empty:
        return {
            'total_needed': 0,
            'total_have': 0,
            'total_meeting_requirements': 0,
            'percent_complete': 0.0
        }

    total_needed = len(progress_df)
    total_have = len(progress_df[progress_df['qty_on_hand'] > 0])
    total_meeting_requirements = len(progress_df[progress_df['meets_requirements'] == 1])
    percent_complete = (total_meeting_requirements / total_needed * 100) if total_needed > 0 else 0

    return {
        'total_needed': total_needed,
        'total_have': total_have,
        'total_meeting_requirements': total_meeting_requirements,
        'percent_complete': percent_complete
    }

def filter_progress_data(progress_df, filter_type):
    """Filter progress data based on filter type"""
    if filter_type == "Have":
        return progress_df[progress_df['meets_requirements'] == 1]
    elif filter_type == "Need":
        return progress_df[progress_df['qty_on_hand'] == 0]
    elif filter_type == "Need Upgrade":
        return progress_df[(progress_df['qty_on_hand'] > 0) & (progress_df['meets_requirements'] == 0)]
    else:  # "All"
        return progress_df

def aggregate_summary_data(summary_data_list):
    """Aggregate summary data across all sets"""
    total_sets = len(summary_data_list)
    total_coins_needed = sum(s.get('total_coins', 0) for s in summary_data_list)
    total_coins_owned = sum(s.get('coins_owned', 0) for s in summary_data_list)

    return {
        'total_sets': total_sets,
        'total_coins_needed': total_coins_needed,
        'total_coins_owned': total_coins_owned
    }
