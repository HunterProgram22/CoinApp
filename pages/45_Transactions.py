# ========== pages/45_Transactions.py ==========
"""Transactions page - Minimal responsibility: Wire up components and define layout"""
import streamlit as st
from datetime import timedelta
from infrastructure.auth.auth_utils import require_auth

require_auth()
from infrastructure.database.database_executor import DatabaseExecutor
from infrastructure.database.repositories.transaction_repository import TransactionRepository
from presentation.components.transaction_components import TransactionRenderer

st.title("📊 Transactions")
st.caption("Review, Add or Edit transactions.")


# === Dependency Injection ===
def get_dependencies():
    """Initialize and cache dependencies"""
    db_executor = DatabaseExecutor()
    repository = TransactionRepository(db_executor)
    renderer = TransactionRenderer(repository)
    return renderer

renderer = get_dependencies()


# === Tab Navigation ===
tabs = st.tabs([
   "Review / Search",
   "Add Transaction",
   "Edit Transaction",
])

with tabs[0]:
    renderer.render_search_tab()
with tabs[1]:
    renderer.render_add_transaction_tab()
with tabs[2]:
    renderer.render_edit_transaction_tab()
