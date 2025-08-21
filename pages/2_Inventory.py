# pages/2_Inventory.py
import io
import streamlit as st
import pandas as pd

from queries import inventory_by_type, inventory_by_series_summary, list_lots

# Optional (patched) helpers for detailed and flag views
try:
    from queries import list_series_for_filter, inventory_details_by_series
except Exception:  # pragma: no cover
    list_series_for_filter = None
    inventory_details_by_series = None

try:
    from queries import inventory_details_proof, inventory_details_slabbed
except Exception:  # pragma: no cover
    inventory_details_proof = None
    inventory_details_slabbed = None

st.header("Inventory")

def _download_csv_button(df: pd.DataFrame, filename: str, money_cols=None, int_cols=None, key: str = None):
    """Render a CSV download button for df, rounding money cols to 2 decimals and casting ints."""
    money_cols = money_cols or []
    int_cols = int_cols or []
    df_export = df.copy()
    for c in money_cols:
        if c in df_export.columns:
            df_export[c] = pd.to_numeric(df_export[c], errors='coerce').round(2)
    for c in int_cols:
        if c in df_export.columns:
            # Cast safely to int, preserving blanks
            df_export[c] = pd.to_numeric(df_export[c], errors='coerce')
            if df_export[c].notna().all():
                df_export[c] = df_export[c].astype(int)
    csv = df_export.to_csv(index=False).encode('utf-8')
    st.download_button("Download CSV", data=csv, file_name=filename, mime="text/csv", key=key)

# Four views
view = st.radio(
    "View",
    ["By Type", "By Series (summary)", "Filter by Series (detail)", "Filter by Flags"],
    horizontal=True,
    key="inv_view",
)

# -----------------------------
# View A: By Type (no money cols)
# -----------------------------
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
        # Friendly labels
        rename = {'mint_mark': 'Mint Mark', 'coins_on_hand': 'Qty on Hand', 'series': 'Series', 'year': 'Year'}
        df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
        st.dataframe(df, use_container_width=True, hide_index=True,
                     column_config={'Qty on Hand': st.column_config.NumberColumn(format="%d")})
        _download_csv_button(df, "inventory_by_type.csv", money_cols=[], int_cols=['Qty on Hand'], key="csv_by_type")
    else:
        st.info("No inventory yet.")

# ---------------------------------
# View B: By Series (summary, money)
# ---------------------------------
elif view == "By Series (summary)":
    summary = inventory_by_series_summary()
    if summary:
        st.subheader("By Series — Summary")
        df = pd.DataFrame(summary)
        col_order = [c for c in ['series','coins','est_value_usd'] if c in df.columns]
        df = df[col_order + [c for c in df.columns if c not in col_order]]
        df = df.rename(columns={'series': 'Series', 'coins': 'Coins', 'est_value_usd': 'Est. Value (USD)'})
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                'Coins': st.column_config.NumberColumn(format="%d"),
                'Est. Value (USD)': st.column_config.NumberColumn(format="$%.2f"),
            },
        )
        _download_csv_button(df, "inventory_by_series_summary.csv", money_cols=['Est. Value (USD)'], int_cols=['Coins'], key="csv_series_summary")
    else:
        st.info("No inventory yet.")

# --------------------------------------------------
# View C: Filter by Series (detail, multiple $ cols)
# --------------------------------------------------
elif view == "Filter by Series (detail)":
    if list_series_for_filter is None or inventory_details_by_series is None:
        st.warning("Series detail helpers not found in queries.py. Please apply the inventory detail patch, then reload.")
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
                    "party": "Party",
                }
                df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

                # Column order
                order = [c for c in ["Acquired","Flip IDs","series","year","Mint Mark","variety","Party",
                                     "Qty","Unit Cost (USD)","Melt/coin (USD)","Melt×Qty (USD)","Grade"] if c in df.columns]
                df = df[[c for c in order if c in df.columns] + [c for c in df.columns if c not in order]]

                # Pretty blanks
                for c in ["variety","Flip IDs","Grade","Party","Mint Mark"]:
                    if c in df.columns:
                        df[c] = df[c].replace({"": "—", None: "—"})

                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Qty": st.column_config.NumberColumn(format="%d"),
                        "Unit Cost (USD)": st.column_config.NumberColumn(format="$%.2f"),
                        "Melt/coin (USD)": st.column_config.NumberColumn(format="$%.2f"),
                        "Melt×Qty (USD)": st.column_config.NumberColumn(format="$%.2f"),
                    },
                )
                _download_csv_button(
                    df, f"inventory_detail_{selected.replace(' ', '_')}.csv",
                    money_cols=["Unit Cost (USD)","Melt/coin (USD)","Melt×Qty (USD)"],
                    int_cols=["Qty"],
                    key="csv_series_detail",
                )

