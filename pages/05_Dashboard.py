# pages/05_Dashboard.py
import pandas as pd
import streamlit as st
from queries import get_portfolio_summary, get_latest_metal_prices, get_dashboard_series_rollup
from dashboard_helpers import (
    format_metal_prices_dataframe,
    calculate_silver_melt_values,
    calculate_series_unrealized_gl,
    prepare_series_display_dataframe,
    get_series_column_config,
    prepare_series_export_data,
    apply_gain_loss_styling
)


st.header("Dashboard")

tab_overview, tab_series = st.tabs(["📊 Overview", "📚 Series Summary"])


def render_portfolio_overview():
    """Render the portfolio overview section."""
    summary = get_portfolio_summary()
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Estimated Portfolio Value (USD)", f"${summary['total_estimated_value_usd']:,}")
    
    with col2:
        st.metric("Coins on Hand", f"{summary['total_coins']:,}")


def render_spot_prices():
    """Render the latest spot prices section."""
    st.subheader("Latest Spot Prices")
    
    spots_data = get_latest_metal_prices()
    df = format_metal_prices_dataframe(spots_data)
    
    if df is not None:
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Metal": st.column_config.TextColumn(),
                "Price Per Oz. (USD)": st.column_config.NumberColumn(format="$%.2f"),
            },
        )
    else:
        st.info("No metal prices yet. Add some under Admin → Metal Prices.")
    
    return {r['metal']: r['price_per_oz_usd'] for r in spots_data} if spots_data else {}


def render_silver_melt_reference(spot_prices):
    """Render the quick silver melt reference section."""
    st.subheader("Quick Silver Melt Reference")
    
    silver_price = spot_prices.get('Ag')
    
    if silver_price is None:
        st.info("No silver spot price found. Update via Admin → Metal Prices.")
        return
    
    df_melt = calculate_silver_melt_values(silver_price)
    st.dataframe(df_melt, use_container_width=True)


def render_series_summary():
    """Render the series summary tab."""
    rows = get_dashboard_series_rollup()
    if not rows:
        st.info("No inventory yet.")
        return
    
    # Process data
    df = pd.DataFrame(rows)
    df = calculate_series_unrealized_gl(df)
    df_display = prepare_series_display_dataframe(df)
    
    # Display interactive dataframe
    st.dataframe(
        df_display,
        use_container_width=True,
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


# ========================
# TAB: OVERVIEW
# ========================
with tab_overview:
    render_portfolio_overview()
    
    # ---- Paste any custom cards/widgets (e.g., Silver Summary) right below this line ----
    
    spot_prices = render_spot_prices()
    render_silver_melt_reference(spot_prices)

# ========================
# TAB: SERIES SUMMARY
# ========================
with tab_series:
    render_series_summary()
