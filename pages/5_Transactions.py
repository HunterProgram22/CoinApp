# pages/5_Transactions.py
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from db import get_conn
from queries import (
    create_buy_transaction, create_sell_transaction,
    list_coin_types, list_storage_locations
)

st.header("Transactions")

# ---------- helpers ----------
try:
    from streamlit.errors import StreamlitAPIException
except Exception:  # older streamlit
    class StreamlitAPIException(Exception):
        pass

def segmented_or_select(container, label, options, default=None, key=None, help=None):
    """Use segmented_control when available; fall back to selectbox/radio otherwise."""
    idx = 0
    if default in options:
        idx = options.index(default)
    try:
        seg = getattr(container, "segmented_control", None)
        if seg is not None:
            return seg(label, options=options, default=default, key=key, help=help)
    except (AttributeError, StreamlitAPIException):
        pass
    # For general selection, selectbox is more compact than radio
    return container.selectbox(label, options, index=idx, key=key, help=help)

def to_iso(d):
    return d.isoformat() if hasattr(d, "isoformat") else str(d)

def df_download(name: str, df: pd.DataFrame):
    st.download_button(
        f"Download {name} (CSV)",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=f"{name.lower().replace(' ', '_')}.csv",
        mime="text/csv"
    )

# ---------- Tabs ----------
tab_review, tab_add, tab_spend = st.tabs(["Review / Search", "Add Transaction", "Spending Log"])

# ===== Review / Search =====
with tab_review:
    col0, col1, col2, col3 = st.columns([2,2,2,2])
    preset = segmented_or_select(col0, "Quick range", ["7d","30d","90d","YTD","1y"], default="30d", key="tx_rng")
    all_time = col1.checkbox("All time", value=False, help="Ignore date range filters", key="tx_alltime")
    tx_type = col2.selectbox("Type", ["All","BUY","SELL"], index=0, key="tx_type_sel")
    party_filter = col3.text_input("Party contains", value="", key="tx_party_like")

    # compute dates
    today = date.today()
    if preset == "7d":
        start = today - timedelta(days=7)
    elif preset == "30d":
        start = today - timedelta(days=30)
    elif preset == "90d":
        start = today - timedelta(days=90)
    elif preset == "YTD":
        start = date(today.year, 1, 1)
    elif preset == "1y":
        start = today - timedelta(days=365)
    else:
        start = today - timedelta(days=30)
    end = today

    cA, cB = st.columns(2)
    d_start = cA.date_input("Start", value=start, key="tx_start")
    d_end = cB.date_input("End", value=end, key="tx_end")

    # Query
    with get_conn() as cx:
        params = []
        where = ["1=1"]
        if not all_time:
            where.append("t.tx_date BETWEEN ? AND ?")
            params += [to_iso(d_start), to_iso(d_end)]
        if tx_type != "All":
            where.append("t.tx_type = ?")
            params.append(tx_type)
        if party_filter.strip():
            where.append("COALESCE(p.name,'') LIKE ?")
            params.append(f"%{party_filter.strip()}%")

        sql = f"""
        SELECT
            t.id AS tx_id, t.tx_date, t.tx_type, COALESCE(p.name,'') AS party,
            t.currency, t.shipping, t.tax, t.fees, tl.id AS line_id,
            ct.id AS coin_type_id, cm.series, ct.year, ct.mint_mark, COALESCE(ct.variety,'') AS variety,
            tl.quantity, tl.unit_price
        FROM tx t
        LEFT JOIN party p   ON p.id = t.party_id
        LEFT JOIN tx_line tl ON tl.tx_id = t.id
        LEFT JOIN coin_type ct ON ct.id = tl.coin_type_id
        LEFT JOIN coin_master cm ON cm.id = ct.master_id
        WHERE {' AND '.join(where)}
        ORDER BY t.tx_date DESC, t.id DESC, tl.id
        """
        rows = cx.execute(sql, params).fetchall()
        df = pd.DataFrame([dict(r) for r in rows])

    if df.empty:
        st.info("No transactions matched your filters.")
    else:
        # Clean display
        disp = df.rename(columns={
            "tx_date":"Date","tx_type":"Type","party":"Party",
            "series":"Series","year":"Year","mint_mark":"Mint Mark","variety":"Variety",
            "quantity":"Qty","unit_price":"Unit Price","currency":"Currency",
            "shipping":"Shipping","tax":"Tax","fees":"Fees"
        })
        # money columns -> 2 decimals
        for col in ["Unit Price","Shipping","Tax","Fees"]:
            if col in disp.columns:
                disp[col] = pd.to_numeric(disp[col], errors="coerce").fillna(0.0).map(lambda x: f"${x:,.2f}")
        st.dataframe(disp, use_container_width=True, hide_index=True)
        df_download("transactions", disp)

