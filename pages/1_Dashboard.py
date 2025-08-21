# pages/1_Dashboard.py
import numpy as np
import pandas as pd
import streamlit as st
from queries import get_portfolio_summary, get_latest_spot

# Optional helper (append its patch to queries.py if missing)
try:
    from queries import dashboard_series_rollup
except Exception:  # pragma: no cover
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

        # Friendly headers
        df = df.rename(columns={
            "metal": "Metal",
            "price_per_oz_usd": "Price Per Oz. (USD)",
        })

        # Show with 2-decimal formatting & hidden index
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

            # Show interactive grid with 2-decimal formatting
            st.dataframe(
                df_disp,
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Coins': st.column_config.NumberColumn(format="%d"),
                    'Melt Value (USD)':       st.column_config.NumberColumn(format="$%.2f"),
                    'Numismatic Value (USD)': st.column_config.NumberColumn(format="$%.2f"),
                    'Total Cost (USD)':       st.column_config.NumberColumn(format="$%.2f"),
                    'Est. Value (USD)':       st.column_config.NumberColumn(format="$%.2f"),
                    'Unrealized G/L (USD)':   st.column_config.NumberColumn(format="$%.2f"),
                    'Unrealized G/L (%)':     st.column_config.NumberColumn(format="%.2f"),
                },
            )

            # CSV download (rounded to 2 decimals)
            export_cols = ['series','coins','melt_total_usd','numi_total_usd','cost_total_usd','chosen_total_usd','unreal_gl_usd','unreal_gl_pct']
            export_cols = [c for c in export_cols if c in df.columns]
            df_export = df[export_cols].copy()
            for c in ['melt_total_usd','numi_total_usd','cost_total_usd','chosen_total_usd','unreal_gl_usd','unreal_gl_pct']:
                if c in df_export.columns:
                    df_export[c] = pd.to_numeric(df_export[c], errors='coerce').round(2)
            st.download_button(
                "Download Series Summary (CSV)",
                data=df_export.to_csv(index=False).encode('utf-8'),
                file_name="series_summary.csv",
                mime="text/csv",
            )

            # Colorized static table (now 2 decimals using Styler.format)
            with st.expander("Colorized view (static table)"):
                def color_gl(val):
                    try:
                        v = float(val)
                    except Exception:
                        return ''
                    if np.isnan(v) or v == 0:
                        return 'color: gray;'
                    return 'color: green;' if v > 0 else 'color: red;'

                df_round = df_disp.copy()
                money_cols = ['Melt Value (USD)','Numismatic Value (USD)','Total Cost (USD)','Est. Value (USD)','Unrealized G/L (USD)']
                pct_cols = ['Unrealized G/L (%)']
                for c in money_cols:
                    if c in df_round.columns:
                        df_round[c] = pd.to_numeric(df_round[c], errors='coerce').round(2)
                for c in pct_cols:
                    if c in df_round.columns:
                        df_round[c] = pd.to_numeric(df_round[c], errors='coerce').round(2)

                styled = df_round.style.applymap(color_gl, subset=['Unrealized G/L (USD)']).applymap(
                    color_gl, subset=['Unrealized G/L (%)']).format(
                    {**{c: "${:,.2f}" for c in money_cols},
                     **{c: "{:,.2f}" for c in pct_cols}}
                )

                st.table(styled)