# pages/5_Transactions.py
import streamlit as st
import pandas as pd
from datetime import date, timedelta

from queries import (
    # existing helpers
    list_coin_types, list_storage_locations,
    create_buy_transaction, create_sell_transaction,
)

# Optional helpers (patched in)
try:
    from queries import search_transactions, get_tx_lines
except Exception:
    search_transactions = None
    get_tx_lines = None

try:
    from queries import spending_log, spending_log_items
except Exception:
    spending_log = None
    spending_log_items = None

st.header("Transactions")

tab_list, tab_add, tab_spend = st.tabs(["📄 Review / Search", "➕ Add Transaction", "💵 Spending Log"])

# =====================================================
# TAB 1: REVIEW / SEARCH
# =====================================================
with tab_list:
    if search_transactions is None or get_tx_lines is None:
        st.warning("Search helpers not found in queries.py. Please apply the provided patch, then reload.")
    else:
        # --- Quick presets ---
        col0, col1, col2, col3 = st.columns([2,2,2,2])
        try:
            preset = col0.segmented_control("Quick range", options=["7d","30d","90d","365d"], default="30d", key="tx_preset")
        except AttributeError:
            preset = col0.selectbox("Quick range", ["7d","30d","90d","365d"], index=1, key="tx_preset_sel")
        all_time = col1.checkbox("All time", value=False, help="Ignore date filters and show everything (paginated)", key="tx_all_time")
        types_default = ["BUY","SELL"]
        tx_types = col2.multiselect("Types", ["BUY","SELL","FEE","ADJUST","GIFT_IN","GIFT_OUT","TRANSFER"], default=types_default, key="tx_types")
        party_q = col3.text_input("Party contains", value="", key="tx_party")

        # Compute default dates from preset
        today = date.today()
        days_map = {"7d":7, "30d":30, "90d":90, "365d":365}
        default_days = days_map.get(preset, 30)
        d_from_default = today - timedelta(days=default_days)
        d_to_default = today

        # Manual overrides (give unique keys)
        colA, colB, colC = st.columns([1.2,1.2,1])
        d_from = colA.date_input("From", value=d_from_default, disabled=all_time, key="tx_from")
        d_to   = colB.date_input("To", value=d_to_default, disabled=all_time, key="tx_to")
        page_size = colC.selectbox("Results", [25, 50, 100], index=0, key="tx_page_size")

        colD, colE, _ = st.columns([1,1,3])
        do_search = colD.button("Search", type="primary")
        if colE.button("Clear filters"):
            # reset to defaults
            st.session_state["tx_from"] = d_from_default
            st.session_state["tx_to"] = d_to_default
            st.session_state["tx_types"] = types_default
            st.session_state["tx_party"] = ""
            st.session_state["tx_all_time"] = False
            try:
                st.rerun()
            except Exception:
                pass

        # simple pagination via session state
        if "tx_offset" not in st.session_state:
            st.session_state.tx_offset = 0

        # reset offset on new search
        if do_search:
            st.session_state.tx_offset = 0

        # Build args
        date_from = None if all_time else (d_from.isoformat() if d_from else None)
        date_to   = None if all_time else (d_to.isoformat() if d_to else None)

        # Fetch rows
        rows = []
        try:
            rows = search_transactions(
                date_from=date_from,
                date_to=date_to,
                tx_types=tx_types or None,
                party_query=party_q.strip() or None,
                limit=int(page_size),
                offset=int(st.session_state.tx_offset),
            )
        except Exception as e:
            st.error(f"Search failed: {e}")
            rows = []

        if not rows:
            if not all_time:
                st.info("No transactions found. Try enabling 'All time' or widening the date range.")
            else:
                st.info("No transactions found.")
        else:
            df = pd.DataFrame(rows)
            # friendly labels
            if "party" in df.columns:
                df["party"] = df["party"].fillna("—")
            rename = {
                "id": "Tx #",
                "tx_date": "Date",
                "tx_type": "Type",
                "party": "Party",
                "currency": "CCY",
                "shipping": "Ship",
                "tax": "Tax",
                "fees": "Fees",
                "notes": "Notes",
            }
            st.dataframe(df.rename(columns=rename), use_container_width=True, hide_index=True)

            st.caption("Expand any transaction to see its line items and quick totals.")

            # Expandable details
            for row in rows:
                with st.expander(f"#{row['id']} • {row['tx_date']} • {row['tx_type']} • {row.get('party') or '—'}"):
                    try:
                        lines = get_tx_lines(row["id"])
                    except Exception as e:
                        st.error(f"Failed to fetch lines: {e}")
                        lines = []
                    if not lines:
                        st.info("No lines found.")
                    else:
                        dfl = pd.DataFrame(lines)
                        # friendly names
                        dfl = dfl.rename(columns={
                            "series": "Series",
                            "year": "Year",
                            "mint_mark": "Mint Mark",
                            "variety": "Variety",
                            "quantity": "Qty",
                            "unit_price": "Unit Price",
                            "grade_company": "Grade Co.",
                            "grade_text": "Grade Text",
                        })
                        st.dataframe(dfl, use_container_width=True, hide_index=True)

                        # Quick totals for BUY/SELL
                        try:
                            qty_sum = int(pd.to_numeric(dfl.get("Qty"), errors="coerce").fillna(0).sum())
                            subtotal = float(pd.to_numeric(dfl.get("Unit Price"), errors="coerce").fillna(0).mul(pd.to_numeric(dfl.get("Qty"), errors="coerce").fillna(0)).sum())
                            st.caption(f"Lines: {len(dfl)} • Qty total: {qty_sum} • Subtotal (Qty × Unit): ${subtotal:,.2f}")
                        except Exception:
                            pass

            # Pager controls
            colP1, colP2, _ = st.columns([1,1,6])
            if colP1.button("⬅️ Prev", disabled=st.session_state.tx_offset <= 0):
                st.session_state.tx_offset = max(0, st.session_state.tx_offset - int(page_size))
                try:
                    st.rerun()
                except Exception:
                    pass
            if colP2.button("Next ➡️", disabled=len(rows) < int(page_size)):
                st.session_state.tx_offset += int(page_size)
                try:
                    st.rerun()
                except Exception:
                    pass

