# pages/55_Reports.py
import streamlit as st
from auth_utils import require_auth

# Check authentication first
require_auth()

import pandas as pd
from datetime import date, datetime, timedelta
import report_logic as rl

st.header("📊 Reports")
st.caption("Generate comprehensive reports from your coin collection data")

# Report selector
report_types = [
    "Collection Value Report",
    "Seller Report", 
    "Gain/Loss Report",
    "Tax Report",
    "Storage Report",
    "Type Set Progress Report",
    "Bullion Holdings Report"
]

selected_report = st.selectbox(
    "Select Report Type",
    report_types,
    help="Choose the type of report to generate"
)

st.divider()

# =============================================================================
# COLLECTION VALUE REPORT
# =============================================================================
if selected_report == "Collection Value Report":
    st.subheader("💰 Collection Value Report")
    
    # Get summary data
    summary = rl.get_collection_value_summary()
    
    if not summary or summary.get('total_coins', 0) == 0:
        st.info("No inventory found. Add some coins to see collection value.")
    else:
        # Display summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        col1.metric("Total Coins", f"{int(summary.get('total_coins', 0)):,}")
        col2.metric("Total Cost", f"${summary.get('total_cost', 0):,.2f}")
        col3.metric("Est. Value", f"${summary.get('total_estimated_value', 0):,.2f}")
        
        gain_loss = summary.get('unrealized_gain_loss', 0)
        gain_loss_pct = summary.get('gain_loss_percent', 0)
        
        if gain_loss >= 0:
            col4.metric("Unrealized G/L", f"${gain_loss:,.2f}", 
                       f"{gain_loss_pct:.1f}%", delta_color="normal")
        else:
            col4.metric("Unrealized G/L", f"${gain_loss:,.2f}", 
                       f"{gain_loss_pct:.1f}%", delta_color="inverse")
        
        # Tabs for different views
        tab1, tab2, tab3, tab4 = st.tabs(["By Category", "By Metal", "Top Valued", "Export"])
        
        with tab1:
            st.markdown("### Value by Asset Category")
            category_data = rl.get_value_by_category()
            if category_data:
                df = pd.DataFrame(category_data).copy()
                
                # Format for display
                for col in ['cost', 'melt_value', 'estimated_value', 'unrealized_gl']:
                    df[col] = df[col].apply(lambda x: f"${x:,.2f}")
                
                st.dataframe(df, hide_index=True, width='stretch')
        
        with tab2:
            st.markdown("### Value by Metal Type")
            metal_data = rl.get_value_by_metal()
            if metal_data:
                df = pd.DataFrame(metal_data).copy()
                
                # Format for display
                for col in ['cost', 'melt_value', 'estimated_value', 'unrealized_gl']:
                    df[col] = df[col].apply(lambda x: f"${x:,.2f}")
                df['troy_oz_fine'] = df['troy_oz_fine'].apply(lambda x: f"{x:.4f}")
                
                st.dataframe(df, hide_index=True, width='stretch')
        
        with tab3:
            st.markdown("### Top Valued Coins")
            
            # Add slider for number of coins to show
            limit = st.slider("Number of coins to show", 10, 100, 20)
            
            top_coins = rl.get_top_valued_coins(limit)
            if top_coins:
                df = pd.DataFrame(top_coins).copy()
                
                # Create display name
                df['coin'] = df.apply(
                    lambda r: f"{r['series']} {r['year']}" + 
                             (f" {r['mint_mark']}" if r.get('mint_mark') else "") +
                             (f" • {r['variety']}" if r.get('variety') else ""),
                    axis=1
                )
                
                # Select and format columns
                display_df = df[['coin', 'qty_remaining', 'grade', 'unit_cost', 
                                 'unit_value', 'total_value', 'unrealized_gl']].copy()
                
                for col in ['unit_cost', 'unit_value', 'total_value', 'unrealized_gl']:
                    display_df[col] = display_df[col].apply(lambda x: f"${x:,.2f}")
                
                st.dataframe(display_df, hide_index=True, width='stretch')
        
        with tab4:
            st.markdown("### Export Data")
            
            # Get all data for export
            all_data = {
                'summary': [summary],
                'by_category': rl.get_value_by_category(),
                'by_metal': rl.get_value_by_metal(),
                'top_100_coins': rl.get_top_valued_coins(100)
            }
            
            # Create export button
            export_data = pd.concat(
                [pd.DataFrame(data) for data in all_data.values() if data],
                keys=all_data.keys(),
                names=['Report Section', 'Row']
            )
            
            csv = export_data.to_csv().encode('utf-8')
            st.download_button(
                "📥 Download Complete Value Report (CSV)",
                data=csv,
                file_name=f"collection_value_report_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )

# =============================================================================
# SELLER REPORT
# =============================================================================
elif selected_report == "Seller Report":
    st.subheader("🏪 Seller Report")
    
    sellers = rl.get_sellers_with_transactions()
    
    if not sellers:
        st.info("No sellers found. Add some BUY transactions first.")
    else:
        # Create seller selector
        seller_options = {}
        for seller in sellers:
            logical_count = seller.get('logical_transaction_count', 0)
            db_count = seller.get('db_transaction_count', 0)
            total_coins = seller.get('total_coins', 0)
            
            if logical_count != db_count:
                label = f"{seller['name']} ({logical_count} dates, {total_coins} coins)"
            else:
                label = f"{seller['name']} ({db_count} transactions, {total_coins} coins)"
            
            seller_options[label] = (seller['id'], seller['name'])
        
        selected_label = st.selectbox(
            "Select Seller",
            [""] + list(seller_options.keys()),
            help="Choose a seller to generate report"
        )
        
        if selected_label and selected_label != "":
            party_id, party_name = seller_options[selected_label]
            
            # Group by date toggle
            group_by_date = st.checkbox(
                "Group transactions by date", 
                value=True,
                help="Group multiple transactions on the same date"
            )
            
            # Get summary
            summary = rl.get_seller_summary(party_id, group_by_date)
            
            if summary:
                # Display metrics
                col1, col2, col3, col4 = st.columns(4)
                
                col1.metric("Transactions", int(summary.get('unique_transactions', 0)))
                col2.metric("Total Purchased", int(summary.get('total_coins_purchased', 0)))
                col3.metric("Still Held", int(summary.get('coins_still_held', 0)))
                col4.metric("Total Cost", f"${summary.get('total_cost_usd', 0):,.2f}")
                
                # Tabs for details
                tab1, tab2 = st.tabs(["By Coin Type", "Transactions"])
                
                with tab1:
                    detail_data = rl.get_seller_detail_by_coin_type(party_id)
                    if detail_data:
                        df = pd.DataFrame(detail_data)
                        st.dataframe(df, hide_index=True, width='stretch')
                
                with tab2:
                    transactions = rl.get_seller_transactions(party_id, group_by_date)
                    if transactions:
                        df = pd.DataFrame(transactions)
                        st.dataframe(df, hide_index=True, width='stretch')

# =============================================================================
# GAIN/LOSS REPORT
# =============================================================================
elif selected_report == "Gain/Loss Report":
    st.subheader("📈 Gain/Loss Report")
    
    # Date range filter
    col1, col2 = st.columns(2)
    with col1:
        date_from = st.date_input("From Date", value=date.today() - timedelta(days=365))
    with col2:
        date_to = st.date_input("To Date", value=date.today())
    
    # Get realized gains/losses
    realized = rl.get_realized_gains_losses(
        date_from.strftime('%Y-%m-%d'),
        date_to.strftime('%Y-%m-%d')
    )
    
    # Get unrealized gains/losses
    unrealized = rl.get_unrealized_gains_losses()
    
    # Display summary
    st.markdown("### Summary")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Realized Gains/Losses")
        if realized and realized.get('total_sales', 0) > 0:
            st.metric("Total Sales", realized.get('total_sales', 0))
            st.metric("Proceeds", f"${realized.get('total_proceeds', 0):,.2f}")
            
            # Check if cost basis is available
            if 'note' in realized:
                st.warning("⚠️ Cost basis tracking not available")
                st.caption("Sales are shown but gains/losses cannot be calculated")
            else:
                st.metric("Cost Basis", f"${realized.get('total_cost_basis', 0):,.2f}")
                realized_gl = realized.get('realized_gain_loss', 0)
                if realized_gl >= 0:
                    st.metric("Realized G/L", f"${realized_gl:,.2f}", delta_color="normal")
                else:
                    st.metric("Realized G/L", f"${realized_gl:,.2f}", delta_color="inverse")
        else:
            st.info("No sales in selected period")
    
    with col2:
        st.markdown("#### Unrealized Gains/Losses")
        if unrealized and unrealized.get('coins_held', 0) > 0:
            st.metric("Coins Held", unrealized.get('coins_held', 0))
            st.metric("Cost Basis", f"${unrealized.get('total_cost_basis', 0):,.2f}")
            st.metric("Current Value", f"${unrealized.get('current_value', 0):,.2f}")
            
            unrealized_gl = unrealized.get('unrealized_gain_loss', 0)
            gl_pct = unrealized.get('gain_loss_percent', 0)
            if unrealized_gl >= 0:
                st.metric("Unrealized G/L", f"${unrealized_gl:,.2f}", 
                         f"{gl_pct:.1f}%", delta_color="normal")
            else:
                st.metric("Unrealized G/L", f"${unrealized_gl:,.2f}", 
                         f"{gl_pct:.1f}%", delta_color="inverse")
        else:
            st.info("No inventory on hand")
    
    # Monthly breakdown
    st.markdown("### Monthly Breakdown")
    monthly_data = rl.get_gain_loss_by_year()
    if monthly_data:
        df = pd.DataFrame(monthly_data)
        st.dataframe(df, hide_index=True, width='stretch')

# =============================================================================
# TAX REPORT
# =============================================================================
elif selected_report == "Tax Report":
    st.subheader("📋 Tax Report (Capital Gains)")
    
    # Year selector
    current_year = datetime.now().year
    tax_year = st.selectbox(
        "Tax Year",
        range(current_year, current_year - 10, -1),
        help="Select the tax year for capital gains reporting"
    )
    
    # Get tax year summary
    summary = rl.get_tax_year_summary(tax_year)
    
    if summary and summary.get('total_sales', 0) > 0:
        # Check if cost basis tracking is available
        if 'note' in summary:
            st.warning("⚠️ Cost basis tracking not available - lot_disposal table not found")
            st.info("Sales information is shown but capital gains cannot be calculated accurately")
        
        # Display summary metrics
        st.markdown("### Summary")
        col1, col2, col3, col4 = st.columns(4)
        
        col1.metric("Total Sales", summary.get('total_sales', 0))
        col2.metric("Total Proceeds", f"${summary.get('total_proceeds', 0):,.2f}")
        
        if 'note' not in summary:
            col3.metric("Total Cost Basis", f"${summary.get('total_cost_basis', 0):,.2f}")
            col4.metric("Net Gain/Loss", f"${summary.get('total_gain_loss', 0):,.2f}")
            
            # Short-term vs Long-term
            st.markdown("### Holding Period Breakdown")
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### Short-term (≤ 1 year)")
                st.metric("Sales", summary.get('short_term_sales', 0))
                st_gl = summary.get('short_term_gain_loss', 0)
                if st_gl >= 0:
                    st.metric("Gain/Loss", f"${st_gl:,.2f}", delta_color="normal")
                else:
                    st.metric("Gain/Loss", f"${st_gl:,.2f}", delta_color="inverse")
            
            with col2:
                st.markdown("#### Long-term (> 1 year)")
                st.metric("Sales", summary.get('long_term_sales', 0))
                lt_gl = summary.get('long_term_gain_loss', 0)
                if lt_gl >= 0:
                    st.metric("Gain/Loss", f"${lt_gl:,.2f}", delta_color="normal")
                else:
                    st.metric("Gain/Loss", f"${lt_gl:,.2f}", delta_color="inverse")
        
        # Detailed transactions
        st.markdown("### Transaction Details")
        details = rl.get_tax_year_details(tax_year)
        if details:
            df = pd.DataFrame(details)
            st.dataframe(df, hide_index=True, width='stretch')
            
            # Export for tax software
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download Tax Report (CSV)",
                data=csv,
                file_name=f"tax_report_{tax_year}.csv",
                mime="text/csv"
            )
        
        # Tax disclaimer
        st.warning("⚠️ This report is for informational purposes only. Please consult with a tax professional for actual tax filing.")
    else:
        st.info(f"No sales found for tax year {tax_year}")

