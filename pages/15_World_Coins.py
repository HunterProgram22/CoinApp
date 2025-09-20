# ========== pages/15_World_Coins.py ==========
"""World Coins page - Minimal responsibility: Wire up components and define layout"""
import streamlit as st
from infrastructure.auth.auth_utils import require_auth

require_auth()
from infrastructure.database.database_executor import DatabaseExecutor
from infrastructure.database.repositories.world_coins_repository import SQLWorldCoinsRepository
from presentation.components.world_coins_components import WorldCoinsRenderer


st.title("🗺 World Coins")
st.caption("Browse Coins based on Country of Origin.")


# === Dependency Injection ===
@st.cache_resource
def get_world_coins_dependencies():
    """Create and cache world coins dependencies"""
    db_executor = DatabaseExecutor()
    repository = SQLWorldCoinsRepository(db_executor)
    renderer = WorldCoinsRenderer(repository)
    return renderer

renderer = get_world_coins_dependencies()
country, filters = renderer.render_filters_and_get_selection()


# === Tab Navigation ===
tabs = st.tabs([
    "📊 Summary",
    "📋 Details",
])

with tabs[0]:
    renderer.render_summary_tab(country, filters)

with tabs[1]:
    renderer.render_detail_tab(country, filters)

# === Footer ===
renderer.render_footer_link()