# --------------------------------------------------
# View D: Filter by Flags (Proof / Slabbed)
# --------------------------------------------------
else:
    if inventory_details_proof is None or inventory_details_slabbed is None:
        st.warning("Flag filter helpers not found in queries.py. Please append the flag filter patch, then reload.")
    else:
        try:
            choice = st.segmented_control("Show", options=["Proof coins","Slabbed (has cert #)"], default="Proof coins", key="inv_flag_choice")
        except AttributeError:
            choice = st.selectbox("Show", ["Proof coins","Slabbed (has cert #)"], index=0, key="inv_flag_choice_sel")

        rows = inventory_details_proof() if choice.startswith("Proof") else inventory_details_slabbed()
        if not rows:
            st.info("No matching coins on hand.")
        else:
            df = pd.DataFrame(rows)
            # Friendly names
            rename = {
                "acquired_date": "Acquired",
                "mint_mark": "Mint Mark",
                "qty_remaining": "Qty",
                "unit_cost_usd": "Unit Cost (USD)",
                "melt_unit_usd": "Melt/coin (USD)",
                "melt_total_usd": "Melt×Qty (USD)",
                "grade": "Grade",
                "flip_ids": "Flip IDs",
                "party": "Party",
                "slab_cert": "Cert #",
                "is_proof": "Proof",
            }
            df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

            # Order columns
            preferred = ["Acquired","Flip IDs","series","year","Mint Mark","variety","Party",
                         "Qty","Unit Cost (USD)","Melt/coin (USD)","Melt×Qty (USD)","Grade","Cert #","Proof"]
            df = df[[c for c in preferred if c in df.columns] + [c for c in df.columns if c not in preferred]]

            # Normalize blanks
            for c in ["variety","Flip IDs","Grade","Party","Mint Mark","Cert #"]:
                if c in df.columns:
                    df[c] = df[c].replace({"": "—", None: "—"})
            if "Proof" in df.columns:
                df["Proof"] = df["Proof"].map({1: "Yes", 0: "No"}).fillna("—")

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Qty": st.column_config.NumberColumn(format="%d"),
                    "Unit Cost (USD)": st.column_config.NumberColumn(format="$%.2f"),
                    "Melt/coin (USD)": st.column_config.NumberColumn(format="$%.2f"),
                    "Melt×Qty (USD)": st.column_config.NumberColumn(format="$%.2f"),
                },
            )
            _download_csv_button(
                df, f"inventory_{'proof' if choice.startswith('Proof') else 'slabbed'}.csv",
                money_cols=["Unit Cost (USD)","Melt/coin (USD)","Melt×Qty (USD)"],
                int_cols=["Qty"],
                key="csv_flags",
            )

# Optional: basic Lots section remains when on By Type view
lots = list_lots()
if lots and view == "By Type":
    st.subheader("Lots")
    dfl = pd.DataFrame(lots).rename(columns={
        "qty_remaining":"Qty",
        "unit_cost":"Unit Cost (USD)",
        "valuation_method":"Valuation",
        "manual_est_unit_value":"Manual Unit (USD)",
    })
    st.dataframe(
        dfl,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Qty": st.column_config.NumberColumn(format="%d"),
            "Unit Cost (USD)": st.column_config.NumberColumn(format="$%.2f"),
            "Manual Unit (USD)": st.column_config.NumberColumn(format="$%.2f"),
        },
    )
    _download_csv_button(dfl, "lots.csv", money_cols=["Unit Cost (USD)","Manual Unit (USD)"], int_cols=["Qty"], key="csv_lots")