# =============================================================================
# STORAGE REPORT
# =============================================================================
elif selected_report == "Storage Report":
    st.subheader("📦 Storage Report")
    
    # Get storage summary
    storage_summary = rl.get_storage_summary()
    unassigned = rl.get_unassigned_inventory_summary()
    
    # Display unassigned warning if any
    if unassigned and unassigned.get('coins', 0) > 0:
        st.warning(f"⚠️ {unassigned['coins']} coins (${unassigned['value']:,.2f} value) not assigned to any storage location")
    
    # Storage location selector
    storage_options = {"Unassigned": None}
    for storage in storage_summary:
        label = f"{storage['name']} ({storage['category']}) - {storage['coins']} coins"
        storage_options[label] = storage['id']
    
    selected_storage_label = st.selectbox(
        "Select Storage Location",
        ["All Locations"] + list(storage_options.keys()),
        help="Choose a storage location to view details"
    )
    
    if selected_storage_label == "All Locations":
        # Show summary of all locations
        st.markdown("### All Storage Locations")
        if storage_summary:
            df = pd.DataFrame(storage_summary).copy()
            
            # Format currency columns
            for col in ['cost', 'value']:
                df[col] = df[col].apply(lambda x: f"${x:,.2f}")
            
            st.dataframe(df, hide_index=True, width='stretch')
    else:
        # Show details for selected location
        storage_id = storage_options[selected_storage_label]
        st.markdown(f"### {selected_storage_label}")
        
        details = rl.get_storage_details(storage_id)
        if details:
            df = pd.DataFrame(details)
            
            # Format for display
            display_cols = ['series', 'year', 'mint_mark', 'variety', 'metal', 
                          'qty_remaining', 'grade', 'unit_cost', 'unit_value', 
                          'total_value', 'acquired_from']
            
            df_display = df[display_cols].copy()
            
            # Format currency columns
            for col in ['unit_cost', 'unit_value', 'total_value']:
                if col in df_display.columns:
                    df_display[col] = df_display[col].apply(lambda x: f"${x:,.2f}")
            
            st.dataframe(df_display, hide_index=True, width='stretch')
            
            # Summary metrics for this location
            if storage_id is None:
                metrics = unassigned
            else:
                metrics = next((s for s in storage_summary if s['id'] == storage_id), {})
            
            if metrics:
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Coins", metrics.get('coins', 0))
                col2.metric("Total Cost", f"${metrics.get('cost', 0):,.2f}")
                col3.metric("Total Value", f"${metrics.get('value', 0):,.2f}")

