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

    # --- Quick Silver Melt Reference ---
    spots = {r['metal']: r['price_per_oz_usd'] for r in get_latest_spot()}
    ag = spots.get('Ag')

    st.subheader("Quick Silver Melt Reference")
    if ag is None:
        st.info("No silver spot price found. Update via Admin → Metal Prices.")
    else:
        # Fine troy ounces per coin (U.S. 90% silver for pre-1965)
        SAE_FINE_OZ = 1.00000  # American Silver Eagle (1 oz .999 fine; use 1.0 for melt calc)
        MORGAN_PEACE_FINE_OZ = 0.77344  # Morgan/Peace dollar (26.73g, .900 fine)
        HALF_FINE_OZ = 0.36169  # Pre-1965 half dollar (12.50g, .900 fine)
        QUARTER_FINE_OZ = 0.18084  # Pre-1965 quarter (6.25g, .900 fine)
        DIME_FINE_OZ = 0.07234  # Pre-1965 dime (2.50g, .900 fine)

        rows = [
            {"Item": "American Silver Eagle (1 oz)", "Fine Oz": SAE_FINE_OZ,
             "Melt (USD)": round(ag * SAE_FINE_OZ, 2)},
            {"Item": "Morgan/Peace Dollar (90%)", "Fine Oz": MORGAN_PEACE_FINE_OZ,
             "Melt (USD)": round(ag * MORGAN_PEACE_FINE_OZ, 2)},
            {"Item": "Pre-1965 Half Dollar (90%)", "Fine Oz": HALF_FINE_OZ,
             "Melt (USD)": round(ag * HALF_FINE_OZ, 2)},
            {"Item": "Pre-1965 Quarter (90%)", "Fine Oz": QUARTER_FINE_OZ,
             "Melt (USD)": round(ag * QUARTER_FINE_OZ, 2)},
            {"Item": "Pre-1965 Dime (90%)", "Fine Oz": DIME_FINE_OZ,
             "Melt (USD)": round(ag * DIME_FINE_OZ, 2)},
        ]
        df_qs = pd.DataFrame(rows)
        # Format for display
        df_qs["Melt (USD)"] = df_qs["Melt (USD)"].map(lambda x: f"${x:,.2f}")
        df_qs["Fine Oz"] = df_qs["Fine Oz"].map(lambda x: f"{x:.5f}")
        # Make 'Item' the index so there's no numeric index column
        df_qs = df_qs.set_index("Item")
        st.dataframe(df_qs, use_container_width=True)
    # --- end Quick Silver Melt Reference ---

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