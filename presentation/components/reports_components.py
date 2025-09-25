# presentation/components/reports_components.py
import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Optional
from infrastructure.database.repositories.reports_repository import ReportsDataRepository
from presentation.components.helpers.reports_helpers import (
    format_money_display, format_percentage_display, format_money_columns,
    format_collection_summary_metrics, format_category_dataframe, format_metal_dataframe,
    format_top_coins_dataframe, format_seller_options, format_seller_summary_metrics,
    format_seller_coin_details_dataframe, format_seller_transactions_dataframe,
    calculate_spending_date_range, format_spending_summary_dataframe,
    format_spending_period_display, validate_spending_date_range,
    prepare_export_data, create_download_filename, create_csv_download_data,
    validate_report_inputs, validate_top_coins_limit, convert_dataclass_list_to_dict_list,
    get_available_report_types, should_show_spending_metrics, create_spending_info_message
)


class ReportsRenderer:
    """UI renderer for Reports functionality"""

    def __init__(self, repository: ReportsDataRepository):
        self.repository = repository

    def render_report_selector(self) -> str:
        """Render the report type selector"""
        report_types = get_available_report_types()

        selected_report = st.selectbox(
            "Select Report Type",
            report_types,
            help="Choose the type of report to generate"
        )

        return selected_report

    def render_collection_value_report(self):
        """Render the Collection Value Report"""
        st.subheader("💰 Collection Value Report")

        # Get summary data
        summary = self.repository.get_collection_value_summary()

        if not summary or summary.total_coins == 0:
            st.info("No inventory found. Add some coins to see collection value.")
            return

        # Display summary metrics
        metrics = format_collection_summary_metrics(summary)
        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Total Coins", metrics['total_coins'])
        col2.metric("Total Cost", metrics['total_cost'])
        col3.metric("Est. Value", metrics['estimated_value'])
        col4.metric("Unrealized G/L", metrics['gain_loss'],
                    metrics['gain_loss_percent'], delta_color=metrics['delta_color'])

        # Tabs for different views
        tab1, tab2, tab3, tab4 = st.tabs(["By Category", "By Metal", "Top Valued", "Export"])

        with tab1:
            self._render_value_by_category_tab()

        with tab2:
            self._render_value_by_metal_tab()

        with tab3:
            self._render_top_valued_tab()

        with tab4:
            self._render_collection_export_tab()

    def render_seller_report(self):
        """Render the Seller Report"""
        st.subheader("🏪 Seller Report")

        sellers = self.repository.get_sellers_with_transactions()

        if not sellers:
            st.info("No sellers found. Add some BUY transactions first.")
            return

        # Create seller selector
        seller_options = format_seller_options(sellers)

        selected_label = st.selectbox(
            "Select Seller",
            [""] + list(seller_options.keys()),
            help="Choose a seller to generate report"
        )

        if not selected_label:
            return

        party_id, party_name = seller_options[selected_label]

        # Group by date toggle
        group_by_date = st.checkbox(
            "Group transactions by date",
            value=True,
            help="Group multiple transactions on the same date"
        )

        # Get and display seller summary
        summary = self.repository.get_seller_summary(party_id, group_by_date)

        if not summary:
            st.warning("No data found for this seller.")
            return

        # Display metrics
        metrics = format_seller_summary_metrics(summary)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Transactions", metrics['transactions'])
        col2.metric("Total Purchased", metrics['total_purchased'])
        col3.metric("Still Held", metrics['still_held'])
        col4.metric("Total Cost", metrics['total_cost'])

        # Additional metrics row
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Unique Coin Types", metrics['unique_types'])
        col2.metric("Current Value", metrics['current_value'])
        col3.metric("Unrealized G/L", metrics['gain_loss'],
                    metrics['gain_loss_percent'], delta_color=metrics['delta_color'])
        col4.metric("Coins Sold", metrics['coins_sold'])

        # Tabs for details
        tab1, tab2, tab3 = st.tabs(["By Coin Type", "Transactions", "Export"])

        with tab1:
            self._render_seller_coin_details_tab(party_id)

        with tab2:
            self._render_seller_transactions_tab(party_id, group_by_date)

        with tab3:
            self._render_seller_export_tab(party_id, party_name)

    def render_spending_log(self):
        """Render the Spending Log (moved from Transactions)"""
        st.subheader("💳 Spending Log")

        col0, col1, col2 = st.columns([2, 2, 2])

        # Initialize session state for dates if not present
        if 'sp_preset_prev' not in st.session_state:
            st.session_state.sp_preset_prev = None

        sp_preset = col0.selectbox(
            "Quick range",
            ["30d", "7d", "90d", "YTD", "1y", "All"],
            index=0,
            key="sp_preset"
        )

        # Calculate date range based on preset
        sp_start_calc, sp_end_calc = calculate_spending_date_range(sp_preset)

        # Check if preset changed and update session state
        if sp_preset != st.session_state.sp_preset_prev:
            st.session_state.sp_start = sp_start_calc
            st.session_state.sp_end = sp_end_calc
            st.session_state.sp_preset_prev = sp_preset

        # Initialize session state if keys don't exist
        if 'sp_start' not in st.session_state:
            st.session_state.sp_start = sp_start_calc
        if 'sp_end' not in st.session_state:
            st.session_state.sp_end = sp_end_calc

        if sp_preset != "All":
            sp_start = col1.date_input("Start", value=st.session_state.sp_start, key="sp_start")
            sp_end = col2.date_input("End", value=st.session_state.sp_end, key="sp_end")
        else:
            sp_start = col1.date_input(
                "Start",
                value=date.today() - timedelta(days=365),
                key="sp_start"
            )
            sp_end = col2.date_input("End", value=date.today(), key="sp_end")

        run_sp = st.button("Run Spending Log", type="primary", key="sp_run")

        if run_sp:
            # Validate date range
            is_valid, error_msg = validate_spending_date_range(sp_start, sp_end)
            if not is_valid:
                st.error(error_msg)
                return

            # Handle "All" preset
            if sp_preset == "All":
                sp_start, sp_end = None, None

            # Display total spending card
            total_spent = self.repository.get_spending_total(sp_start, sp_end)

            if should_show_spending_metrics(total_spent):
                period_label = format_spending_period_display(sp_start, sp_end, sp_preset)

                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    st.info(create_spending_info_message(total_spent, period_label))

                # Display spending summary table
                agg = self.repository.get_spending_summary(sp_start, sp_end)

                if agg.empty:
                    st.info("No BUY transactions in that range.")
                else:
                    # Format for display
                    display_agg = format_spending_summary_dataframe(agg)
                    st.dataframe(display_agg, width='stretch', hide_index=True)

                    # Download button
                    csv_data = create_csv_download_data(agg)
                    filename = create_download_filename("spending_log", datetime.now())
                    st.download_button(
                        "📥 Download Spending Log (CSV)",
                        data=csv_data,
                        file_name=filename,
                        mime="text/csv"
                    )
            else:
                st.info("No spending found in the selected period.")

    def _render_value_by_category_tab(self):
        """Render value by category tab"""
        st.markdown("### Value by Asset Category")
        category_data = self.repository.get_value_by_category()

        if category_data:
            df = format_category_dataframe(category_data)
            st.dataframe(df, hide_index=True, width='stretch')
        else:
            st.info("No category data available.")

    def _render_value_by_metal_tab(self):
        """Render value by metal tab"""
        st.markdown("### Value by Metal Type")
        metal_data = self.repository.get_value_by_metal()

        if metal_data:
            df = format_metal_dataframe(metal_data)
            st.dataframe(df, hide_index=True, width='stretch')
        else:
            st.info("No metal data available.")

    def _render_top_valued_tab(self):
        """Render top valued coins tab"""
        st.markdown("### Top Valued Coins")

        # Add slider for number of coins to show
        limit = st.slider("Number of coins to show", 10, 100, 20)

        # Validate limit
        is_valid, error_msg = validate_top_coins_limit(limit)
        if not is_valid:
            st.error(error_msg)
            return

        top_coins = self.repository.get_top_valued_coins(limit)

        if top_coins:
            df = format_top_coins_dataframe(top_coins)
            st.dataframe(df, hide_index=True, width='stretch')
        else:
            st.info("No coin data available.")

    def _render_collection_export_tab(self):
        """Render collection value export tab"""
        st.markdown("### Export Data")

        # Get all data for export
        summary = self.repository.get_collection_value_summary()
        category_data = self.repository.get_value_by_category()
        metal_data = self.repository.get_value_by_metal()
        top_coins = self.repository.get_top_valued_coins(100)

        all_data = {
            'summary': [summary.__dict__] if summary else [],
            'by_category': convert_dataclass_list_to_dict_list(category_data),
            'by_metal': convert_dataclass_list_to_dict_list(metal_data),
            'top_100_coins': convert_dataclass_list_to_dict_list(top_coins)
        }

        # Create export button
        export_data = prepare_export_data(all_data)

        if not export_data.empty:
            csv_data = create_csv_download_data(export_data)
            filename = create_download_filename("collection_value", datetime.now())
            st.download_button(
                "📥 Download Complete Value Report (CSV)",
                data=csv_data,
                file_name=filename,
                mime="text/csv"
            )
        else:
            st.info("No data available for export.")

    def _render_seller_coin_details_tab(self, party_id: int):
        """Render seller coin details tab"""
        st.markdown("### Purchases by Coin Type")
        detail_data = self.repository.get_seller_detail_by_coin_type(party_id)

        if detail_data:
            df = format_seller_coin_details_dataframe(detail_data)
            st.dataframe(df, hide_index=True, width='stretch')
        else:
            st.info("No coin details available for this seller.")

    def _render_seller_transactions_tab(self, party_id: int, group_by_date: bool):
        """Render seller transactions tab"""
        st.markdown("### Transaction History")

        if group_by_date:
            st.info(
                "📊 Transactions on the same date are grouped together as one logical transaction")

        transactions = self.repository.get_seller_transactions(party_id, group_by_date)

        if transactions:
            df = format_seller_transactions_dataframe(transactions, group_by_date)
            st.dataframe(df, hide_index=True, width='stretch')
        else:
            st.info("No transactions available for this seller.")

    def _render_seller_export_tab(self, party_id: int, party_name: str):
        """Render seller export tab"""
        st.markdown("### Export Data")

        # Prepare all data for export
        summary = self.repository.get_seller_summary(party_id, True)
        details = self.repository.get_seller_detail_by_coin_type(party_id)
        transactions = self.repository.get_seller_transactions(party_id, False)

        export_data_dict = {
            'Summary': [summary.__dict__] if summary else [],
            'Coin Details': convert_dataclass_list_to_dict_list(details),
            'Transactions': convert_dataclass_list_to_dict_list(transactions)
        }

        # Create combined export
        export_data = prepare_export_data(export_data_dict)

        if not export_data.empty:
            csv_data = create_csv_download_data(export_data)
            filename = create_download_filename("seller", datetime.now(), party_name)
            st.download_button(
                "📥 Download Seller Report (CSV)",
                data=csv_data,
                file_name=filename,
                mime="text/csv"
            )
        else:
            st.info("No data available for export.")

    def render_report_footer(self):
        """Render the report footer with information"""
        st.markdown("---")
        with st.expander("ℹ️ About Reports"):
            st.markdown("""
            **Available Reports:**

            - **Collection Value Report**: Overall collection valuation with breakdown by category, metal type, and top valued coins. Shows unrealized gains/losses based on current market values.

            - **Seller Report**: Detailed purchase history and performance analysis for each seller/dealer. Track what you bought, when, and how your purchases are performing.

            - **Spending Log**: Track your spending patterns over time with detailed breakdowns by date and seller. Monitor your purchasing behavior and budget compliance.

            **Tips:**
            - Reports use current market values from your metal prices and guide prices
            - Unrealized gains/losses are based on your chosen valuation method for each lot
            - Export any report to CSV for further analysis in Excel
            - Group transactions by date in the Seller Report to see logical purchase sessions
            - Use the Spending Log to track budget compliance and spending patterns
            """)
