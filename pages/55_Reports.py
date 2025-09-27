# ========== pages/55_Reports.py ==========
"""Reports page - Minimal responsibility: Wire up components and define layout"""
import streamlit as st
from infrastructure.auth.auth_utils import require_auth

require_auth()
from infrastructure.database.database_executor import DatabaseExecutor
from infrastructure.database.repositories.reports_repository import ReportsRepository
from presentation.components.reports_components import ReportsRenderer


st.title("📊 Reports")
st.caption("Generate comprehensive reports from your coin collection data")


# === Dependency Injection ===
def get_reports_dependencies():
    """Initialize dependencies for Reports page"""
    db_executor = DatabaseExecutor()
    repository = ReportsRepository(db_executor)
    renderer = ReportsRenderer(repository)
    return renderer

renderer = get_reports_dependencies()

# Report selector
selected_report = renderer.render_report_selector()

st.divider()

# Conditional rendering based on selected report type
if selected_report == "Collection Value Report":
    renderer.render_collection_value_report()
elif selected_report == "Seller Report":
    renderer.render_seller_report()
elif selected_report == "Spending Log":
    renderer.render_spending_log()
elif selected_report == "All Coin Insurance Report":
    renderer.render_insurance_report()


# Footer
renderer.render_report_footer()
