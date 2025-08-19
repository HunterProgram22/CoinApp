# pages/3_Inventory.py
import streamlit as st
import pandas as pd
from queries import inventory_by_type, inventory_by_series_summary, list_lots
from db import get_conn

st.header("Inventory")

# --------------------- Views ---------------------
view = st.radio("View", ["By Series (summary)", "By Type"], horizontal=True)

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
        # Friendly labels (minimal)
        rename = {
            'mint_mark': 'Mint Mark',
            'coins_on_hand': 'Qty on Hand',
            'series': 'Series',
            'year': 'Year',
        }
        df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No inventory yet.")
else:
    summary = inventory_by_series_summary()
    if summary:
        st.subheader("By Series — Summary")
        df = pd.DataFrame(summary)
        col_order = [c for c in ['series','coins','est_value_usd'] if c in df.columns]
        df = df[col_order + [c for c in df.columns if c not in col_order]]
        df = df.rename(columns={'series': 'Series', 'coins': 'Coins', 'est_value_usd': 'Est. Value (USD)'})
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No inventory yet.")

# Lots table (for context)
lots = list_lots()
if lots and view == "By Type":
    st.subheader("Lots")
    st.dataframe(pd.DataFrame(lots), use_container_width=True)