# =====================================================
# TAB 2: ADD TRANSACTION (same form you already use)
# =====================================================
with tab_add:
    # Fallback if Streamlit version doesn't support segmented_control
    try:
        mode = st.segmented_control("Transaction Type", options=["BUY","SELL"], default="BUY", key="tx_mode")
    except AttributeError:
        mode = st.radio("Transaction Type", ["BUY","SELL"], index=0, horizontal=True, key="tx_mode_radio")

    coin_types = list_coin_types()
    if not coin_types:
        st.warning("Add at least one Coin Type in Settings → Coin Types.")

    storage_options = list_storage_locations()

    if mode == "BUY":
        with st.form("buy_form", clear_on_submit=False):
            colA, colB, colC = st.columns(3)
            tx_date = colA.date_input("Date", key="buy_date")
            party_name = colB.text_input("Counterparty (Dealer/Person)", key="buy_party")
            currency = colC.text_input("Currency", value="USD", key="buy_ccy")
            shipping = colA.number_input("Shipping", min_value=0.0, step=0.01, value=0.0, key="buy_ship")
            tax = colB.number_input("Tax", min_value=0.0, step=0.01, value=0.0, key="buy_tax")
            fees = colC.number_input("Fees", min_value=0.0, step=0.01, value=0.0, key="buy_fees")
            notes = st.text_area("Notes", height=70, key="buy_notes")

            st.subheader("Line Item")
            if coin_types:
                options = {f"{ct['series']} {ct['year']}{(' ' + ct['mint_mark']) if ct['mint_mark'] else ''}{(' • ' + ct['variety']) if ct['variety'] else ''}  (#{ct['id']})": ct['id'] for ct in coin_types}
                label = st.selectbox("Coin Type", list(options.keys()), key="buy_ct")
                coin_type_id = options[label]
            else:
                coin_type_id = None

            quantity = st.number_input("Quantity", min_value=1, step=1, value=1, key="buy_qty")
            unit_price = st.number_input("Unit Price (per coin)", min_value=0.0, step=0.01, value=0.0, key="buy_unit_price")

            with st.expander("Grades & Valuation"):
                purchase_grade_company = st.text_input("Purchase Grade Company (PCGS/NGC/RAW)", key="buy_pgc")
                purchase_grade_text = st.text_input("Purchase Grade Text (e.g., MS64)", key="buy_pgt")
                purchase_numeric_grade = st.number_input("Purchase Numeric Grade", min_value=0.0, step=0.5, value=0.0, key="buy_png")
                slab_cert = st.text_input("Slab Cert #", key="buy_slab")

                estimated_grade_text = st.text_input("Estimated Grade (your current opinion)", key="buy_egt")
                estimated_numeric_grade = st.number_input("Estimated Numeric Grade", min_value=0.0, step=0.5, value=0.0, key="buy_eng")
                valuation_method = st.selectbox("Valuation Method", ["AUTO","MELT_ONLY","GUIDE_ONLY","MANUAL"], index=0, key="buy_val_method")
                manual_est_unit_value = st.number_input("Manual Unit Value (used only if MANUAL)", min_value=0.0, step=0.01, value=0.0, key="buy_manual_val")

            with st.expander("Storage"):
                if storage_options:
                    names = {f"{s['name']} ({s['category']})".strip(): s['id'] for s in storage_options}
                    storage_label = st.selectbox("Storage Location", list(names.keys()), key="buy_storage")
                    storage_location_id = names[storage_label]
                else:
                    st.info("No storage locations yet. Add some in Settings.")
                    storage_location_id = None
                lot_notes = st.text_input("Lot Notes", key="buy_lot_notes")

            submitted = st.form_submit_button("Save BUY")
            if submitted:
                if not coin_type_id:
                    st.error("Please add/select a Coin Type first.")
                else:
                    create_buy_transaction(
                        tx_date=tx_date.isoformat(), party_name=party_name, currency=currency,
                        shipping=shipping, tax=tax, fees=fees, notes=notes,
                        items=[{
                            "coin_type_id": coin_type_id,
                            "quantity": int(quantity),
                            "unit_price": float(unit_price),
                            "purchase_grade_company": purchase_grade_company or None,
                            "purchase_grade_text": purchase_grade_text or None,
                            "purchase_numeric_grade": float(purchase_numeric_grade or 0) or None,
                            "slab_cert": slab_cert or None,
                            "estimated_grade_text": estimated_grade_text or None,
                            "estimated_numeric_grade": float(estimated_numeric_grade or 0) or None,
                            "valuation_method": valuation_method,
                            "manual_est_unit_value": float(manual_est_unit_value or 0) or None,
                            "storage_location_id": storage_location_id,
                            "lot_notes": lot_notes or None,
                        }]
                    )
                    st.success("BUY saved.")

    else:  # SELL
        with st.form("sell_form", clear_on_submit=False):
            colA, colB, colC = st.columns(3)
            tx_date = colA.date_input("Date", key="sell_date")
            party_name = colB.text_input("Counterparty (Buyer)", key="sell_party")
            currency = colC.text_input("Currency", value="USD", key="sell_ccy")
            shipping = colA.number_input("Shipping", min_value=0.0, step=0.01, value=0.0, key="sell_ship")
            tax = colB.number_input("Tax", min_value=0.0, step=0.01, value=0.0, key="sell_tax")
            fees = colC.number_input("Fees", min_value=0.0, step=0.01, value=0.0, key="sell_fees")
            notes = st.text_area("Notes", height=70, key="sell_notes")

            st.subheader("Line Item")
            if coin_types:
                options = {f"{ct['series']} {ct['year']}{(' ' + ct['mint_mark']) if ct['mint_mark'] else ''}{(' • ' + ct['variety']) if ct['variety'] else ''}  (#{ct['id']})": ct['id'] for ct in coin_types}
                label = st.selectbox("Coin Type", list(options.keys()), key="sell_ct")
                coin_type_id = options[label]
            else:
                coin_type_id = None

            quantity = st.number_input("Quantity to SELL", min_value=1, step=1, value=1, key="sell_qty")
            unit_price = st.number_input("Unit Price (per coin)", min_value=0.0, step=0.01, value=0.0, key="sell_unit_price")

            submitted = st.form_submit_button("Save SELL (FIFO)")
            if submitted:
                if not coin_type_id:
                    st.error("Please add/select a Coin Type first.")
                else:
                    try:
                        create_sell_transaction(
                            tx_date=tx_date.isoformat(), party_name=party_name, currency=currency,
                            shipping=shipping, tax=tax, fees=fees, notes=notes,
                            items=[{"coin_type_id": coin_type_id, "quantity": int(quantity), "unit_price": float(unit_price)}],
                            method='FIFO'
                        )
                        st.success("SELL saved (FIFO).")
                    except ValueError as e:
                        st.error(str(e))

