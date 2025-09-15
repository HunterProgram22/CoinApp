# ========== dashboard_components.py ==========
"""Dashboard UI components - Single Responsibility: Rendering dashboard UI"""
import streamlit as st
import pandas as pd
from typing import Dict, List
from presentation.components.helpers.dashboard_helpers import (
    format_metal_prices_dataframe,
    calculate_silver_melt_values,
    calculate_series_unrealized_gl,
    prepare_series_display_dataframe,
    get_series_column_config,
    prepare_series_export_data,
    apply_gain_loss_styling
)


class DashboardRenderer:
    """Handles all dashboard rendering - Single Responsibility"""

    def __init__(self, data_repository: 'DashboardDataRepository'):
        """Inject data repository dependency"""
        self.repo = data_repository

    def render_portfolio_overview(self):
        """Render the portfolio overview section."""
        summary = self.repo.get_portfolio_summary()
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Estimated Portfolio Value (USD)",
                      f"${summary.total_estimated_value_usd:,}")

        with col2:
            st.metric("Coins on Hand", f"{summary.total_coins:,}")

        with col3:
            st.metric("Est. Sale Proceeds", f"${summary.estimated_sale_proceeds:,}")
            st.caption("90% bullion/junk, 75% numismatic")

    def render_spot_prices(self) -> Dict[str, float]:
        """Render the latest spot prices section."""
        st.subheader("Latest Spot Prices")

        prices = self.repo.get_latest_metal_prices()

        if not prices:
            st.info("No metal prices yet. Add some under Admin → Metal Prices.")
            return {}

        # Convert to DataFrame for display
        spots_data = [{'metal': p.metal, 'price_per_oz_usd': p.price_per_oz_usd}
                      for p in prices]
        df = format_metal_prices_dataframe(spots_data)

        if df is not None:
            df["Price Per Oz. (USD)"] = df["Price Per Oz. (USD)"].apply(
                lambda x: f"${x:,.2f}"
            )
            st.dataframe(
                df,
                width='stretch',
                hide_index=True,
                column_config={
                    "Metal": st.column_config.TextColumn(),
                },
            )

        return {p.metal: p.price_per_oz_usd for p in prices}

    def render_silver_melt_reference(self, spot_prices: Dict[str, float]):
        """Render the quick silver melt reference section."""
        st.subheader("Quick Silver Melt Reference")

        silver_price = spot_prices.get('Ag')

        if silver_price is None:
            st.info("No silver spot price found. Update via Admin → Metal Prices.")
            return

        df_melt = calculate_silver_melt_values(silver_price)
        st.dataframe(df_melt, width='stretch')

        # Add link to NGC melt values page
        st.markdown(
            "For additional coin melt values not listed above, see "
            "[NGC's Complete Melt Value Guide]"
            "(https://www.ngccoin.com/price-guide/coin-melt-values.aspx)"
        )

    def render_series_summary(self):
        """Render the series summary tab."""
        rollup_data = self.repo.get_series_rollup()

        if not rollup_data:
            st.info("No inventory yet.")
            return

        # Convert to DataFrame
        rows = [vars(r) for r in rollup_data]  # Convert dataclasses to dicts
        df = pd.DataFrame(rows)
        df = calculate_series_unrealized_gl(df)
        df_display = prepare_series_display_dataframe(df)

        # Display interactive dataframe
        st.dataframe(
            df_display,
            width='stretch',
            hide_index=True,
            column_config=get_series_column_config(),
        )

        # Export functionality
        df_export = prepare_series_export_data(df)
        st.download_button(
            "Download Series Summary (CSV)",
            data=df_export.to_csv(index=False).encode('utf-8'),
            file_name="series_summary.csv",
            mime="text/csv",
        )

        # Colorized static table
        with st.expander("Colorized view (static table)"):
            styled_df = apply_gain_loss_styling(df_display)
            st.table(styled_df)
