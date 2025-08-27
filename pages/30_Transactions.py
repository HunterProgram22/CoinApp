
# pages/30_Transactions.py
import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime
from db import get_conn
from queries import (
    list_coin_types, list_storage_locations,
    create_buy_transaction, create_sell_transaction,
)

st.header("Transactions")

# --------------------------
# Helpers
# --------------------------
def _friendly_money(val, places=2):
    try:
        return f"${float(val):,.{places}f}"
    except Exception:
        return val

def _party_list():
    with get_conn() as cx:
        rows = cx.execute("""
            SELECT DISTINCT COALESCE(p.name,'') AS party
            FROM tx t LEFT JOIN party p ON p.id = t.party_id
            WHERE COALESCE(p.name,'') <> ''
            ORDER BY party
        """).fetchall()
    return [r[0] for r in rows]

def _fetch_tx(start_dt=None, end_dt=None, kinds=("BUY","SELL"), party=None, search=None):
    where = []
    params = []
    if start_dt and end_dt:
        where.append("DATE(t.tx_date) BETWEEN DATE(?) AND DATE(?)")
        params += [start_dt, end_dt]
    if kinds and len(kinds) < 2:
        where.append("t.tx_type = ?")
        params.append(kinds[0])
    if party:
        where.append("COALESCE(p.name,'') = ?")
        params.append(party)
    if search:
        s = f"%{search.strip()}%"
        where.append("(cm.series LIKE ? OR ct.variety LIKE ? OR COALESCE(p.name,'') LIKE ? OR COALESCE(t.notes,'') LIKE ?)")
        params += [s, s, s, s]

    clause = ("WHERE " + " AND ".join(where)) if where else ""
    with get_conn() as cx:
        rows = cx.execute(f"""
            SELECT
              t.id AS tx_id, t.tx_date, t.tx_type,
              COALESCE(p.name,'') AS party,
              cm.series, ct.year, ct.mint_mark, COALESCE(ct.variety,'') AS variety,
              tl.quantity, tl.unit_price,
              t.currency, t.shipping, t.tax, t.fees, COALESCE(t.notes,'') AS tx_notes
            FROM tx t
            JOIN tx_line tl     ON tl.tx_id = t.id
            LEFT JOIN party p   ON p.id = t.party_id
            LEFT JOIN coin_type ct ON ct.id = tl.coin_type_id
            LEFT JOIN coin_master cm ON cm.id = ct.master_id
            {clause}
            ORDER BY DATE(t.tx_date) DESC, t.id DESC, tl.id ASC
        """, params).fetchall()
    df = pd.DataFrame([dict(r) for r in rows])
    return df

def _calc_preset_range(preset: str):
    today = date.today()
    if preset == "7d":
        return (today - timedelta(days=7), today)
    if preset == "30d":
        return (today - timedelta(days=30), today)
    if preset == "90d":
        return (today - timedelta(days=90), today)
    if preset == "YTD":
        start = date(today.year, 1, 1)
        return (start, today)
    if preset == "1y":
        return (today - timedelta(days=365), today)
    return (today - timedelta(days=30), today)

def _download_button(label: str, df: pd.DataFrame, filename: str):
    st.download_button(label, df.to_csv(index=False).encode("utf-8"), file_name=filename, mime="text/csv")

# --------------------------
# Tabs
# --------------------------
tab_review, tab_add, tab_spend = st.tabs(["Review / Search", "Add Transaction", "Spending Log"])

