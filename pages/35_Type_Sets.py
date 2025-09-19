# ========== pages/35_Type_Sets.py ==========
"""Type Sets page - Minimal responsibility: Wire up components and define layout"""
import streamlit as st
from infrastructure.auth.auth_utils import require_auth

require_auth()
from infrastructure.database.database_executor import DatabaseExecutor
from infrastructure.database.repositories.type_sets_repository import SQLTypeSetsRepository
from presentation.components.type_sets_components import TypeSetsRenderer


st.title("📚 Type Sets")


# === Dependency Injection  ===
@st.cache_resource
def get_type_sets_dependencies():
    """Initialize dependencies for Type Sets page"""
    db_executor = DatabaseExecutor()
    repository = SQLTypeSetsRepository(db_executor)
    renderer = TypeSetsRenderer(repository)
    return renderer

renderer = get_type_sets_dependencies()


# === Tab Navigation ===
tabs = st.tabs([
    "📊 My Sets",
    "📋 Set Summary",
    "➕ Define Set",
    "✏️Modify Set",
])

with tabs[0]:
    renderer.render_my_sets_tab()
with tabs[1]:
    renderer.render_set_summary_tab()
with tabs[2]:
    renderer.render_define_set_tab()
with tabs[3]:
    renderer.render_modify_set_tab()
