# ========== pages/10_Inventory.py ==========
"""Inventory page - Minimal responsibility: Wire up components and define layout"""
import streamlit as st
from infrastructure.auth.auth_utils import require_auth

require_auth()
from infrastructure.database.database_executor import DatabaseExecutor
from infrastructure.database.repositories.inventory_repository import SQLInventoryRepository
from presentation.components.inventory_components import InventoryRenderer


st.title("📦 Inventory")
st.caption("Review Coin Series Summaries and Details.")


# === Dependency Injection ===
@st.cache_resource
def get_inventory_dependencies():
    """Create and cache inventory dependencies"""
    db_executor = DatabaseExecutor()
    repository = SQLInventoryRepository(db_executor)
    renderer = InventoryRenderer(repository)
    return renderer

renderer = get_inventory_dependencies()


# === Tab Navigation ===
tabs = st.tabs([
    "📋 Series Summary",
    "🔎 Series Detail",
    "🚩 Filter by Flags"
])

with tabs[0]:
    renderer.render_series_summary_tab()

with tabs[1]:
    renderer.render_series_detail_tab()

with tabs[2]:
    renderer.render_flags_tab()
