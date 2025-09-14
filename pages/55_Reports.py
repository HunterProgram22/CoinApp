# pages/55_Reports.py
import streamlit as st
from auth_utils import require_auth

# Check authentication first
require_auth()
# pages/55_Reports.py
import streamlit as st
import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import date, timedelta
from db_operations import execute_query_all, execute_query_single

st.header("📊 Reports")

# ---------------------------------
# Data Access Functions for Seller Report
# ---------------------------------
def get_sellers_with_transactions() -> List[Dict[str, Any]]:
    """Get all parties who have sold coins (BUY transactions)."""
    query = """
        SELECT DISTINCT 
            p.id,
            p.name,
            COUNT(DISTINCT t.id) as transaction_count,
            MIN(t.tx_date) as first_transaction,
            MAX(t.tx_date) as last_transaction,
            SUM(ABS(tl.quantity)) as total_coins
        FROM tx t
        JOIN party p ON p.id = t.party_id
        JOIN tx_line tl ON tl.tx_id = t.id
        WHERE t.tx_type = 'BUY' AND p.name IS NOT NULL
        GROUP BY p.id, p.name
        ORDER BY p.name
    """
    return execute_query_all(query)


def get_seller_summary(party_id: int) -> Dict[str, Any]:
    """Get summary statistics for a specific seller."""
    query = """
        WITH purchase_data AS (
            SELECT 
                t.id as tx_id,
                t.tx_date,
                tl.id as line_id,
                tl.coin_type_id,
                ABS(tl.quantity) as quantity,
                tl.unit_price,
                l.id as lot_id,
                l.qty_remaining,
                l.unit_cost,
                -- Add allocated shipping/tax/fees to unit cost
                l.unit_cost * l.qty_remaining as lot_cost,
                v.chosen_unit_value,
                v.chosen_unit_value * l.qty_remaining as current_value
            FROM tx t
            JOIN tx_line tl ON tl.tx_id = t.id
            JOIN lot l ON l.acquisition_line_id = tl.id
            LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
            WHERE t.party_id = ? AND t.tx_type = 'BUY'
        )
        SELECT 
            COUNT(DISTINCT tx_id) as unique_transactions,
            SUM(quantity) as total_coins_purchased,
            COUNT(DISTINCT coin_type_id) as unique_coin_types,
            SUM(lot_cost) as total_cost_usd,
            SUM(current_value) as total_current_value_usd,
            SUM(current_value) - SUM(lot_cost) as unrealized_gain_loss,
            CASE 
                WHEN SUM(lot_cost) > 0 THEN 
                    ((SUM(current_value) - SUM(lot_cost)) / SUM(lot_cost)) * 100
                ELSE 0 
            END as gain_loss_percent,
            SUM(qty_remaining) as coins_still_held,
            SUM(quantity) - SUM(qty_remaining) as coins_sold
        FROM purchase_data
    """
    result = execute_query_single(query, (party_id,))
    return result if result else {}


def get_seller_detail_by_coin_type(party_id: int) -> List[Dict[str, Any]]:
    """Get detailed purchases by coin type from a specific seller."""
    query = """
        SELECT 
            cm.series,
            ct.year,
            ct.mint_mark,
            COALESCE(ct.variety, '') as variety,
            cm.metal,
            cm.asset_category,
            COUNT(DISTINCT t.id) as purchase_transactions,
            SUM(ABS(tl.quantity)) as total_purchased,
            ROUND(AVG(tl.unit_price), 2) as avg_purchase_price,
            ROUND(SUM(ABS(tl.quantity) * tl.unit_price), 2) as total_spent,
            SUM(l.qty_remaining) as qty_remaining,
            ROUND(SUM(l.qty_remaining * l.unit_cost), 2) as cost_of_remaining,
            ROUND(SUM(l.qty_remaining * v.chosen_unit_value), 2) as current_value,
            ROUND(SUM(l.qty_remaining * v.chosen_unit_value) - SUM(l.qty_remaining * l.unit_cost), 2) as unrealized_gl,
            MIN(t.tx_date) as first_purchase,
            MAX(t.tx_date) as last_purchase,
            COALESCE(MAX(l.estimated_grade_text), MAX(l.purchase_grade_text)) as best_grade
        FROM tx t
        JOIN tx_line tl ON tl.tx_id = t.id
        JOIN coin_type ct ON ct.id = tl.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        JOIN lot l ON l.acquisition_line_id = tl.id
        LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
        WHERE t.party_id = ? AND t.tx_type = 'BUY'
        GROUP BY cm.series, ct.year, ct.mint_mark, ct.variety, cm.metal, cm.asset_category
        ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety
    """
    return execute_query_all(query, (party_id,))


