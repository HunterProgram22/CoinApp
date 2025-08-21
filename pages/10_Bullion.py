# pages/12_Bullion.py
import streamlit as st
import pandas as pd
from queries import get_latest_spot  # optional, for context
try:
    from queries import bullion_by_category, bullion_by_series
except ImportError:
    st.error("Please copy patches/queries_bullion_additions.py functions into queries.py before using this page.")
    st.stop()

st.header("Bullion Overview (Rounds & Bars)")

# Context: spot prices
spots = get_latest_spot()
if spots:
    st.caption("Latest spot (from your metal_price table):")
    st.dataframe(pd.DataFrame(spots).rename(columns={
        "metal":"Metal", "price_per_oz_usd":"Price per oz (USD)"
    }), hide_index=True, use_container_width=True)

tab_cat, tab_series = st.tabs(["By Category", "By Series"])

with tab_cat:
    rows = bullion_by_category()
    if not rows:
        st.info("No bullion (ROUND/BAR) detected yet. Set 'asset_category' on your Coin Master records.")
    else:
        df = pd.DataFrame(rows)
        df = df.rename(columns={
            "category":"Category", "metal":"Metal", "units_on_hand":"Units",
            "gross_oz":"Gross oz", "fine_oz":"Fine oz", "melt_value_usd":"Melt Value (USD)"
        })
        # Formatting
        fmt = {"Gross oz":"{:.4f}", "Fine oz":"{:.4f}", "Melt Value (USD)":"${:,.2f}"}
        st.dataframe(df.style.format(fmt), hide_index=True, use_container_width=True)
        st.download_button("Download CSV (By Category)",
                           data=df.to_csv(index=False).encode("utf-8"),
                           file_name="bullion_by_category.csv", mime="text/csv")

with tab_series:
    rows = bullion_by_series()
    if not rows:
        st.info("No bullion (ROUND/BAR) detected yet. Set 'asset_category' on your Coin Master records.")
    else:
        df = pd.DataFrame(rows)
        df = df.rename(columns={
            "category":"Category", "metal":"Metal", "series":"Series",
            "unit_troy_oz":"Unit troy oz", "unit_fine_oz":"Unit fine oz",
            "units_on_hand":"Units", "gross_oz":"Gross oz", "fine_oz":"Fine oz",
            "melt_value_usd":"Melt Value (USD)"
        })
        fmt = {"Unit troy oz":"{:.4f}", "Unit fine oz":"{:.4f}", "Gross oz":"{:.4f}", "Fine oz":"{:.4f}", "Melt Value (USD)":"${:,.2f}"}
        st.dataframe(df.style.format(fmt), hide_index=True, use_container_width=True)
        st.download_button("Download CSV (By Series)",
                           data=df.to_csv(index=False).encode("utf-8"),
                           file_name="bullion_by_series.csv", mime="text/csv")

st.markdown("---")
st.caption("Tip: Use your Coin Master editor to set **asset_category = ROUND or BAR** on products like generic Buffalo rounds, APMEX bars, 10 oz bars, etc. "
           "Valuation uses your melt setup via weight×fineness×spot.")