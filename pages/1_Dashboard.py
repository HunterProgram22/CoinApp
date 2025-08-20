# pages/1_Dashboard.py
import streamlit as st
import pandas as pd
from queries import get_portfolio_summary, get_latest_spot

_SILVER_ITEMS = [
    ("American Silver Eagle (1 oz)", 1.00000),
    ("Morgan/Peace Dollar",          0.77344),
    ("Pre-1965 Half Dollar",         0.36169),
    ("Pre-1965 Quarter",             0.18084),
    ("Pre-1965 Dime",                0.07234),
]

def _get_spot_silver():
    spots = get_latest_spot() or []
    for row in spots:
        # expect rows like {'metal': 'Ag', 'price_per_oz_usd': 29.45}
        if str(row.get('metal')) == 'Ag':
            return float(row.get('price_per_oz_usd') or 0.0)
    return None

def render_silver_quick_widget(title: str = "Silver Melt Quick Reference"):
    st.subheader(title)
    spot = _get_spot_silver()
    if spot is None:
        st.info("No silver price found. Add one under Admin → Metal Prices, then refresh.")
        return

    # Metrics layout (cards)
    cols = st.columns(3)
    for i, (label, ounces) in enumerate(_SILVER_ITEMS):
        value = round(ounces * spot, 2)
        cols[i % 3].metric(label=label, value=f"${value:,.2f}", delta=f"{ounces:.5f} oz Ag @ ${spot:,.2f}")

    # Tabular view
    st.caption("Details")
    df = pd.DataFrame([
        {"Item": label, "Troy oz Ag": ounces, "Value (USD)": round(ounces * spot, 2)}
        for (label, ounces) in _SILVER_ITEMS
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)

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


render_silver_quick_widget()