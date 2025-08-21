
# pages/1_Dashboard.py
import io
import numpy as np
import pandas as pd
import streamlit as st
from queries import get_portfolio_summary, get_latest_spot

# Optional helper (append its patch to queries.py if missing)
try:
    from queries import dashboard_series_rollup
except Exception:
    dashboard_series_rollup = None

st.header("Dashboard")

tab_overview, tab_series = st.tabs(["📊 Overview", "📚 Series Summary"])

# ========================
# TAB: OVERVIEW
# ========================
with tab_overview:
    summary = get_portfolio_summary()
    col1, col2 = st.columns(2)
    col1.metric("Estimated Portfolio Value (USD)", f"${summary['total_estimated_value_usd']:,}")
    col2.metric("Coins on Hand", f"{summary['total_coins']:,}")

    # ---- Paste any custom cards/widgets (e.g., Silver Summary) right below this line ----

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

        # Friendly headers & hide row index
        df = df.rename(columns={
            "metal": "Metal",
            "price_per_oz_usd": "Price Per Oz. (USD)",
        })
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No metal prices yet. Add some under Admin → Metal Prices.")

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

            # Compute Unrealized G/L $ and %
            df['unreal_gl_usd'] = (df.get('chosen_total_usd', 0).fillna(0) - df.get('cost_total_usd', 0).fillna(0)).round(2)
            cost = df.get('cost_total_usd', 0).replace({0: np.nan})
            df['unreal_gl_pct'] = (df['unreal_gl_usd'] / cost * 100).round(2)

            # Friendly headers
            rename = {
                'series': 'Series',
                'coins': 'Coins',
                'melt_total_usd': 'Melt Value (USD)',
                'numi_total_usd': 'Numismatic Value (USD)',
                'cost_total_usd': 'Total Cost (USD)',
                'chosen_total_usd': 'Est. Value (USD)',
                'unreal_gl_usd': 'Unrealized G/L (USD)',
                'unreal_gl_pct': 'Unrealized G/L (%)',
            }
            df_disp = df.rename(columns=rename)

            # Column order
            order = [c for c in [
                'Series','Coins','Melt Value (USD)','Numismatic Value (USD)',
                'Total Cost (USD)','Est. Value (USD)','Unrealized G/L (USD)','Unrealized G/L (%)'
            ] if c in df_disp.columns]
            df_disp = df_disp[order]

            # Show interactive grid
            st.dataframe(df_disp, use_container_width=True, hide_index=True)

            # CSV download (raw numbers, including G/L %)
            export_cols = ['series','coins','melt_total_usd','numi_total_usd','cost_total_usd','chosen_total_usd','unreal_gl_usd','unreal_gl_pct']
            export_cols = [c for c in export_cols if c in df.columns]
            csv = df[export_cols].to_csv(index=False).encode('utf-8')
            st.download_button("Download Series Summary (CSV)", data=csv, file_name="series_summary.csv", mime="text/csv")

            # Optional: colorized static table for gains/losses
            with st.expander("Colorized view (static table)"):
                def color_gl(val):
                    try:
                        v = float(val)
                    except Exception:
                        return ''
                    if np.isnan(v) or v == 0:
                        return 'color: gray;'
                    return 'color: green;' if v > 0 else 'color: red;'

                styled = df_disp.style.applymap(color_gl, subset=['Unrealized G/L (USD)']).applymap(
                    color_gl, subset=['Unrealized G/L (%)'])

                st.table(styled)
