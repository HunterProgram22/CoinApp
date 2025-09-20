# pages/30_Proof_Sets.py
"""Proof Sets page - Minimal responsibility: Wire up components and define layout"""
import streamlit as st
from infrastructure.auth.auth_utils import require_auth

require_auth()
from infrastructure.database.database_executor import DatabaseExecutor
from infrastructure.database.repositories.proof_sets_repository import ProofSetsRepository
from presentation.components.proof_sets_components import ProofSetsRenderer


st.title("🎁 Proof Sets & Mint Sets")
st.caption("A summary of Proof and Mint Sets not included in other summaries.")


# === Dependency Injection ===
@st.cache_resource
def get_proof_sets_dependencies():
    """Create and cache proof sets dependencies"""
    db_executor = DatabaseExecutor()
    repository = ProofSetsRepository(db_executor)
    renderer = ProofSetsRenderer(repository)
    return renderer

renderer = get_proof_sets_dependencies()


# === Tab Navigation ===
tabs = st.tabs([
    "📊 Overview",
    "➕ Add to Inventory",
    "📝 Manage Inventory",
    "🏷️ Define Set Types",
    "📈 Market Values",
])

with tabs[0]:
    renderer.render_overview_tab()

with tabs[1]:
    renderer.render_add_inventory_tab()

with tabs[2]:
    renderer.render_manage_inventory_tab()

with tabs[3]:
    renderer.render_define_sets_tab()

with tabs[4]:
    renderer.render_market_values_tab()

# === Footer ===
renderer.render_info_section()
