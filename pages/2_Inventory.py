# pages/3_Inventory.py
import streamlit as st
import pandas as pd
from queries import inventory_by_type, inventory_by_series_summary, list_lots

# Optional (patched) helpers
try:
    from queries import list_series_for_filter, inventory_details_by_series
except Exception:
    list_series_for_filter = None
    inventory_details_by_series = None

st.header("Inventory")

view = st.radio("View", ["By Type", "By Series (summary)", "Filter by Series (detail)"], horizontal=True, key="inv_view")

if view == "By Type":
    inv = inventory_by_type()
    if inv:
        st.subheader("By Type")
        df = pd.DataFrame(inv)
        # Hide internal ID and put Series first
        if 'coin_type_id' in df.columns:
            df = df.drop(columns=['coin_type_id'])
        first_order = [c for c in ['series','year','mint_mark','variety','coins_on_hand'] if c in df.columns]
        df = df[first_order + [c for c in df.columns if c not in first_order]]
        rename = {'mint_mark': 'Mint Mark', 'coins_on_hand': 'Qty on Hand', 'series': 'Series', 'year': 'Year'}
        df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No inventory yet.")

elif view == "By Series (summary)":
    summary = inventory_by_series_summary()
    if summary:
        st.subheader("By Series — Summary")
        df = pd.DataFrame(summary)
        col_order = [c for c in ['series','coins','est_value_usd'] if c in df.columns]
        df = df[col_order + [c for c in df.columns if c not in col_order]]
        df = df.rename(columns={'series': 'Series', 'coins': 'Coins', 'est_value_usd': 'Est. Value (USD)'})
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No inventory yet.")

else:  # Filter by Series (detail)
    if list_series_for_filter is None or inventory_details_by_series is None:
        st.warning("Series detail helpers not found in queries.py. Please apply the provided patch, then reload.")
    else:
        series_list = list_series_for_filter(only_on_hand=True)
        if not series_list:
            st.info("No series to show yet.")
        else:
            selected = st.selectbox("Choose a series", options=series_list, key="inv_series_select")
            rows = inventory_details_by_series(selected) if selected else []
            if not rows:
                st.info("No on-hand coins for that series.")
            else:
                df = pd.DataFrame(rows)
                # Friendly column names
                rename = {
                    "acquired_date": "Acquired",
                    "mint_mark": "Mint Mark",
                    "qty_remaining": "Qty",
                    "unit_cost_usd": "Unit Cost (USD)",
                    "melt_unit_usd": "Melt/coin (USD)",
                    "melt_total_usd": "Melt×Qty (USD)",
                    "grade": "Grade",
                    "flip_ids": "Flip IDs",
                }
                df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
                # Column order
                order = [c for c in ["Acquired","Flip IDs","series","year","Mint Mark","variety","Party","Qty","Unit Cost (USD)","Melt/coin (USD)","Melt×Qty (USD)","Grade"] if c in df.columns]
                df = df[[c for c in order if c in df.columns] + [c for c in df.columns if c not in order]]
                # Pretty blanks
                for c in ["variety","flip_ids","Grade","Party","Mint Mark"]:
                    if c in df.columns:
                        df[c] = df[c].replace({"": "—", None: "—"})
                st.dataframe(df, use_container_width=True, hide_index=True)

# Keep Lots section minimal when on Type view (optional)
lots = list_lots()
if lots and view == "By Type":
    st.subheader("Lots")
    st.dataframe(pd.DataFrame(lots), use_container_width=True, hide_index=True)