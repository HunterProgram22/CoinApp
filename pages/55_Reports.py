# pages/55_Reports.py
import streamlit as st
from auth_utils import require_auth

# Check authentication first
require_auth()

import pandas as pd
from datetime import datetime
import report_logic as rl

st.header("📊 Reports")
st.caption("Generate comprehensive reports from your coin collection data")

# Report selector
report_types = [
    "Collection Value Report",
    "Seller Report"
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
                
                # Additional metrics row
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Unique Coin Types", int(summary.get('unique_coin_types', 0)))
                col2.metric("Current Value", f"${summary.get('total_current_value_usd', 0):,.2f}")
                
                gain_loss = summary.get('unrealized_gain_loss', 0)
                gain_loss_pct = summary.get('gain_loss_percent', 0)
                
                if gain_loss >= 0:
                    col3.metric("Unrealized G/L", f"${gain_loss:,.2f}", 
                               f"{gain_loss_pct:.1f}%", delta_color="normal")
                else:
                    col3.metric("Unrealized G/L", f"${gain_loss:,.2f}", 
                               f"{gain_loss_pct:.1f}%", delta_color="inverse")
                
                col4.metric("Coins Sold", int(summary.get('coins_sold', 0)))
                
                # Tabs for details
                tab1, tab2, tab3 = st.tabs(["By Coin Type", "Transactions", "Export"])
                
                with tab1:
                    st.markdown("### Purchases by Coin Type")
                    detail_data = rl.get_seller_detail_by_coin_type(party_id)
                    if detail_data:
                        df = pd.DataFrame(detail_data).copy()
                        
                        # Format the dataframe for display
                        df['coin'] = df.apply(
                            lambda r: f"{r['series']} {r['year']}" + 
                                     (f" {r['mint_mark']}" if r['mint_mark'] else "") +
                                     (f" • {r['variety']}" if r['variety'] else ""),
                            axis=1
                        )
                        
                        # Calculate gain/loss percentage for each coin type
                        df['gl_percent'] = df.apply(
                            lambda r: ((r['unrealized_gl'] / r['cost_of_remaining'] * 100) 
                                      if r['cost_of_remaining'] and r['cost_of_remaining'] > 0 else 0),
                            axis=1
                        )
                        
                        # Select and rename columns for display
                        display_df = df[[
                            'coin', 'metal', 'asset_category', 'total_purchased', 'qty_remaining',
                            'avg_purchase_price', 'total_spent', 'cost_of_remaining', 
                            'current_value', 'unrealized_gl', 'gl_percent', 'best_grade',
                            'first_purchase', 'last_purchase'
                        ]].copy()
                        
                        display_df = display_df.rename(columns={
                            'coin': 'Coin',
                            'metal': 'Metal',
                            'asset_category': 'Category',
                            'total_purchased': 'Purchased',
                            'qty_remaining': 'On Hand',
                            'avg_purchase_price': 'Avg Price',
                            'total_spent': 'Total Spent',
                            'cost_of_remaining': 'Cost (On Hand)',
                            'current_value': 'Current Value',
                            'unrealized_gl': 'Unrealized G/L',
                            'gl_percent': 'G/L %',
                            'best_grade': 'Grade',
                            'first_purchase': 'First Purchase',
                            'last_purchase': 'Last Purchase'
                        })
                        
                        # Format money columns
                        money_cols = ['Avg Price', 'Total Spent', 'Cost (On Hand)', 'Current Value', 'Unrealized G/L']
                        for col in money_cols:
                            display_df[col] = display_df[col].apply(lambda x: f"${x:,.2f}")
                        
                        display_df['G/L %'] = display_df['G/L %'].apply(lambda x: f"{x:.1f}%")
                        
                        st.dataframe(display_df, hide_index=True, width='stretch')
                
                with tab2:
                    st.markdown("### Transaction History")
                    
                    if group_by_date:
                        st.info("📊 Transactions on the same date are grouped together as one logical transaction")
                    
                    transactions = rl.get_seller_transactions(party_id, group_by_date)
                    if transactions:
                        df = pd.DataFrame(transactions).copy()
                        
                        # Modify column names based on grouping
                        if group_by_date:
                            rename_dict = {
                                'tx_ids': 'TX IDs',
                                'db_transaction_count': 'DB Entries',
                                'tx_date': 'Date',
                                'line_items': 'Items',
                                'total_quantity': 'Qty',
                                'subtotal': 'Subtotal',
                                'shipping': 'Shipping',
                                'tax': 'Tax',
                                'fees': 'Fees',
                                'total': 'Total',
                                'notes': 'Notes'
                            }
                        else:
                            rename_dict = {
                                'tx_ids': 'TX#',
                                'tx_date': 'Date',
                                'line_items': 'Items',
                                'total_quantity': 'Qty',
                                'subtotal': 'Subtotal',
                                'shipping': 'Shipping',
                                'tax': 'Tax',
                                'fees': 'Fees',
                                'total': 'Total',
                                'notes': 'Notes'
                            }
                        
                        # Format for display
                        display_tx = df.rename(columns=rename_dict)
                        
                        # Remove the db_transaction_count column if not grouping
                        if not group_by_date and 'DB Entries' in display_tx.columns:
                            display_tx = display_tx.drop(columns=['DB Entries'])
                        
                        # Format money columns
                        money_cols = ['Subtotal', 'Shipping', 'Tax', 'Fees', 'Total']
                        for col in money_cols:
                            if col in display_tx.columns:
                                display_tx[col] = display_tx[col].apply(lambda x: f"${x:,.2f}" if x else "$0.00")
                        
                        st.dataframe(display_tx, hide_index=True, width='stretch')
                
                with tab3:
                    st.markdown("### Export Data")
                    
                    # Prepare all data for export
                    export_summary = pd.DataFrame([summary])
                    export_details = pd.DataFrame(rl.get_seller_detail_by_coin_type(party_id))
                    export_transactions = pd.DataFrame(rl.get_seller_transactions(party_id, False))
                    
                    # Create combined export
                    export_data = pd.concat(
                        [export_summary, export_details, export_transactions],
                        keys=['Summary', 'Coin Details', 'Transactions'],
                        names=['Report Section', 'Row']
                    )
                    
                    csv = export_data.to_csv().encode('utf-8')
                    st.download_button(
                        "📥 Download Seller Report (CSV)",
                        data=csv,
                        file_name=f"seller_report_{party_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )

# =============================================================================
# FOOTER
# =============================================================================
st.markdown("---")
with st.expander("ℹ️ About Reports"):
    st.markdown("""
    **Available Reports:**
    
    - **Collection Value Report**: Overall collection valuation with breakdown by category, metal type, and top valued coins. Shows unrealized gains/losses based on current market values.
    
    - **Seller Report**: Detailed purchase history and performance analysis for each seller/dealer. Track what you bought, when, and how your purchases are performing.
    
    **Tips:**
    - Reports use current market values from your metal prices and guide prices
    - Unrealized gains/losses are based on your chosen valuation method for each lot
    - Export any report to CSV for further analysis in Excel
    - Group transactions by date in the Seller Report to see logical purchase sessions
    """)