# =============================================================================
# TYPE SET PROGRESS REPORT
# =============================================================================
elif selected_report == "Type Set Progress Report":
    st.subheader("🎯 Type Set Progress Report")
    
    # Get available type sets
    type_sets = rl.get_type_set_definitions()
    
    if type_sets:
        # Select type set
        set_options = {ts['name']: ts for ts in type_sets}
        selected_set_name = st.selectbox(
            "Select Type Set",
            list(set_options.keys()),
            help="Choose a type set to view progress"
        )
        
        if selected_set_name:
            selected_set = set_options[selected_set_name]
            st.markdown(f"**{selected_set['description']}**")
            
            # Get progress
            progress = rl.get_type_set_progress(selected_set_name)
            
            if progress:
                # Display progress bar
                percent = progress.get('percent_complete', 0)
                st.progress(percent / 100.0)
                st.markdown(f"**{percent:.1f}% Complete** ({progress['total_owned']} of {progress['total_required']} coins)")
                
                # Get details
                details = rl.get_type_set_details(selected_set_name)
                if details:
                    df = pd.DataFrame(details)
                    
                    # Color code owned vs needed
                    def highlight_owned(row):
                        if row['owned'] == 'Yes':
                            return ['background-color: #d4edda'] * len(row)
                        else:
                            return ['background-color: #f8d7da'] * len(row)
                    
                    styled_df = df.style.apply(highlight_owned, axis=1)
                    st.dataframe(styled_df, hide_index=True, width='stretch')
                    
                    # Export needed list
                    needed_df = df[df['owned'] == 'No']
                    if not needed_df.empty:
                        csv = needed_df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            "📥 Download Needed Coins List (CSV)",
                            data=csv,
                            file_name=f"type_set_needed_{selected_set_name.replace(' ', '_')}.csv",
                            mime="text/csv"
                        )
    else:
        st.info("Type set definitions not configured. This feature requires additional setup.")

