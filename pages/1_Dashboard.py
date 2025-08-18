# pages/1_Dashboard.py
import streamlit as st
import pandas as pd
from queries import get_portfolio_summary, get_latest_spot

st.header("Dashboard")

summary = get_portfolio_summary()
col1, col2 = st.columns(2)
col1.metric("Estimated Portfolio Value (USD)", f"${summary['total_estimated_value_usd']:,}")
col2.metric("Coins on Hand", f"{summary['total_coins']:,}")

st.subheader("Latest Spot Prices")
spots = get_latest_spot()
if spots:
    st.dataframe(pd.DataFrame(spots))
else:
    st.info("No metal prices yet. Add some under Settings or via script.")
