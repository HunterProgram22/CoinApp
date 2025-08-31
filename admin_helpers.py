# admin_helpers.py
"""Helper functions for admin operations."""
import streamlit as st
from typing import List, Dict, Any, Optional
from db_operations import execute_query_all, execute_update
from queries import create_or_update_coin_master, create_or_update_coin_type
from constants import ASSET_CATEGORIES


# ---------------------------------
# Data Access Functions
# ---------------------------------
def get_coin_masters() -> List[Dict[str, Any]]:
    """Get all coin masters."""
    query = """
        SELECT id, country, denomination, series, metal, fineness, weight_grams,
            diameter_mm, thickness_mm, edge, 
            years_start, years_end, asset_category,
            numista_url, ngc_url, pcgs_url, notes
        FROM coin_master
        ORDER BY country, denomination, series
    """
    return execute_query_all(query)


def get_all_coin_types() -> List[Dict[str, Any]]:
    """Get all coin types with master information."""
    query = """
        SELECT ct.id, cm.country, cm.denomination, cm.series, ct.year,
               COALESCE(ct.mint_mark,'') AS mint_mark, 
               COALESCE(ct.variety,'') AS variety,
               ct.mintage, ct.is_proof, ct.master_id
        FROM coin_type ct
        JOIN coin_master cm ON cm.id = ct.master_id
        ORDER BY cm.country, cm.denomination, cm.series, ct.year, ct.mint_mark, ct.variety
    """
    return execute_query_all(query)


def update_coin_master(master_id: int, **kwargs) -> int:
    """Update a coin master record."""
    query = """
        UPDATE coin_master
        SET country=?, denomination=?, series=?, metal=?, fineness=?, 
            weight_grams=?, diameter_mm=?, thickness_mm=?, edge=?,
            years_start=?, years_end=?, asset_category=?, 
            numista_url=?, ngc_url=?, pcgs_url=?, notes=?
        WHERE id=?
    """
    params = (
        kwargs.get('country'),
        kwargs.get('denomination'),
        kwargs.get('series'),
        kwargs.get('metal'),
        kwargs.get('fineness', 0.0),
        kwargs.get('weight_grams', 0.0),
        kwargs.get('diameter_mm', 0.0),
        kwargs.get('thickness_mm', 0.0),
        kwargs.get('edge'),
        kwargs.get('years_start', 0),
        kwargs.get('years_end', 0),
        kwargs.get('asset_category', 'COIN'),
        kwargs.get('numista_url'),
        kwargs.get('ngc_url'),
        kwargs.get('pcgs_url'),
        kwargs.get('notes'),
        master_id
    )
    return execute_update(query, params)


def update_coin_type(type_id: int, **kwargs) -> int:
    """Update a coin type record."""
    query = """
        UPDATE coin_type
        SET year=?, mint_mark=?, variety=?, mintage=?, is_proof=?
        WHERE id=?
    """
    params = (
        kwargs.get('year', 0),
        normalize_text(kwargs.get('mint_mark')),
        normalize_text(kwargs.get('variety')),
        kwargs.get('mintage', 0),
        1 if kwargs.get('is_proof') else 0,
        type_id
    )
    return execute_update(query, params)


# ---------------------------------
# Helper Functions
# ---------------------------------
def normalize_text(val: Any) -> Optional[str]:
    """Clean string input, handling NaN-like values."""
    if val is None:
        return None
    s = str(val).strip()
    if s.lower() in {"nan", "none", "-", "–", ""}:
        return ""
    return s


def format_master_label(master: Dict[str, Any]) -> str:
    """Format coin master for display."""
    return f"{master['country']} • {master['denomination']} • {master['series']}"


def format_type_label(coin_type: Dict[str, Any]) -> str:
    """Format coin type for display."""
    label = f"{coin_type['country']} • {coin_type['denomination']} • {coin_type['series']} — {coin_type['year']}"
    if coin_type['mint_mark']:
        label += f" {coin_type['mint_mark']}"
    if coin_type['variety']:
        label += f" • {coin_type['variety']}"
    return label


# ---------------------------------
# Common Weight Presets
# ---------------------------------
WEIGHT_PRESETS = {
    "1 troy oz": 31.1034768,
    "1/2 troy oz": 15.5517384,
    "1/4 troy oz": 7.7758692,
    "1/10 troy oz": 3.11034768,
    "1/20 troy oz": 1.55517384,
    "5 grams": 5.0,
    "10 grams": 10.0,
    "100 grams": 100.0,
    "1 kg": 1000.0,
}


def render_weight_helper():
    """Render weight conversion helper."""
    with st.expander("Weight Conversion Helper"):
        col1, col2 = st.columns(2)
        with col1:
            preset = st.selectbox("Common weights", list(WEIGHT_PRESETS.keys()))
            st.info(f"{preset} = {WEIGHT_PRESETS[preset]} grams")
        with col2:
            troy_oz = st.number_input("Troy ounces", min_value=0.0, step=0.01, value=1.0)
            grams = troy_oz * 31.1034768
            st.info(f"{troy_oz} troy oz = {grams:.6f} grams")