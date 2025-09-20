# pages/40_Storage_Report.py
"""Storage Report page - Minimal responsibility: Wire up components and define layout"""
import streamlit as st
from infrastructure.auth.auth_utils import require_auth

# Check authentication first
require_auth()

from infrastructure.database.database_executor import DatabaseExecutor
from infrastructure.database.repositories.storage_report_repository import StorageReportRepository
from presentation.components.storage_report_components import StorageReportRenderer

st.title("📦 Storage Location Report")
st.caption("Overview of Storage Content and Bulk Movement of Coins.")


# === Dependency Injection ===
@st.cache_resource
def get_storage_report_dependencies():
    """Create and cache storage report dependencies"""
    db_executor = DatabaseExecutor()
    repository = StorageReportRepository(db_executor)
    renderer = StorageReportRenderer(repository)
    return renderer

renderer = get_storage_report_dependencies()


# === Tab Navigation ===
tabs = st.tabs([
    "📊 Storage Summary",
    "📋 Storage Details",
    "⚙️ Manage Storage",
    "📦 Bulk Move Items",
])

with tabs[0]:
    renderer.render_summary_tab()

with tabs[1]:
    renderer.render_detail_tab()

with tabs[2]:
    renderer.render_manage_storage_tab()

with tabs[3]:
    renderer.render_bulk_move_tab()
