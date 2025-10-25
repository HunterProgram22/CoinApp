# presentation/components/series_analysis_components.py
"""Series Analysis UI components - Single Responsibility: Series analysis rendering logic"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Optional
from infrastructure.database.repositories.series_analysis_repository import (
    SeriesAnalysisDataRepository
)


class SeriesAnalysisRenderer:
    """Handles all series analysis UI rendering - Single Responsibility"""

    def __init__(self, repo: SeriesAnalysisDataRepository):
        """Inject series analysis repository dependency"""
        self.repo = repo

    def render_series_selector(self) -> Optional[str]:
        """Render country and series dropdown selectors"""
        countries = self.repo.get_all_countries()

        if not countries:
            st.info("No series found in your collection. Add some inventory first!")
            return None

        # Default to USA if available, otherwise first country
        default_country = "USA" if "USA" in countries else countries[0]

        col1, col2 = st.columns(2)

        with col1:
            selected_country = st.selectbox(
                "Select Country",
                options=countries,
                index=countries.index(default_country),
                key="series_analysis_country"
            )

        with col2:
            series_list = self.repo.get_series_by_country(selected_country)

            if not series_list:
                st.selectbox(
                    "Select Series",
                    options=["No series available"],
                    disabled=True,
                    key="series_analysis_series"
                )
                return None

            selected_series = st.selectbox(
                "Select Series",
                options=series_list,
                index=0,
                key="series_analysis_series"
            )

        return selected_series

    def render_core_metrics(self, series: str):
        """Render core metrics section"""
        metrics = self.repo.get_series_metrics(series)

        if not metrics:
            st.warning(f"No data found for series: {series}")
            return

        st.subheader(f"📊 {series} - Overview")

        # Top row - primary metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Coins", f"{metrics.total_coins:,}")
            st.caption(f"{metrics.total_lots} lots")

        with col2:
            st.metric("Total Value", f"${metrics.total_est_value_usd:,.2f}")
            melt_value = metrics.total_melt_value_usd or 0
            st.caption(f"Melt: ${melt_value:,.2f}")

        with col3:
            st.metric("Total Cost", f"${metrics.total_cost_usd:,.2f}")

        with col4:
            gain_loss = metrics.gain_loss_usd or 0
            gain_loss_pct = metrics.gain_loss_pct or 0
            delta_color = "normal" if gain_loss >= 0 else "inverse"
            st.metric(
                "Gain/Loss",
                f"${gain_loss:,.2f}",
                f"{gain_loss_pct:+.2f}%",
                delta_color=delta_color
            )

        # Second row - grades and dates
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if metrics.avg_grade:
                st.metric("Average Grade", f"{metrics.avg_grade:.1f}")
            else:
                st.metric("Average Grade", "N/A")

        with col2:
            if metrics.min_grade:
                st.metric("Lowest Grade", f"{metrics.min_grade:.1f}")
            else:
                st.metric("Lowest Grade", "N/A")

        with col3:
            if metrics.max_grade:
                st.metric("Highest Grade", f"{metrics.max_grade:.1f}")
            else:
                st.metric("Highest Grade", "N/A")

        with col4:
            if metrics.earliest_acquisition and metrics.latest_acquisition:
                date_range = f"{metrics.earliest_acquisition} to {metrics.latest_acquisition}"
                st.metric("Collection Period", "")
                st.caption(date_range)
            else:
                st.metric("Collection Period", "N/A")

    def render_grade_distribution(self, series: str):
        """Render grade distribution chart"""
        st.subheader("📈 Grade Distribution")

        grade_data = self.repo.get_grade_distribution(series)

        if not grade_data:
            st.info("No graded coins in this series.")
            return

        # Convert to DataFrame
        df = pd.DataFrame([vars(g) for g in grade_data])

        # Create bar chart
        fig = px.bar(
            df,
            x='grade_text',
            y='count',
            title=f"Grade Distribution for {series}",
            labels={'grade_text': 'Grade', 'count': 'Number of Coins'},
            text='count'
        )

        fig.update_traces(textposition='outside')
        fig.update_layout(
            showlegend=False,
            xaxis_title="Grade",
            yaxis_title="Count",
            height=400
        )

        st.plotly_chart(fig, width='stretch')

        # Also show as table
        with st.expander("View Grade Distribution Table"):
            display_df = df[['grade_text', 'count']].copy()
            display_df.columns = ['Grade', 'Count']
            st.dataframe(display_df, hide_index=True, width='stretch')

    def render_financial_analysis(self, series: str):
        """Render financial analysis section"""
        st.subheader("💰 Financial Analysis")

        # Get acquisition timeline
        timeline_data = self.repo.get_acquisition_timeline(series)

        if not timeline_data:
            st.info("No acquisition data available.")
            return

        # Convert to DataFrame
        df = pd.DataFrame([vars(t) for t in timeline_data])

        # Calculate cumulative spending
        df['cumulative_spent'] = df['total_spent'].cumsum()
        df['cumulative_coins'] = df['coins_acquired'].cumsum()

        # Create dual-axis chart
        fig = go.Figure()

        # Add cumulative spending line
        fig.add_trace(go.Scatter(
            x=df['acquisition_date'],
            y=df['cumulative_spent'],
            name='Cumulative Spending',
            mode='lines+markers',
            line=dict(color='#1f77b4', width=2),
            yaxis='y'
        ))

        # Add cumulative coins line
        fig.add_trace(go.Scatter(
            x=df['acquisition_date'],
            y=df['cumulative_coins'],
            name='Cumulative Coins',
            mode='lines+markers',
            line=dict(color='#ff7f0e', width=2),
            yaxis='y2'
        ))

        fig.update_layout(
            title=f"Acquisition Timeline for {series}",
            xaxis_title="Date",
            yaxis=dict(
                title=dict(
                    text="Cumulative Spending (USD)",
                    font=dict(color='#1f77b4')
                ),
                tickfont=dict(color='#1f77b4')
            ),
            yaxis2=dict(
                title=dict(
                    text="Cumulative Coins",
                    font=dict(color='#ff7f0e')
                ),
                tickfont=dict(color='#ff7f0e'),
                overlaying='y',
                side='right'
            ),
            hovermode='x unified',
            height=400
        )

        st.plotly_chart(fig, width='stretch')

        # Show detailed breakdown
        with st.expander("View Acquisition Details"):
            display_df = df[['acquisition_date', 'coins_acquired', 'total_spent']].copy()
            display_df.columns = ['Date', 'Coins Acquired', 'Amount Spent']
            display_df['Amount Spent'] = display_df['Amount Spent'].apply(lambda x: f"${x:,.2f}")
            st.dataframe(display_df, hide_index=True, width='stretch')

    def render_seller_breakdown(self, series: str):
        """Render seller/dealer breakdown"""
        st.subheader("🏪 Seller Breakdown")

        seller_data = self.repo.get_seller_breakdown(series)

        if not seller_data:
            st.info("No seller information available.")
            return

        # Convert to DataFrame
        df = pd.DataFrame([vars(s) for s in seller_data])

        # Create two columns
        col1, col2 = st.columns(2)

        with col1:
            # Pie chart by spending
            fig = px.pie(
                df,
                values='total_spent_usd',
                names='seller',
                title='Spending by Seller',
                hole=0.3
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, width='stretch')

        with col2:
            # Pie chart by quantity
            fig = px.pie(
                df,
                values='coins_purchased',
                names='seller',
                title='Coins by Seller',
                hole=0.3
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, width='stretch')

        # Detailed table
        st.markdown("**Detailed Breakdown**")
        display_df = df.copy()
        display_df['total_spent_usd'] = display_df['total_spent_usd'].apply(lambda x: f"${x:,.2f}")
        display_df['avg_cost_per_coin'] = display_df['avg_cost_per_coin'].apply(
            lambda x: f"${x:,.2f}")
        display_df.columns = ['Seller', 'Coins Purchased', 'Total Spent', 'Avg Cost/Coin']

        st.dataframe(display_df, hide_index=True, width='stretch')

    def render_location_breakdown(self, series: str):
        """Render storage location breakdown"""
        st.subheader("📍 Storage Locations")

        location_data = self.repo.get_location_breakdown(series)

        if not location_data:
            st.info("No location information available.")
            return

        # Convert to DataFrame
        df = pd.DataFrame([vars(loc) for loc in location_data])

        # Create horizontal bar chart
        fig = px.bar(
            df,
            y='location',
            x='coins_stored',
            orientation='h',
            title=f'Coins by Storage Location',
            labels={'location': 'Location', 'coins_stored': 'Number of Coins'},
            text='coins_stored'
        )

        fig.update_traces(textposition='outside')
        fig.update_layout(
            showlegend=False,
            height=max(300, len(df) * 40)  # Dynamic height based on number of locations
        )

        st.plotly_chart(fig, width='stretch')

        # Detailed table
        with st.expander("View Location Details"):
            display_df = df.copy()
            display_df['total_value_usd'] = display_df['total_value_usd'].apply(
                lambda x: f"${x:,.2f}")
            display_df.columns = ['Location', 'Coins Stored', 'Total Value']
            st.dataframe(display_df, hide_index=True, width='stretch')

    def render_type_breakdown(self, series: str):
        """Render breakdown by coin type (year/mint/variety)"""
        st.subheader("🪙 Collection Breakdown by Type")

        type_data = self.repo.get_type_breakdown(series)

        if not type_data:
            st.info("No type data available.")
            return

        # Convert to DataFrame
        df = pd.DataFrame([vars(t) for t in type_data])

        # Create display columns
        df['Type'] = df.apply(
            lambda
                row: f"{row['year'] or ''} {row['mint_mark'] or ''} {row['variety'] or ''}".strip(),
            axis=1
        )

        # Calculate gain/loss per type
        df['gain_loss'] = (df['total_value'].fillna(0) - df['total_cost'].fillna(0))
        df['gain_loss_pct'] = (
                    (df['gain_loss'] / df['total_cost'].replace(0, float('nan'))) * 100).round(2)

        # Display table with key metrics
        display_df = df[['Type', 'quantity', 'avg_cost', 'total_cost', 'total_value', 'gain_loss',
                         'gain_loss_pct']].copy()
        display_df.columns = ['Type', 'Qty', 'Avg Cost', 'Total Cost', 'Total Value', 'Gain/Loss',
                              'G/L %']

        # Format money columns
        for col in ['Avg Cost', 'Total Cost', 'Total Value', 'Gain/Loss']:
            display_df[col] = display_df[col].apply(
                lambda x: f"${x:,.2f}" if pd.notna(x) else "$0.00")

        display_df['G/L %'] = display_df['G/L %'].apply(
            lambda x: f"{x:+.2f}%" if pd.notna(x) else "N/A")

        st.dataframe(
            display_df,
            hide_index=True,
            width='stretch',
            height=min(600, (len(display_df) + 1) * 35 + 3)  # Dynamic height
        )

        # Download button
        csv = display_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "⬇️ Download Type Breakdown CSV",
            data=csv,
            file_name=f"{series.replace(' ', '_')}_type_breakdown.csv",
            mime="text/csv"
        )

    def render_notes_section(self, series: str):
        """Render special notes and varieties section"""
        st.subheader("📝 Notes & Varieties")

        notes_data = self.repo.get_series_notes(series)

        if not notes_data:
            st.info("No notes recorded for this series.")
            return

        # Display notes as expandable items
        for note_item in notes_data:
            type_str = f"{note_item['year'] or ''} {note_item['mint_mark'] or ''} {note_item['variety'] or ''}".strip()
            qty = note_item['quantity']

            with st.expander(f"📌 {type_str} ({qty} coin{'s' if qty != 1 else ''})"):
                st.write(note_item['notes'])

    def render_export_section(self, series: str):
        """Render export options"""
        st.divider()
        st.subheader("📥 Export Options")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("📊 Generate PDF Report", width='stretch'):
                st.info("PDF export functionality coming soon!")

        with col2:
            if st.button("📧 Email Report", width='stretch'):
                st.info("Email functionality coming soon!")
