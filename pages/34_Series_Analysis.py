# ========== pages/34_Series_Analysis.py ==========
"""Series Analysis page - Minimal responsibility: Wire up components and define layout"""
import streamlit as st
from infrastructure.auth.auth_utils import require_auth

require_auth()
from infrastructure.database.database_executor import DatabaseExecutor
from infrastructure.database.repositories.series_analysis_repository import \
    SQLSeriesAnalysisRepository
from presentation.components.series_analysis_components import SeriesAnalysisRenderer

st.title("📊 Series Analysis")
st.caption("Deep dive into your coin series with comprehensive analytics.")


# === Dependency Injection ===
def get_series_analysis_dependencies():
    """Create and cache series analysis dependencies"""
    db_executor = DatabaseExecutor()
    repository = SQLSeriesAnalysisRepository(db_executor)
    renderer = SeriesAnalysisRenderer(repository)
    return renderer


renderer = get_series_analysis_dependencies()

# === Series Selection ===
selected_series = renderer.render_series_selector()

if not selected_series:
    st.stop()

# === Tab Navigation ===
tabs = st.tabs([
    "📈 Overview",
    "💰 Financial",
    "🏪 Sellers & Locations",
    "🪙 Collection Details"
])

with tabs[0]:
    # Core metrics at the top
    renderer.render_core_metrics(selected_series)

    st.divider()

    # Grade distribution
    renderer.render_grade_distribution(selected_series)

with tabs[1]:
    # Financial analysis with timeline
    renderer.render_financial_analysis(selected_series)

    st.divider()

    # Show the metrics summary again for context
    metrics = renderer.repo.get_series_metrics(selected_series)
    if metrics:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Invested", f"${metrics.total_cost_usd:,.2f}")
        with col2:
            st.metric("Current Value", f"${metrics.total_est_value_usd:,.2f}")
        with col3:
            gain_loss = metrics.gain_loss_usd or 0
            gain_loss_pct = metrics.gain_loss_pct or 0
            delta_color = "normal" if gain_loss >= 0 else "inverse"
            st.metric(
                "Gain/Loss",
                f"${gain_loss:,.2f}",
                f"{gain_loss_pct:+.2f}%",
                delta_color=delta_color
            )

with tabs[2]:
    # Seller breakdown
    renderer.render_seller_breakdown(selected_series)

    st.divider()

    # Location breakdown
    renderer.render_location_breakdown(selected_series)

with tabs[3]:
    # Type breakdown (year/mint/variety)
    renderer.render_type_breakdown(selected_series)

    st.divider()

    # Notes and varieties
    renderer.render_notes_section(selected_series)

# === Footer ===
st.divider()
st.caption(f"Analysis generated for: {selected_series}")
