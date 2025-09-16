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

# === UI Orchestration (thin layer, just wiring up components) ===
tab_series, tab_series_detail, tab_flags = st.tabs(
    ["Series Summary", "Series Detail", "Filter by Flags"]
)

with tab_series:
    renderer.render_series_summary_tab()

with tab_series_detail:
    renderer.render_series_detail_tab()

with tab_flags:
    renderer.render_flags_tab()
