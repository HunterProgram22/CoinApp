# pages/15_World_Coins.py
"""
Refactored World Coins page - Clean orchestration following SOLID principles
"""
import streamlit as st
from infrastructure.auth.auth_utils import require_auth

# Check authentication first
require_auth()

from infrastructure.database.database_executor import DatabaseExecutor
from infrastructure.database.repositories.world_coins_repository import SQLWorldCoinsRepository
from presentation.components.world_coins_components import WorldCoinsRenderer

# Page configuration
st.header("World Coins")

# === Dependency Injection (following our established pattern) ===
@st.cache_resource
def get_world_coins_dependencies():
    """Create and cache world coins dependencies"""
    db_executor = DatabaseExecutor()
    repository = SQLWorldCoinsRepository(db_executor)
    renderer = WorldCoinsRenderer(repository)
    return renderer

# Get dependencies
renderer = get_world_coins_dependencies()

# === Session State for Tab Persistence ===
if 'world_coins_tab_index' not in st.session_state:
    st.session_state.world_coins_tab_index = 0

# === Filter Controls (apply to both tabs) ===
country, filters = renderer.render_filters_and_get_selection()

# === UI Orchestration (thin layer, just wiring up components) ===
tab_labels = ["Summary", "Detail"]

# Create tabs but track the selected one
selected_tab = st.radio(
    "Select View:",
    tab_labels,
    index=st.session_state.world_coins_tab_index,
    horizontal=True,
    key="world_coins_tab_selector"
)

# Update session state when tab changes
if selected_tab != tab_labels[st.session_state.world_coins_tab_index]:
    st.session_state.world_coins_tab_index = tab_labels.index(selected_tab)

# Render content based on selected tab
st.markdown("---")  # Visual separator

if selected_tab == "Summary":
    renderer.render_summary_tab(country, filters)
elif selected_tab == "Detail":
    renderer.render_detail_tab(country, filters)

# === Footer ===
renderer.render_footer_link()
