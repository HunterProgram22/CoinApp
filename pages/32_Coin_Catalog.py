# pages/32_Coin_Catalog.py
"""
Refactored Coin Catalog page - Clean orchestration following SOLID principles
"""
import streamlit as st
from infrastructure.auth.auth_utils import require_auth

# Check authentication first
require_auth()

from infrastructure.database.database_executor import DatabaseExecutor
from infrastructure.database.repositories.coin_catalog_repository import CoinCatalogRepository
from presentation.components.coin_catalog_components import CoinCatalogRenderer

# Page configuration
st.title("📚 Coin Catalog")
st.caption("Browse Master Coins and Coin Types with reference links.")

# === Dependency Injection (following our established pattern) ===
@st.cache_resource
def get_coin_catalog_dependencies():
    """Create and cache coin catalog dependencies"""
    db_executor = DatabaseExecutor()
    repository = CoinCatalogRepository(db_executor)
    renderer = CoinCatalogRenderer(repository)
    return renderer

# Get dependencies
renderer = get_coin_catalog_dependencies()

# === Session State for Tab Persistence ===
if 'coin_catalog_tab_index' not in st.session_state:
    st.session_state.coin_catalog_tab_index = 0

# === UI Orchestration (thin layer, just wiring up components) ===
tab_labels = ["📖 Coin Masters", "🪙 Coin Types"]

# Create tabs but track the selected one
selected_tab = st.radio(
    "Select View:",
    tab_labels,
    index=st.session_state.coin_catalog_tab_index,
    horizontal=True,
    key="coin_catalog_tab_selector"
)

# Update session state when tab changes
if selected_tab != tab_labels[st.session_state.coin_catalog_tab_index]:
    st.session_state.coin_catalog_tab_index = tab_labels.index(selected_tab)

# Render content based on selected tab
st.markdown("---")  # Visual separator

if selected_tab == "📖 Coin Masters":
    renderer.render_masters_tab()
elif selected_tab == "🪙 Coin Types":
    renderer.render_types_tab()
