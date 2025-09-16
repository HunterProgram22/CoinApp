# ========== pages/20_Bullion.py ==========
"""Bullion page - Minimal responsibility: Wire up components and define layout"""
import streamlit as st
from infrastructure.auth.auth_utils import require_auth

require_auth()
from infrastructure.database.database_executor import DatabaseExecutor
from infrastructure.database.repositories.bullion_repository import SQLBullionRepository
from presentation.components.bullion_components import BullionRenderer


st.title("🧱 Bullion Overview")
st.caption("Summary of Precious Metal Bars, Rounds, Bullion Coins and Junk Silver")

# === Dependency Injection ===
@st.cache_resource
def get_bullion_dependencies():
    """Create and cache bullion dependencies"""
    db_executor = DatabaseExecutor()
    repository = SQLBullionRepository(db_executor)
    renderer = BullionRenderer(repository)
    return renderer

renderer = get_bullion_dependencies()

renderer.render_spot_prices()

renderer.render_totals_summary()

tab_category, tab_series = st.tabs(["🧿 By Category", "🗃 By Series"])

# ========================
# TAB: CATEGORY
# ========================
with tab_category:
    renderer.render_category_tab()

# ========================
# TAB: SERIES
# ========================
with tab_series:
    renderer.render_series_tab()

# === Footer ===
renderer.render_footer_sections()
