# ========== dashboard_components.py ==========
"""Dashboard UI components - Single Responsibility: Rendering dashboard UI"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
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

    def render_enhanced_metrics(self):
        """Render enhanced portfolio metrics with visual indicators."""
        summary = self.repo.get_portfolio_summary()

        # Calculate gain/loss
        gain_loss = summary.total_estimated_value_usd - summary.total_cost_usd
        gain_loss_pct = (
                    gain_loss / summary.total_cost_usd * 100) if summary.total_cost_usd > 0 else 0

        # First row - 3 columns
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Portfolio Value",
                f"${summary.total_estimated_value_usd:,.2f}",
                delta=f"{gain_loss_pct:+.1f}%" if gain_loss_pct != 0 else None
            )

        with col2:
            st.metric(
                "Total Cost Basis",
                f"${summary.total_cost_usd:,.2f}"
            )

        with col3:
            st.metric(
                "Est. Sale Proceeds",
                f"${summary.estimated_sale_proceeds:,.2f}"
            )
            st.caption("90% bullion/junk, 70% numismatic")

        # Second row - 3 columns
        col4, col5, col6 = st.columns(3)

        with col4:
            st.metric(
                "Unrealized Gain/Loss",
                f"${gain_loss:+,.2f}",
                delta=f"{gain_loss_pct:+.1f}%"
            )

        with col5:
            st.metric(
                "Total Coins",
                f"{summary.total_coins:,}"
            )

        with col6:
            st.metric(
                "Total Lots",
                f"{summary.total_lots:,}"
            )

    def render_charts_tab(self):
        """Render the charts tab with multiple visualizations."""

        # Portfolio Composition Pie Chart
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📊 Portfolio Composition")
            composition = self.repo.get_portfolio_composition()

            if composition:
                df_comp = pd.DataFrame(composition)
                fig = px.pie(
                    df_comp,
                    values='value',
                    names='category',
                    title='Portfolio by Category',
                    color_discrete_map={
                        'Bullion': '#FFD700',
                        'Junk Silver': '#C0C0C0',
                        'Numismatic': '#B87333'
                    }
                )
                fig.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("No data available for portfolio composition")

        with col2:
            st.subheader("🏆 Metal Distribution")
            metals = self.repo.get_coins_by_metal()

            if metals:
                df_metals = pd.DataFrame(metals)
                fig = px.pie(
                    df_metals,
                    values='value',
                    names='metal',
                    title='Value by Metal Type',
                    color_discrete_map={
                        'Au': '#FFD700',
                        'Ag': '#C0C0C0',
                        'Pt': '#E5E4E2',
                        'Cu': '#B87333'
                    }
                )
                fig.update_traces(
                    textposition='inside',
                    textinfo='percent+label',
                    hovertemplate='%{label}<br>Value: $%{value:,.2f}<br>Count: %{customdata[0]} coins<extra></extra>',
                    customdata=df_metals[['count']]
                )
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("No metal data available")

        # Top Series Bar Chart
        st.subheader("💰 Top 10 Series by Value")
        top_series = self.repo.get_top_series_by_value(10)

        if top_series:
            df_series = pd.DataFrame(top_series)
            fig = px.bar(
                df_series,
                x='total_value',
                y='series',
                orientation='h',
                title='Most Valuable Series in Collection',
                labels={'total_value': 'Total Value (USD)', 'series': 'Series'},
                text='total_value',
                color='total_value',
                color_continuous_scale='Blues'
            )
            fig.update_traces(
                texttemplate='$%{text:,.0f}',
                textposition='inside',
                hovertemplate='%{y}<br>Value: $%{x:,.2f}<br>Coins: %{customdata[0]}<extra></extra>',
                customdata=df_series[['coins']]
            )
            fig.update_layout(showlegend=False, height=400)
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No series data available")

        # Value vs Cost Comparison
        st.subheader("📈 Value vs Cost Analysis")
        value_cost = self.repo.get_value_vs_cost_by_series()

        if value_cost:
            df_vc = pd.DataFrame(value_cost)

            fig = go.Figure()
            fig.add_trace(go.Bar(
                name='Cost Basis',
                x=df_vc['series'],
                y=df_vc['total_cost'],
                marker_color='lightgray'
            ))
            fig.add_trace(go.Bar(
                name='Current Value',
                x=df_vc['series'],
                y=df_vc['total_value'],
                marker_color='green'
            ))

            fig.update_layout(
                title='Cost Basis vs Current Value by Series',
                xaxis_title='Series',
                yaxis_title='Value (USD)',
                barmode='group',
                height=400,
                xaxis={'tickangle': -45}
            )
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No value/cost data available")

        # Country Distribution for World Coins
        st.subheader("🌍 Geographic Distribution")
        countries = self.repo.get_country_distribution()

        if countries and len(countries) > 1:  # Only show if more than just USA
            df_countries = pd.DataFrame(countries)

            # Create two columns for the country data
            col1, col2 = st.columns([2, 1])

            with col1:
                # Bar chart for top countries
                fig = px.bar(
                    df_countries.head(10),
                    x='country',
                    y='value',
                    title='Top Countries by Value',
                    labels={'value': 'Total Value (USD)', 'country': 'Country'},
                    color='coins',
                    color_continuous_scale='Viridis'
                )
                fig.update_layout(height=350)
                st.plotly_chart(fig, width='stretch')

            with col2:
                # Summary metrics
                st.metric("Countries", len(df_countries))
                st.metric("Non-US Coins",
                          df_countries[df_countries['country'] != 'USA']['coins'].sum())
                non_us_value = df_countries[df_countries['country'] != 'USA']['value'].sum()
                st.metric("Non-US Value", f"${non_us_value:,.2f}")
        else:
            st.info("No country distribution data available")

        # Quick Stats Summary
        st.subheader("📊 Quick Statistics")
        col1, col2, col3 = st.columns(3)

        summary = self.repo.get_portfolio_summary()
        metals = self.repo.get_coins_by_metal()

        with col1:
            if summary.total_coins > 0:
                avg_value = summary.total_estimated_value_usd / summary.total_coins
                st.metric("Average Coin Value", f"${avg_value:.2f}")

        with col2:
            if metals:
                precious_metals = ['Au', 'Ag', 'Pt', 'Pd']
                precious_value = sum(
                    m['value'] for m in metals if m['metal'] in precious_metals)
                st.metric("Precious Metals Value", f"${precious_value:,.2f}")

        with col3:
            if summary.total_cost_usd > 0:
                roi = ((
                                   summary.total_estimated_value_usd - summary.total_cost_usd) / summary.total_cost_usd) * 100
                st.metric("Return on Investment", f"{roi:+.1f}%")
