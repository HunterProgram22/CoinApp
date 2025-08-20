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


# Optional rollup helper (append its patch to queries.py if missing)
try:
    from queries import dashboard_series_rollup
except Exception:
    dashboard_series_rollup = None

st.header("Dashboard")

tab_overview, tab_series = st.tabs(["📊 Overview", "📚 Series Summary"])

# ========================
# TAB: OVERVIEW (keep your existing cards here)
# ========================
with tab_overview:
    summary = get_portfolio_summary()
    col1, col2 = st.columns(2)
    col1.metric("Estimated Portfolio Value (USD)", f"${summary['total_estimated_value_usd']:,}")
    col2.metric("Coins on Hand", f"{summary['total_coins']:,}")

    # ---- (Optional) Your existing custom cards/widgets (e.g., Silver Summary) ----
    # Paste your existing custom Dashboard blocks right below this comment so they remain on the Overview tab.
    # ----------------------------------------------------------------------------

    st.subheader("Latest Spot Prices")
    spots = get_latest_spot()
    if spots:
        df = pd.DataFrame(spots)

        # Friendly order: Ag, Au, Pt, Pd (where present)
        if "metal" in df.columns:
            try:
                order = pd.Categorical(df["metal"], categories=["Ag","Au","Pt","Pd"], ordered=True)
                df = df.assign(metal=order).sort_values("metal").assign(metal=df["metal"].astype(str))
            except Exception:
                pass

        # Friendly headers
        df = df.rename(columns={
            "metal": "Metal",
            "price_per_oz_usd": "Price Per Oz. (USD)",
        })
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No metal prices yet. Add some under Admin → Metal Prices.")

    render_silver_quick_widget()
# ========================
# TAB: SERIES SUMMARY
# ========================
with tab_series:
    if dashboard_series_rollup is None:
        st.warning("Series rollup helper not found in queries.py. Please apply the provided patch, then reload.")
    else:
        rows = dashboard_series_rollup()
        if not rows:
            st.info("No inventory yet.")
        else:
            df = pd.DataFrame(rows)

            # Compute Unrealized G/L
            if {'chosen_total_usd','cost_total_usd'}.issubset(df.columns):
                df['unreal_gl_usd'] = (df['chosen_total_usd'].fillna(0) - df['cost_total_usd'].fillna(0)).round(2)
            else:
                df['unreal_gl_usd'] = None

            # Friendly columns
            rename = {
                'series': 'Series',
                'coins': 'Coins',
                'melt_total_usd': 'Melt Value (USD)',
                'numi_total_usd': 'Numismatic Value (USD)',
                'cost_total_usd': 'Total Cost (USD)',
                'chosen_total_usd': 'Est. Value (USD)',
                'unreal_gl_usd': 'Unrealized G/L (USD)',
            }
            df = df.rename(columns=rename)

            # Order columns
            order = [c for c in [
                'Series','Coins','Melt Value (USD)','Numismatic Value (USD)',
                'Total Cost (USD)','Est. Value (USD)','Unrealized G/L (USD)'
            ] if c in df.columns]
            df = df[order]

            st.dataframe(df, use_container_width=True, hide_index=True)