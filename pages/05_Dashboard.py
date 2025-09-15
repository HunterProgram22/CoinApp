# ========== pages/05_Dashboard.py (Refactored) ==========
"""Dashboard page - Minimal responsibility: Wire up components and define layout"""
import streamlit as st
from infrastructure.auth.auth_utils import require_auth
from infrastructure.database.repositories.dashboard_repository import SQLDashboardRepository
from presentation.components.dashboard_components import DashboardRenderer
from infrastructure.database.database_executor import DatabaseExecutor

# Check authentication first
require_auth()

st.header("Dashboard")

# Create tabs
tab_overview, tab_series = st.tabs(["📊 Overview", "📚 Series Summary"])

# Dependency injection - wire up components
db_executor = DatabaseExecutor()
data_repository = SQLDashboardRepository(db_executor)
renderer = DashboardRenderer(data_repository)

# ========================
# TAB: OVERVIEW
# ========================
with tab_overview:
    renderer.render_portfolio_overview()

    # ---- Custom cards/widgets can be added here ----

    spot_prices = renderer.render_spot_prices()
    renderer.render_silver_melt_reference(spot_prices)

# ========================
# TAB: SERIES SUMMARY
# ========================
with tab_series:
    renderer.render_series_summary()