# ===== Add Transaction =====
with tab_add:
    try:
        mode = segmented_or_select(st, "Transaction Type", ["BUY","SELL"], default="BUY", key="tx_mode")
    except Exception:
        mode = st.radio("Transaction Type", ["BUY","SELL"], horizontal=True, index=0)

    coin_types = list_coin_types()
    storage_opts = list_storage_locations()

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
                st.info("No coin types yet. Add some in Settings / Editor.")
                coin_type_id = None

            quantity = st.number_input("Quantity", min_value=1, step=1, value=1, key="buy_qty")
            unit_price = st.number_input("Unit Price (per coin)", min_value=0.0, step=0.01, value=0.0, key="buy_price")

            with st.expander("Grades & Valuation"):
                purchase_grade_company = st.text_input("Purchase Grade Company (PCGS/NGC/RAW)", key="buy_pgc")
                purchase_grade_text = st.text_input("Purchase Grade Text (e.g., MS64)", key="buy_pgt")
                purchase_numeric_grade = st.number_input("Purchase Numeric Grade", min_value=0.0, step=0.5, value=0.0, key="buy_png")
                slab_cert = st.text_input("Slab Cert #", key="buy_cert")

                estimated_grade_text = st.text_input("Estimated Grade (your current opinion)", key="buy_egt")
                estimated_numeric_grade = st.number_input("Estimated Numeric Grade", min_value=0.0, step=0.5, value=0.0, key="buy_eng")
                valuation_method = st.selectbox("Valuation Method", ["AUTO","MELT_ONLY","GUIDE_ONLY","MANUAL"], index=0, key="buy_valm")
                manual_est_unit_value = st.number_input("Manual Unit Value (used only if MANUAL)", min_value=0.0, step=0.01, value=0.0, key="buy_manual")

            with st.expander("Storage"):
                if storage_opts:
                    names = {f"{s['name']} ({s['category']})".strip(): s['id'] for s in storage_opts}
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
                        tx_date=to_iso(tx_date), party_name=party_name, currency=currency,
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
            coin_types = list_coin_types()
            if coin_types:
                options = {f"{ct['series']} {ct['year']}{(' ' + ct['mint_mark']) if ct['mint_mark'] else ''}{(' • ' + ct['variety']) if ct['variety'] else ''}  (#{ct['id']})": ct['id'] for ct in coin_types}
                label = st.selectbox("Coin Type", list(options.keys()), key="sell_ct")
                coin_type_id = options[label]
            else:
                st.info("No coin types yet. Add some in Settings / Editor.")
                coin_type_id = None

            quantity = st.number_input("Quantity to SELL", min_value=1, step=1, value=1, key="sell_qty")
            unit_price = st.number_input("Unit Price (per coin)", min_value=0.0, step=0.01, value=0.0, key="sell_price")

            submitted = st.form_submit_button("Save SELL (FIFO)")
            if submitted:
                if not coin_type_id:
                    st.error("Please add/select a Coin Type first.")
                else:
                    try:
                        create_sell_transaction(
                            tx_date=to_iso(tx_date), party_name=party_name, currency=currency,
                            shipping=shipping, tax=tax, fees=fees, notes=notes,
                            items=[{"coin_type_id": coin_type_id, "quantity": int(quantity), "unit_price": float(unit_price)}],
                            method='FIFO'
                        )
                        st.success("SELL saved (FIFO).")
                    except ValueError as e:
                        st.error(str(e))

