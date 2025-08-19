# pages/2_Add_Transaction.py
import streamlit as st
from queries import (
    list_coin_types, list_storage_locations,
    create_buy_transaction, create_sell_transaction,
)

st.header("Add Transaction")
# Fallback if Streamlit version doesn't support segmented_control
try:
    mode = st.segmented_control("Transaction Type", options=["BUY","SELL"], default="BUY")
except AttributeError:
    mode = st.radio("Transaction Type", ["BUY","SELL"], index=0, horizontal=True)

coin_types = list_coin_types()
if not coin_types:
    st.warning("Add at least one Coin Type in Settings → Coin Types.")

storage_options = list_storage_locations()

if mode == "BUY":
    with st.form("buy_form", clear_on_submit=False):
        colA, colB, colC = st.columns(3)
        tx_date = colA.date_input("Date")
        party_name = colB.text_input("Counterparty (Dealer/Person)")
        currency = colC.text_input("Currency", value="USD")
        shipping = colA.number_input("Shipping", min_value=0.0, step=0.01, value=0.0)
        tax = colB.number_input("Tax", min_value=0.0, step=0.01, value=0.0)
        fees = colC.number_input("Fees", min_value=0.0, step=0.01, value=0.0)
        notes = st.text_area("Notes", height=70)

        st.subheader("Line Item")
        if coin_types:
            options = {f"{ct['series']} {ct['year']}{(' ' + ct['mint_mark']) if ct['mint_mark'] else ''}{(' • ' + ct['variety']) if ct['variety'] else ''}  (#{ct['id']})": ct['id'] for ct in coin_types}
            label = st.selectbox("Coin Type", list(options.keys()))
            coin_type_id = options[label]
        else:
            coin_type_id = None

        quantity = st.number_input("Quantity", min_value=1, step=1, value=1)
        unit_price = st.number_input("Unit Price (per coin)", min_value=0.0, step=0.01, value=0.0)

        with st.expander("Grades & Valuation"):
            purchase_grade_company = st.text_input("Purchase Grade Company (PCGS/NGC/RAW)")
            purchase_grade_text = st.text_input("Purchase Grade Text (e.g., MS64)")
            purchase_numeric_grade = st.number_input("Purchase Numeric Grade", min_value=0.0, step=0.5, value=0.0)
            slab_cert = st.text_input("Slab Cert #")

            estimated_grade_text = st.text_input("Estimated Grade (your current opinion)")
            estimated_numeric_grade = st.number_input("Estimated Numeric Grade", min_value=0.0, step=0.5, value=0.0)
            valuation_method = st.selectbox("Valuation Method", ["AUTO","MELT_ONLY","GUIDE_ONLY","MANUAL"], index=0)
            manual_est_unit_value = st.number_input("Manual Unit Value (used only if MANUAL)", min_value=0.0, step=0.01, value=0.0)

        with st.expander("Storage"):
            if storage_options:
                names = {f"{s['name']} ({s['category']})".strip(): s['id'] for s in storage_options}
                storage_label = st.selectbox("Storage Location", list(names.keys()))
                storage_location_id = names[storage_label]
            else:
                st.info("No storage locations yet. Add some in Settings.")
                storage_location_id = None
            lot_notes = st.text_input("Lot Notes")

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
        tx_date = colA.date_input("Date")
        party_name = colB.text_input("Counterparty (Buyer)")
        currency = colC.text_input("Currency", value="USD")
        shipping = colA.number_input("Shipping", min_value=0.0, step=0.01, value=0.0)
        tax = colB.number_input("Tax", min_value=0.0, step=0.01, value=0.0)
        fees = colC.number_input("Fees", min_value=0.0, step=0.01, value=0.0)
        notes = st.text_area("Notes", height=70)

        st.subheader("Line Item")
        if coin_types:
            options = {f"{ct['series']} {ct['year']}{(' ' + ct['mint_mark']) if ct['mint_mark'] else ''}{(' • ' + ct['variety']) if ct['variety'] else ''}  (#{ct['id']})": ct['id'] for ct in coin_types}
            label = st.selectbox("Coin Type", list(options.keys()))
            coin_type_id = options[label]
        else:
            coin_type_id = None

        quantity = st.number_input("Quantity to SELL", min_value=1, step=1, value=1)
        unit_price = st.number_input("Unit Price (per coin)", min_value=0.0, step=0.01, value=0.0)

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