def get_seller_transactions(party_id: int) -> List[Dict[str, Any]]:
    """Get all transactions from a specific seller."""
    query = """
        SELECT 
            t.id,
            t.tx_date,
            COUNT(tl.id) as line_items,
            SUM(ABS(tl.quantity)) as total_quantity,
            ROUND(SUM(ABS(tl.quantity) * tl.unit_price), 2) as subtotal,
            t.shipping,
            t.tax,
            t.fees,
            ROUND(SUM(ABS(tl.quantity) * tl.unit_price) + 
                  COALESCE(t.shipping, 0) + COALESCE(t.tax, 0) + COALESCE(t.fees, 0), 2) as total,
            t.notes
        FROM tx t
        JOIN tx_line tl ON tl.tx_id = t.id
        WHERE t.party_id = ? AND t.tx_type = 'BUY'
        GROUP BY t.id, t.tx_date, t.shipping, t.tax, t.fees, t.notes
        ORDER BY t.tx_date DESC
    """
    return execute_query_all(query, (party_id,))


# ---------------------------------
# Report Generation Functions
# ---------------------------------
def generate_seller_report(party_id: int, party_name: str):
    """Generate the seller report display."""
    
    # Get summary data
    summary = get_seller_summary(party_id)
    
    if not summary or summary.get('unique_transactions', 0) == 0:
        st.warning(f"No purchase transactions found for {party_name}")
        return
    
    # Display party info
    st.subheader(f"Seller Report: {party_name}")
    
    # Summary metrics
    st.markdown("### Summary")
    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric("Transactions", int(summary.get('unique_transactions', 0)))
    col2.metric("Total Coins Purchased", int(summary.get('total_coins_purchased', 0)))
    col3.metric("Unique Coin Types", int(summary.get('unique_coin_types', 0)))
    col4.metric("Coins Still Held", int(summary.get('coins_still_held', 0)))
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_cost = float(summary.get('total_cost_usd', 0))
    col1.metric("Total Cost", f"${total_cost:,.2f}")
    
    current_value = float(summary.get('total_current_value_usd', 0))
    col2.metric("Current Est. Value", f"${current_value:,.2f}")
    
    gain_loss = float(summary.get('unrealized_gain_loss', 0))
    gain_loss_pct = float(summary.get('gain_loss_percent', 0))
    
    # Color the gain/loss based on positive/negative
    if gain_loss > 0:
        col3.metric("Unrealized Gain/Loss", f"${gain_loss:,.2f}", 
                   f"{gain_loss_pct:.1f}%", delta_color="normal")
    elif gain_loss < 0:
        col3.metric("Unrealized Gain/Loss", f"${gain_loss:,.2f}", 
                   f"{gain_loss_pct:.1f}%", delta_color="inverse")
    else:
        col3.metric("Unrealized Gain/Loss", f"${gain_loss:,.2f}")
    
    coins_sold = int(summary.get('coins_sold', 0))
    col4.metric("Coins Sold", coins_sold)
    
    # Add tabs for different views
    tab1, tab2, tab3 = st.tabs(["By Coin Type", "By Transaction", "Analysis"])
    
    with tab1:
        st.markdown("### Purchases by Coin Type")
        
        # Get detailed data
        detail_data = get_seller_detail_by_coin_type(party_id)
        
        if detail_data:
            df = pd.DataFrame(detail_data)
            
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
            ]].rename(columns={
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
            
            # Display the dataframe
            st.dataframe(display_df, width='stretch', hide_index=True)
            
            # Download button
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download Coin Type Details (CSV)",
                data=csv,
                file_name=f"seller_report_{party_name.replace(' ', '_')}_by_coin.csv",
                mime="text/csv"
            )
    
    with tab2:
        st.markdown("### Transaction History")
        
        transactions = get_seller_transactions(party_id)
        
        if transactions:
            tx_df = pd.DataFrame(transactions)
            
            # Format for display
            display_tx = tx_df.rename(columns={
                'id': 'TX#',
                'tx_date': 'Date',
                'line_items': 'Items',
                'total_quantity': 'Qty',
                'subtotal': 'Subtotal',
                'shipping': 'Shipping',
                'tax': 'Tax',
                'fees': 'Fees',
                'total': 'Total',
                'notes': 'Notes'
            })
            
            # Format money columns
            money_cols = ['Subtotal', 'Shipping', 'Tax', 'Fees', 'Total']
            for col in money_cols:
                if col in display_tx.columns:
                    display_tx[col] = display_tx[col].apply(lambda x: f"${x:,.2f}" if x else "$0.00")
            
            st.dataframe(display_tx, width='stretch', hide_index=True)
            
            # Download button
            csv = tx_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download Transaction History (CSV)",
                data=csv,
                file_name=f"seller_report_{party_name.replace(' ', '_')}_transactions.csv",
                mime="text/csv"
            )
    
    with tab3:
        st.markdown("### Analysis")
        
        # Performance by metal
        if detail_data:
            metal_df = pd.DataFrame(detail_data)
            metal_summary = metal_df.groupby('metal').agg({
                'total_purchased': 'sum',
                'qty_remaining': 'sum',
                'cost_of_remaining': 'sum',
                'current_value': 'sum',
                'unrealized_gl': 'sum'
            }).round(2)
            
            if not metal_summary.empty:
                st.markdown("#### Performance by Metal")
                metal_summary['gl_percent'] = (metal_summary['unrealized_gl'] / metal_summary['cost_of_remaining'] * 100).round(1)
                
                display_metal = metal_summary.rename(columns={
                    'total_purchased': 'Purchased',
                    'qty_remaining': 'On Hand',
                    'cost_of_remaining': 'Cost',
                    'current_value': 'Value',
                    'unrealized_gl': 'G/L',
                    'gl_percent': 'G/L %'
                })
                
                # Format for display
                for col in ['Cost', 'Value', 'G/L']:
                    display_metal[col] = display_metal[col].apply(lambda x: f"${x:,.2f}")
                display_metal['G/L %'] = display_metal['G/L %'].apply(lambda x: f"{x:.1f}%")
                
                st.dataframe(display_metal, width='stretch')
        
        # Timeline analysis
        if transactions:
            st.markdown("#### Purchase Timeline")
            timeline_df = pd.DataFrame(transactions)
            timeline_df['tx_date'] = pd.to_datetime(timeline_df['tx_date'])
            timeline_df['year_month'] = timeline_df['tx_date'].dt.to_period('M')
            
            monthly_summary = timeline_df.groupby('year_month').agg({
                'id': 'count',
                'total_quantity': 'sum',
                'total': 'sum'
            }).rename(columns={
                'id': 'Transactions',
                'total_quantity': 'Coins',
                'total': 'Amount'
            })
            
            monthly_summary.index = monthly_summary.index.astype(str)
            monthly_summary['Amount'] = monthly_summary['Amount'].apply(lambda x: f"${x:,.2f}")
            
            st.dataframe(monthly_summary, width='stretch')