# =====================================================
# TAB 3: SPENDING LOG (grouped by Date + Party, BUY only)
# =====================================================
with tab_spend:
    if spending_log is None or spending_log_items is None:
        st.warning("Spending helpers not found in queries.py. Please apply the provided patch, then reload.")
    else:
        today = date.today()
        colA, colB, colC, colD = st.columns([1.2,1.2,1,1])
        d_from = colA.date_input("From", value=today - timedelta(days=90), key="sp_from")
        d_to   = colB.date_input("To", value=today, key="sp_to")
        party_q = colC.text_input("Party contains", value="", key="sp_party")
        page_size = colD.selectbox("Results", [25, 50, 100], index=0, key="sp_page_size")

        # pagination
        if "spend_offset" not in st.session_state:
            st.session_state.spend_offset = 0
        colE, colF, colG = st.columns([1,1,6])
        if colE.button("Search", type="primary", key="sp_search"):
            st.session_state.spend_offset = 0
        if colF.button("All time", key="sp_alltime"):
            d_from = None
            d_to = None
            st.session_state.spend_offset = 0

        rows = []
        try:
            rows = spending_log(
                date_from=d_from.isoformat() if d_from else None,
                date_to=d_to.isoformat() if d_to else None,
                party_query=party_q.strip() or None,
                limit=int(page_size),
                offset=int(st.session_state.spend_offset),
            )
        except Exception as e:
            st.error(f"Spending query failed: {e}")
            rows = []

        if not rows:
            st.info("No spending found for the current filters.")
        else:
            # Build a friendly table
            friendly = []
            for r in rows:
                # Items summary
                try:
                    items = spending_log_items(r["tx_date"], r.get("party"))
                except Exception as e:
                    items = []
                if items:
                    parts = []
                    for it in items:
                        qty = int(it.get("qty", 0) or 0)
                        series = it.get("series") or ""
                        parts.append(f"{qty} {series}")
                    items_str = ", ".join(parts)
                else:
                    items_str = "—"

                friendly.append({
                    "Date": r["tx_date"],
                    "Party": r.get("party") or "—",
                    "Total Spent (USD)": f"${float(r.get('spent_usd') or 0):,.2f}",
                    "What was bought": items_str,
                })

            st.dataframe(pd.DataFrame(friendly), use_container_width=True, hide_index=True)

            # Pager controls
            colP1, colP2, _ = st.columns([1,1,6])
            if colP1.button("⬅️ Prev", disabled=st.session_state.spend_offset <= 0, key="sp_prev"):
                st.session_state.spend_offset = max(0, st.session_state.spend_offset - int(page_size))
                try:
                    st.rerun()
                except Exception:
                    pass
            if colP2.button("Next ➡️", disabled=len(rows) < int(page_size), key="sp_next"):
                st.session_state.spend_offset += int(page_size)
                try:
                    st.rerun()
                except Exception:
                    pass