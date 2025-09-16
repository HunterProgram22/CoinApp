# ========== pages/32_Coin_Catalog.py ==========
"""Coin Catalog page - Minimal responsibility: Wire up components and define layout"""
import streamlit as st
from infrastructure.auth.auth_utils import require_auth

require_auth()
from infrastructure.database.database_executor import DatabaseExecutor
from infrastructure.database.repositories.coin_catalog_repository import CoinCatalogRepository
from presentation.components.coin_catalog_components import CoinCatalogRenderer


st.title("📚 Coin Catalog")
st.caption("Browse Master Coins and Coin Types with reference links.")

# === Dependency Injection ===
@st.cache_resource
def get_coin_catalog_dependencies():
    """Create and cache coin catalog dependencies"""
    db_executor = DatabaseExecutor()
    repository = CoinCatalogRepository(db_executor)
    renderer = CoinCatalogRenderer(repository)
    return renderer

renderer = get_coin_catalog_dependencies()

# Create tabs
tab_masters, tab_types = st.tabs(["📖 Coin Masters", "🪙 Coin Types"])

# ========================
# TAB: COIN MASTERS
# ========================
with tab_masters:
    renderer.render_masters_tab()

# ========================
# TAB: COIN TYPES
# ========================
with tab_types:
    renderer.render_types_tab()