# =============================================
# Review / Search
# =============================================
with tab_review:
    col0, col1, col2, col3 = st.columns([2,2,2,2])
    preset = col0.selectbox("Quick range", ["30d","7d","90d","YTD","1y","All"], index=0, key="tx_preset")
    if preset == "All":
        start_dt, end_dt = None, None
        all_time = True
    else:
        start_dt, end_dt = _calc_preset_range(preset)
        all_time = False

    # Ensure unique keys for date inputs
    start_dt = col1.date_input("Start", value=start_dt or date.today() - timedelta(days=365*5), key="tx_rev_start")
    end_dt   = col2.date_input("End",   value=end_dt or date.today(), key="tx_rev_end")

    kinds = col3.multiselect("Type", ["BUY","SELL"], default=["BUY","SELL"], key="tx_rev_kinds")

    c4, c5, c6 = st.columns([2,2,3])
    parties = _party_list()
    party = c4.selectbox("Party (optional)", ["(any)"] + parties, index=0, key="tx_rev_party")
    party = None if party == "(any)" else party

    search = c5.text_input("Search text (series/variety/party/notes)", key="tx_rev_search")

    run = c6.button("Run Search", type="primary", key="tx_rev_run")

    if run:
        df = _fetch_tx(None if all_time else start_dt, None if all_time else end_dt, tuple(kinds) if kinds else None, party, search)
        if df.empty:
            st.info("No transactions matched your filters.")
        else:
            # Display
            show = df.copy()
            show.rename(columns={
                "tx_date": "Date",
                "tx_type": "Type",
                "party": "Party",
                "series": "Series",
                "year": "Year",
                "mint_mark": "Mint Mark",
                "variety": "Variety",
                "quantity": "Qty",
                "unit_price": "Unit Price (USD)",
                "currency": "Currency",
                "shipping": "Shipping",
                "tax": "Tax",
                "fees": "Fees",
                "tx_notes": "Notes",
            }, inplace=True)
            # Money columns to 2dp
            for c in ["Unit Price (USD)","Shipping","Tax","Fees"]:
                if c in show.columns:
                    show[c] = pd.to_numeric(show[c], errors="coerce").fillna(0.0).map(lambda x: f"${x:,.2f}")
            # Year to 4-digit string
            if "Year" in show.columns:
                show["Year"] = pd.to_numeric(show["Year"], errors="coerce").map(lambda x: "" if pd.isna(x) else f"{int(x)}")
            st.dataframe(show, use_container_width=True, hide_index=True)

            # CSV
            _download_button("Download CSV (Transactions)", df, "transactions.csv")

