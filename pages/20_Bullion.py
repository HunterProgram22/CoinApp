# pages/20_Bullion.py
"""
Refactored Bullion page - Clean orchestration following SOLID principles
"""
import streamlit as st
from infrastructure.auth.auth_utils import require_auth

# Check authentication first
require_auth()

from infrastructure.database.database_executor import DatabaseExecutor
from infrastructure.database.repositories.bullion_repository import SQLBullionRepository
from presentation.components.bullion_components import BullionRenderer

# Page configuration
st.header("Bullion Overview (Bars, Rounds, Bullion Coins and Junk Silver)")

# === Dependency Injection (following our established pattern) ===
@st.cache_resource
def get_bullion_dependencies():
    """Create and cache bullion dependencies"""
    db_executor = DatabaseExecutor()
    repository = SQLBullionRepository(db_executor)
    renderer = BullionRenderer(repository)
    return renderer

# Get dependencies
renderer = get_bullion_dependencies()

# === Session State for Tab Persistence ===
if 'bullion_tab_index' not in st.session_state:
    st.session_state.bullion_tab_index = 0

# === Header Content (applies to both tabs) ===
# Show spot prices for context
renderer.render_spot_prices()

# Show bullion totals summary
renderer.render_totals_summary()

# === UI Orchestration (thin layer, just wiring up components) ===
tab_labels = ["By Category", "By Series"]

# Create tabs but track the selected one
selected_tab = st.radio(
    "Select View:",
    tab_labels,
    index=st.session_state.bullion_tab_index,
    horizontal=True,
    key="bullion_tab_selector"
)

# Update session state when tab changes
if selected_tab != tab_labels[st.session_state.bullion_tab_index]:
    st.session_state.bullion_tab_index = tab_labels.index(selected_tab)

# Render content based on selected tab
st.markdown("---")  # Visual separator

if selected_tab == "By Category":
    renderer.render_category_tab()
elif selected_tab == "By Series":
    renderer.render_series_tab()

# === Footer ===
renderer.render_footer_sections()
