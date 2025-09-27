# pages/25_Coin_Registry.py
"""Coin Registry page - Minimal responsibility: Wire up components and define layout"""
import streamlit as st
from infrastructure.auth.auth_utils import require_auth

# Check authentication first
require_auth()

from infrastructure.database.database_executor import DatabaseExecutor
from infrastructure.database.repositories.coin_registry_repository import CoinRegistryRepository
from presentation.components.coin_registry_components import CoinRegistryRenderer


st.title("🏷️ Coin Registry")
st.caption("Browse coins by Slab or Flip ID.")


# === Dependency Injection ===
def get_coin_registry_dependencies():
    """Create and cache coin registry dependencies"""
    db_executor = DatabaseExecutor()
    repository = CoinRegistryRepository(db_executor)
    renderer = CoinRegistryRenderer(repository)
    return renderer

renderer = get_coin_registry_dependencies()


# === Tab Navigation ===
tabs = st.tabs([
    "🛡️ Slabbed Coins",
    "📚 Browse Specimens",
    "➕ Add Flips",
    "✏️ Edit Flip",
    "🔍 Lookup Flip"
])

with tabs[0]:
    renderer.render_slabbed_coins_tab()

with tabs[1]:
    renderer.render_browse_specimens_tab()

with tabs[2]:
    renderer.render_add_flips_tab()

with tabs[3]:
    renderer.render_edit_flip_tab()

with tabs[4]:
    renderer.render_lookup_flip_tab()
