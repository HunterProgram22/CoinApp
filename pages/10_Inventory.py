# pages/10_Inventory.py
"""
Refactored Inventory page - Clean orchestration following SOLID principles
"""
import streamlit as st
from infrastructure.auth.auth_utils import require_auth

# Check authentication first
require_auth()

from infrastructure.database.database_executor import DatabaseExecutor
from infrastructure.database.repositories.inventory_repository import SQLInventoryRepository
from presentation.components.inventory_components import InventoryRenderer

# Page configuration
st.header("Inventory")

# === Dependency Injection (following our established pattern) ===
@st.cache_resource
def get_inventory_dependencies():
    """Create and cache inventory dependencies"""
    db_executor = DatabaseExecutor()
    repository = SQLInventoryRepository(db_executor)
    renderer = InventoryRenderer(repository)
    return renderer

# Get dependencies
renderer = get_inventory_dependencies()

# === Session State for Tab Persistence ===
if 'inventory_tab_index' not in st.session_state:
    st.session_state.inventory_tab_index = 0

# === UI Orchestration (thin layer, just wiring up components) ===
tab_labels = ["Series Summary", "Series Detail", "Filter by Flags"]

# Create tabs but track the selected one
selected_tab = st.radio(
    "Select View:",
    tab_labels,
    index=st.session_state.inventory_tab_index,
    horizontal=True,
    key="inventory_tab_selector"
)

# Update session state when tab changes
if selected_tab != tab_labels[st.session_state.inventory_tab_index]:
    st.session_state.inventory_tab_index = tab_labels.index(selected_tab)

# Render content based on selected tab
st.markdown("---")  # Visual separator

if selected_tab == "Series Summary":
    renderer.render_series_summary_tab()
elif selected_tab == "Series Detail":
    renderer.render_series_detail_tab()
elif selected_tab == "Filter by Flags":
    renderer.render_flags_tab()