# ===== Spending Log =====
with tab_spend:
    colA, colB, colC = st.columns(3)
    preset2 = segmented_or_select(colA, "Quick range", ["7d","30d","90d","YTD","1y"], default="30d", key="sp_rng")
    all_time2 = colB.checkbox("All time", value=False, key="sp_all")
    party_like = colC.text_input("Party contains", value="", key="sp_party")

    today = date.today()
    if preset2 == "7d":
        s2 = today - timedelta(days=7)
    elif preset2 == "30d":
        s2 = today - timedelta(days=30)
    elif preset2 == "90d":
        s2 = today - timedelta(days=90)
    elif preset2 == "YTD":
        s2 = date(today.year, 1, 1)
    else:
        s2 = today - timedelta(days=365)
    e2 = today

    d_s2 = colA.date_input("Start", value=s2, key="sp_start")
    d_e2 = colB.date_input("End", value=e2, key="sp_end")

    with get_conn() as cx:
        params = []
        where = ["t.tx_type = 'BUY'"]
        if not all_time2:
            where.append("t.tx_date BETWEEN ? AND ?")
            params += [to_iso(d_s2), to_iso(d_e2)]
        if party_like.strip():
            where.append("COALESCE(p.name,'') LIKE ?")
            params.append(f"%{party_like.strip()}%")

        # Summary by date+party
        sum_sql = f"""
        WITH line_tot AS (
            SELECT t.id AS tx_id,
                   SUM(ABS(COALESCE(tl.quantity,0)) * COALESCE(tl.unit_price,0)) AS line_total
            FROM tx t
            LEFT JOIN tx_line tl ON tl.tx_id = t.id
            WHERE {' AND '.join(where)}
            GROUP BY t.id
        )
        SELECT t.tx_date, COALESCE(p.name,'') AS party,
               ROUND(COALESCE(line_tot.line_total,0) + COALESCE(t.shipping,0) + COALESCE(t.tax,0) + COALESCE(t.fees,0), 2) AS total_spent
        FROM tx t
        LEFT JOIN party p ON p.id = t.party_id
        LEFT JOIN line_tot ON line_tot.tx_id = t.id
        WHERE {' AND '.join(where)}
        ORDER BY t.tx_date DESC, party
        """
        rows = cx.execute(sum_sql, params*2 if not all_time2 or party_like.strip() else []).fetchall()
        df_sum = pd.DataFrame([dict(r) for r in rows])

        # Line breakdown (counts by series per date+party)
        det_sql = f"""
        SELECT t.tx_date, COALESCE(p.name,'') AS party, cm.series, SUM(ABS(COALESCE(tl.quantity,0))) AS qty
        FROM tx t
        LEFT JOIN party p ON p.id = t.party_id
        LEFT JOIN tx_line tl ON tl.tx_id = t.id
        LEFT JOIN coin_type ct ON ct.id = tl.coin_type_id
        LEFT JOIN coin_master cm ON cm.id = ct.master_id
        WHERE {' AND '.join(where)}
        GROUP BY t.tx_date, party, cm.series
        ORDER BY t.tx_date DESC, party, cm.series
        """
        rows2 = cx.execute(det_sql, params).fetchall()
        df_det = pd.DataFrame([dict(r) for r in rows2])

    if df_sum.empty:
        st.info("No BUY spending found for the selected period.")
    else:
        # Roll up same-date+party rows (in case multiple BUY tx that day)
        grp = df_sum.groupby(["tx_date","party"], as_index=False)["total_spent"].sum()
        # Build a descriptor like "(1 Morgan, 1 Peace)"
        if not df_det.empty:
            parts = (
                df_det.groupby(["tx_date","party","series"], as_index=False)["qty"].sum()
                     .sort_values(["tx_date","party","series"])
            )
            desc_map = {}
            for (d, p), sub in parts.groupby(["tx_date","party"]):
                chunk = ", ".join([f"{int(r.qty)} {r.series}" for _, r in sub.iterrows()])
                desc_map[(d,p)] = f"({chunk})"
            grp["what"] = grp.apply(lambda r: desc_map.get((r["tx_date"], r["party"]), ""), axis=1)
        else:
            grp["what"] = ""
        grp = grp.rename(columns={"tx_date":"Date","party":"Party","total_spent":"Total Spent (USD)"})
        grp["Total Spent (USD)"] = grp["Total Spent (USD)"].map(lambda x: f"${x:,.2f}")
        st.dataframe(grp, use_container_width=True, hide_index=True)
        df_download("spending_log", grp)