# =============================================================================
# BULLION HOLDINGS REPORT
# =============================================================================
elif selected_report == "Bullion Holdings Report":
    st.subheader("🥇 Bullion Holdings Report")
    
    # Get summary
    summary = rl.get_bullion_summary()
    
    if summary and summary.get('total_coins', 0) > 0:
        # Display summary metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        
        col1.metric("Total Coins", f"{int(summary.get('total_coins', 0)):,}")
        col2.metric("Fine Ounces", f"{summary.get('total_fine_oz', 0):.4f}")
        col3.metric("Total Cost", f"${summary.get('total_cost', 0):,.2f}")
        col4.metric("Melt Value", f"${summary.get('total_melt_value', 0):,.2f}")
        
        # Calculate premium/discount
        if summary.get('total_melt_value', 0) > 0:
            premium = ((summary.get('total_cost', 0) / summary.get('total_melt_value', 0)) - 1) * 100
            col5.metric("Avg Premium", f"{premium:.1f}%")
        
        # Tabs for different views
        tab1, tab2, tab3 = st.tabs(["By Metal", "Detailed Holdings", "Analysis"])
        
        with tab1:
            st.markdown("### Holdings by Metal")
            metal_data = rl.get_bullion_by_metal()
            if metal_data:
                df = pd.DataFrame(metal_data).copy()
                
                # Format columns
                for col in ['cost', 'melt_value', 'market_value']:
                    df[col] = df[col].apply(lambda x: f"${x:,.2f}")
                df['gross_oz'] = df['gross_oz'].apply(lambda x: f"{x:.4f}")
                df['fine_oz'] = df['fine_oz'].apply(lambda x: f"{x:.4f}")
                df['avg_premium'] = df['avg_premium'].apply(lambda x: f"{x:.2%}" if x else "N/A")
                
                st.dataframe(df, hide_index=True, width='stretch')
        
        with tab2:
            st.markdown("### Detailed Holdings")
            details = rl.get_bullion_details()
            if details:
                df = pd.DataFrame(details).copy()
                
                # Format for display
                display_cols = ['series', 'year', 'metal', 'qty_remaining', 
                               'fine_oz_per_coin', 'total_fine_oz', 'unit_cost',
                               'melt_value_per_coin', 'total_melt_value', 
                               'premium_to_spot', 'storage_location']
                
                df_display = df[display_cols].copy()
                
                # Format columns
                for col in ['unit_cost', 'melt_value_per_coin', 'total_melt_value']:
                    df_display[col] = df_display[col].apply(lambda x: f"${x:,.2f}")
                df_display['premium_to_spot'] = df_display['premium_to_spot'].apply(
                    lambda x: f"{x:.1%}" if x else "Spot"
                )
                
                st.dataframe(df_display, hide_index=True, width='stretch')
        
        with tab3:
            st.markdown("### Analysis")
            
            # Premium analysis
            st.markdown("#### Premium/Discount to Spot")
            
            by_metal = rl.get_bullion_by_metal()
            if by_metal:
                for metal in by_metal:
                    cost = metal['cost']
                    melt = metal['melt_value']
                    if melt > 0:
                        premium = ((cost / melt) - 1) * 100
                        st.metric(
                            f"{metal['metal']} Premium",
                            f"{premium:.1f}%",
                            delta_color="inverse" if premium > 0 else "normal"
                        )
            
            # Export all bullion data
            all_details = rl.get_bullion_details()
            if all_details:
                csv = pd.DataFrame(all_details).to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 Download Bullion Holdings (CSV)",
                    data=csv,
                    file_name=f"bullion_holdings_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
    else:
        st.info("No bullion holdings found. Bullion items should have asset_category set to 'BULLION' or 'JUNK_SILVER'")

# =============================================================================
# FOOTER
# =============================================================================
st.markdown("---")
with st.expander("ℹ️ About Reports"):
    st.markdown("""
    **Available Reports:**
    
    - **Collection Value Report**: Overall collection valuation and breakdown by category/metal
    - **Seller Report**: Detailed purchase history and performance by seller/dealer
    - **Gain/Loss Report**: Realized and unrealized gains/losses
    - **Tax Report**: Capital gains report for tax purposes (consult tax professional)
    - **Storage Report**: Inventory breakdown by storage location
    - **Type Set Progress**: Track completion of type sets
    - **Bullion Holdings**: Precious metals summary with spot price analysis
    
    **Tips:**
    - Reports use current market values from metal prices and guide prices
    - Export any report to CSV for further analysis
    - Tax reports are for informational purposes only
    - Unrealized gains/losses update with market prices
    """)