# ---------------------------------
# UI Components
# ---------------------------------
def render_report_selector():
    """Render the report type selector."""
    report_types = [
        "Seller Report",
        # Future reports can be added here
        # "Collection Value Report",
        # "Gain/Loss Report",
        # "Storage Location Report",
        # "Type Set Progress Report",
        # "Bullion Holdings Report",
        # "Tax Report"
    ]
    
    selected_report = st.selectbox(
        "Select Report Type",
        report_types,
        help="Choose the type of report to generate"
    )
    
    return selected_report


def render_seller_report():
    """Render the seller report interface."""
    sellers = get_sellers_with_transactions()
    
    if not sellers:
        st.info("No sellers found. Add some BUY transactions first.")
        return
    
    # Create seller options with transaction counts
    seller_options = {}
    for seller in sellers:
        logical_count = seller['logical_transaction_count']
        db_count = seller['db_transaction_count']
        
        # Show both counts if they differ
        if logical_count != db_count:
            label = f"{seller['name']} ({logical_count} purchase dates from {db_count} entries, {seller['total_coins']} coins)"
        else:
            label = f"{seller['name']} ({logical_count} transactions, {seller['total_coins']} coins)"
        
        seller_options[label] = (seller['id'], seller['name'])
    
    selected_label = st.selectbox(
        "Select Seller",
        [""] + list(seller_options.keys()),
        help="Choose a seller to generate report. Numbers show logical transactions (by date) vs database entries."
    )
    
    if selected_label and selected_label != "":
        party_id, party_name = seller_options[selected_label]
        
        # Date range filter (optional)
        with st.expander("Filter Options", expanded=False):
            col1, col2 = st.columns(2)
            filter_dates = col1.checkbox("Filter by date range", value=False)
            
            if filter_dates:
                date_from = col1.date_input("From date", value=date.today() - timedelta(days=365))
                date_to = col2.date_input("To date", value=date.today())
                st.info("Date filtering not yet implemented in this version")
        
        # Generate the report
        generate_seller_report(party_id, party_name)


# ---------------------------------
# Main UI
# ---------------------------------
st.caption("Generate comprehensive reports from your coin collection data")

# Report selector
report_type = render_report_selector()

st.divider()

# Render the selected report
if report_type == "Seller Report":
    render_seller_report()
# Add more report types here as they are developed
# elif report_type == "Collection Value Report":
#     render_collection_value_report()
# elif report_type == "Gain/Loss Report":
#     render_gain_loss_report()

# Footer with help information
st.markdown("---")
with st.expander("ℹ️ About Reports"):
    st.markdown("""
    **Available Reports:**
    
    **Seller Report**
    - View all purchases from a specific seller/dealer
    - Track performance and unrealized gains/losses
    - Analyze purchases by coin type
    - Review transaction history
    - See performance by metal type
    
    **Coming Soon:**
    - Collection Value Report - Overall collection valuation
    - Gain/Loss Report - Realized and unrealized P&L
    - Tax Report - Capital gains for tax purposes
    - Storage Report - Detailed inventory by location
    - Type Set Progress - Completion status of type sets
    - Bullion Holdings - Precious metals summary
    
    **Tips:**
    - Reports use current market values from your metal prices and guide prices
    - Unrealized gains/losses are based on your chosen valuation method
    - Export any report to CSV for further analysis in Excel
    """)
