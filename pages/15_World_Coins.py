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

# Create tabs
tab_summary, tab_details = st.tabs(["Summary", "Detail"])

# country, filters = renderer.render_filters_and_get_selection()

country, filters = renderer.render_filters_and_get_selection()
# ========================
# TAB: SUMMARY
# ========================
with tab_summary:
    renderer.render_summary_tab(country, filters)

# ========================
# TAB: DETAIL
# ========================
with tab_details:
    # country, filters = renderer.render_filters_and_get_selection()
    renderer.render_detail_tab(country, filters)
# === Session State for Tab Persistence ===
# if 'world_coins_tab_index' not in st.session_state:
#     st.session_state.world_coins_tab_index = 0

# === Filter Controls (apply to both tabs) ===

# === UI Orchestration (thin layer, just wiring up components) ===

# Create tabs but track the selected one
# selected_tab = st.radio(
#     "Select View:",
#     tab_labels,
#     index=st.session_state.world_coins_tab_index,
#     horizontal=True,
#     key="world_coins_tab_selector"
# )

# Update session state when tab changes
# if selected_tab != tab_labels[st.session_state.world_coins_tab_index]:
#     st.session_state.world_coins_tab_index = tab_labels.index(selected_tab)

# Render content based on selected tab
# st.markdown("---")  # Visual separator

# if selected_tab == "Summary":
#     renderer.render_summary_tab(country, filters)
# elif selected_tab == "Detail":
#     renderer.render_detail_tab(country, filters)

# === Footer ===
renderer.render_footer_link()
