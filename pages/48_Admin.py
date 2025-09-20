# ========== pages/48_Admin.py ==========
"""Admin page - Minimal responsibility: Wire up components and define layout"""
import streamlit as st
from infrastructure.auth.auth_utils import require_auth

require_auth()
from infrastructure.database.database_executor import DatabaseExecutor
from infrastructure.database.repositories.admin_repository import AdminRepository
from presentation.components.admin_components import AdminRenderer


st.set_page_config(page_title="Admin", page_icon="🛠️", layout="wide")
st.title("🛠️ Admin")


# Dependency injection with caching
@st.cache_resource
def get_dependencies():
    """Initialize and cache dependencies"""
    db_executor = DatabaseExecutor()
    repository = AdminRepository(db_executor)
    renderer = AdminRenderer(repository)
    return renderer

renderer = get_dependencies()


# === Tab Navigation ===
tabs = st.tabs([
    "📖 Coin Masters Editor",
    "💵 Coin Types Editor",
    "📈 Metal Prices",
    "🛠️ Maintenance Tools",
    "📥 Database",
])

with tabs[0]:
    renderer.render_coin_master_tab()
with tabs[1]:
    renderer.render_coin_type_tab()
with tabs[2]:
    renderer.render_metal_prices_tab()
with tabs[3]:
    renderer.render_maintenance_tab()
with tabs[4]:
    renderer.render_database_tab()
