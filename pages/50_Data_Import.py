# ========== pages/50_Data_Import.py ==========
"""Data Import page - Minimal responsibility: Wire up components and define layout"""
import streamlit as st
from infrastructure.auth.auth_utils import require_auth

require_auth()
from infrastructure.database.database_executor import DatabaseExecutor
from infrastructure.database.repositories.import_repository import ImportRepository
from presentation.components.import_components import ImportRenderer


st.title("📥 Data Import")
st.caption("Import Coin Masters, Coin Types and Transactions.")


# === Dependency Injection ===
@st.cache_resource
def get_dependencies():
    """Initialize and cache dependencies"""
    db_executor = DatabaseExecutor()
    repository = ImportRepository(db_executor)
    renderer = ImportRenderer(repository)
    return renderer

renderer = get_dependencies()


# === Tab Navigation ===
tabs = st.tabs([
    "Quick Templates",
    "Flexible Import (Column Mapper)",
    "Catalog Import (Masters & Types)",
])

with tabs[0]:
    renderer.render_quick_template_tab()
with tabs[1]:
    renderer.render_flexible_import_tab()
with tabs[2]:
    renderer.render_catalog_import_tab()

renderer.render_import_help()