# =============================================
# Add Transaction
# =============================================
with tab_add:
    try:
        tx_mode = st.segmented_control("Transaction Type", options=["BUY","SELL"], default="BUY", key="tx_mode")
    except AttributeError:
        tx_mode = st.radio("Transaction Type", ["BUY","SELL"], index=0, horizontal=True, key="tx_mode")

    coin_types = list_coin_types()
    storage_options = list_storage_locations()

    def ct_label(ct):
        mm  = f" {ct['mint_mark']}" if ct.get('mint_mark') else ""
        var = f" • {ct['variety']}" if ct.get('variety') else ""
        return f"{ct['series']} {ct['year']}{mm}{var}"

    if tx_mode == "BUY":
        with st.form("buy_form", clear_on_submit=False):
            colA, colB, colC = st.columns(3)
            tx_date = colA.date_input("Date", value=date.today(), key="buy_date")
            party_name = colB.text_input("Counterparty (Dealer/Person)", key="buy_party")
            currency = colC.text_input("Currency", value="USD", key="buy_ccy")
            shipping = colA.number_input("Shipping", min_value=0.0, step=0.01, value=0.0, key="buy_ship")
            tax = colB.number_input("Tax", min_value=0.0, step=0.01, value=0.0, key="buy_tax")
            fees = colC.number_input("Fees", min_value=0.0, step=0.01, value=0.0, key="buy_fees")
            notes = st.text_area("Notes", height=70, key="buy_notes")

            st.subheader("Line Item")
            if coin_types:
                selection = st.selectbox("Coin Type", coin_types, format_func=ct_label, key="buy_ct")
                coin_type_id = selection["id"] if selection else None
            else:
                st.warning("Add at least one Coin Type in Admin → Coin Types.")
                coin_type_id = None

            quantity = st.number_input("Quantity", min_value=1, step=1, value=1, key="buy_qty")
            unit_price = st.number_input("Unit Price (per coin)", min_value=0.0, step=0.01, value=0.0, key="buy_unit")

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
                if storage_options:
                    def stg_label(s): return f"{s['name']}" + (f" ({s['category']})" if s.get('category') else "")
                    stg = st.selectbox("Storage Location", storage_options, format_func=stg_label, key="buy_storage")
                    storage_location_id = stg["id"] if stg else None
                else:
                    st.info("No storage locations yet. Add some in Admin → Storage.")
                    storage_location_id = None
                lot_notes = st.text_input("Lot Notes", key="buy_lot_notes")

            submitted = st.form_submit_button("Save BUY", type="primary", use_container_width=False)
            if submitted:
                if not coin_type_id:
                    st.error("Please add/select a Coin Type first.")
                else:
                    create_buy_transaction(
                        tx_date=tx_date.isoformat(), party_name=party_name, currency=currency,
                        shipping=shipping, tax=tax, fees=fees, notes=notes,
                        items=[{
                            "coin_type_id": int(coin_type_id),
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
                    try:
                        st.rerun()
                    except Exception:
                        pass

    else:  # SELL
        with st.form("sell_form", clear_on_submit=False):
            colA, colB, colC = st.columns(3)
            tx_date = colA.date_input("Date", value=date.today(), key="sell_date")
            party_name = colB.text_input("Counterparty (Buyer)", key="sell_party")
            currency = colC.text_input("Currency", value="USD", key="sell_ccy")
            shipping = colA.number_input("Shipping", min_value=0.0, step=0.01, value=0.0, key="sell_ship")
            tax = colB.number_input("Tax", min_value=0.0, step=0.01, value=0.0, key="sell_tax")
            fees = colC.number_input("Fees", min_value=0.0, step=0.01, value=0.0, key="sell_fees")
            notes = st.text_area("Notes", height=70, key="sell_notes")

            st.subheader("Line Item")
            if coin_types:
                selection = st.selectbox("Coin Type", coin_types, format_func=ct_label, key="sell_ct")
                coin_type_id = selection["id"] if selection else None
            else:
                st.warning("Add at least one Coin Type in Admin → Coin Types.")
                coin_type_id = None

            quantity = st.number_input("Quantity to SELL", min_value=1, step=1, value=1, key="sell_qty")
            unit_price = st.number_input("Unit Price (per coin)", min_value=0.0, step=0.01, value=0.0, key="sell_unit")

            submitted = st.form_submit_button("Save SELL (FIFO)", type="primary")
            if submitted:
                if not coin_type_id:
                    st.error("Please add/select a Coin Type first.")
                else:
                    try:
                        create_sell_transaction(
                            tx_date=tx_date.isoformat(), party_name=party_name, currency=currency,
                            shipping=shipping, tax=tax, fees=fees, notes=notes,
                            items=[{"coin_type_id": int(coin_type_id), "quantity": int(quantity), "unit_price": float(unit_price)}],
                            method='FIFO'
                        )
                        st.success("SELL saved (FIFO).")
                        try:
                            st.rerun()
                        except Exception:
                            pass
                    except ValueError as e:
                        st.error(str(e))

# =============================================
# Spending Log (BUYs only)
# =============================================
with tab_spend:
    col0, col1, col2 = st.columns([2,2,2])
    sp_preset = col0.selectbox("Quick range", ["30d","7d","90d","YTD","1y","All"], index=0, key="sp_preset")
    if sp_preset == "All":
        sp_start, sp_end = None, None
        sp_all = True
    else:
        sp_start, sp_end = _calc_preset_range(sp_preset)
        sp_all = False
    sp_start = col1.date_input("Start", value=sp_start or (date.today() - timedelta(days=365)), key="sp_start")
    sp_end   = col2.date_input("End",   value=sp_end or date.today(), key="sp_end")

    run_sp = st.button("Run Spending Log", type="primary", key="sp_run")

    if run_sp:
        df = _fetch_tx(None if sp_all else sp_start, None if sp_all else sp_end, kinds=("BUY",), party=None, search=None)
        if df.empty:
            st.info("No BUY transactions in that range.")
        else:
            # Total per tx (line-level)
            df["line_total"] = pd.to_numeric(df["unit_price"], errors="coerce").fillna(0.0) * pd.to_numeric(df["quantity"], errors="coerce").fillna(0.0)
            # Group by Date + Party
            df["Date"] = pd.to_datetime(df["tx_date"]).dt.date
            df["Series"] = df["series"].fillna("")
            agg = df.groupby(["Date","party"], dropna=False).agg(
                Total_Spent_USD=("line_total", "sum"),
                Items=("Series", lambda s: ", ".join(f"{n}×{k}" for k, n in s.value_counts().items())),
                Lines=("series", "count")
            ).reset_index().rename(columns={"party":"Party"})
            # Display
            show = agg.copy()
            show["Total_Spent_USD"] = show["Total_Spent_USD"].map(lambda x: f"${x:,.2f}")
            show = show.sort_values(["Date","Party"], ascending=[False,True])
            st.dataframe(show, use_container_width=True, hide_index=True)
            _download_button("Download CSV (Spending Log)", agg, "spending_log.csv")
