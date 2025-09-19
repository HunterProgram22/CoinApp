# pages/35_Type_Sets.py
import streamlit as st
from infrastructure.auth.auth_utils import require_auth
from infrastructure.database.database_executor import DatabaseExecutor
from infrastructure.database.repositories.type_sets_repository import TypeSetsRepository
from presentation.components.type_sets_components import TypeSetsRenderer

# Check authentication first
require_auth()

st.header("Type Sets")

# Dependency injection with caching
@st.cache_resource
def get_type_sets_dependencies():
    """Initialize dependencies for Type Sets page"""
    db_executor = DatabaseExecutor()
    repository = TypeSetsRepository(db_executor)
    renderer = TypeSetsRenderer(repository)
    return renderer

renderer = get_type_sets_dependencies()

# Session state for tab persistence
if 'type_sets_tab_index' not in st.session_state:
    st.session_state.type_sets_tab_index = 0

# Radio button navigation (not st.tabs for consistency)
tab_labels = ["📊 My Sets", "📋 Set Summary", "➕ Define Set", "✏️ Modify Set"]
selected_tab = st.radio(
    "Select View:",
    tab_labels,
    index=st.session_state.type_sets_tab_index,
    horizontal=True,
    key="type_sets_tab_selector"
)

# Update session state
if selected_tab != tab_labels[st.session_state.type_sets_tab_index]:
    st.session_state.type_sets_tab_index = tab_labels.index(selected_tab)

# Conditional rendering based on selected tab
if selected_tab == "📊 My Sets":
    renderer.render_my_sets_tab()
elif selected_tab == "📋 Set Summary":
    renderer.render_set_summary_tab()
elif selected_tab == "➕ Define Set":
    renderer.render_define_set_tab()
elif selected_tab == "✏️ Modify Set":
    renderer.render_modify_set_tab()
