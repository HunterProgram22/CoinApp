# pages/6_Settings.py
import streamlit as st
from queries import (
    upsert_coin_master, upsert_coin_type, upsert_storage, upsert_party, list_coin_types
)

st.header("Settings")

with st.expander("Coin Master (country/denomination/series)", expanded=True):
    with st.form("master_form"):
        country = st.text_input("Country", value="USA")
        denom = st.text_input("Denomination", value="Half Dollar")
        series = st.text_input("Series", value="Kennedy")
        metal = st.text_input("Metal (Ag/Au/CuNi)", value="Ag")
        fineness = st.number_input("Fineness", min_value=0.0, step=0.001, value=0.9)
        weight_grams = st.number_input("Weight (g)", min_value=0.0, step=0.001, value=12.5)
        diameter_mm = st.number_input("Diameter (mm)", min_value=0.0, step=0.01, value=30.6)
        thickness_mm = st.number_input("Thickness (mm)", min_value=0.0, step=0.01, value=0.0)
        edge = st.text_input("Edge", value="Reeded")
        years_start = st.number_input("First Year", min_value=0, step=1, value=1964)
        years_end = st.number_input("Last Year (0 = ongoing)", min_value=0, step=1, value=0)
        notes = st.text_area("Notes", height=70)
        if st.form_submit_button("Add/Find Master"):
            master_id = upsert_coin_master(country, denom, series, metal, fineness, weight_grams,
                                           diameter_mm, thickness_mm, edge,
                                           years_start if years_end else years_start,
                                           years_end if years_end else None, notes)
            st.success(f"Master ID: {master_id}")

with st.expander("Coin Types (year/mint/variety)", expanded=True):
    with st.form("type_form"):
        st.caption("Ensure the master exists above before adding types.")
        master_id = st.number_input("Master ID", min_value=1, step=1)
        year = st.number_input("Year", min_value=0, step=1, value=1964)
        mint_mark = st.text_input("Mint Mark (P/D/S/W)")
        variety = st.text_input("Variety (optional)")
        mintage = st.number_input("Mintage (optional)", min_value=0, step=1, value=0)
        is_proof = st.selectbox("Proof?", options=[0,1], index=0)
        designer = st.text_input("Designer (optional)")
        obv_desc = st.text_input("Obv Desc (optional)")
        rev_desc = st.text_input("Rev Desc (optional)")
        if st.form_submit_button("Add/Find Type"):
            type_id = upsert_coin_type(int(master_id), int(year), mint_mark or None, variety or None,
                                       int(mintage) if mintage else None, int(is_proof), designer or None,
                                       obv_desc or None, rev_desc or None)
            st.success(f"Type ID: {type_id}")

with st.expander("Storage Locations", expanded=True):
    with st.form("storage_form"):
        name = st.text_input("Name", value="Safe A - Tray 1")
        category = st.text_input("Category", value="Home Safe")
        description = st.text_area("Description", height=60)
        if st.form_submit_button("Add/Find Storage"):
            sid = upsert_storage(name, category or None, description or None)
            st.success(f"Storage ID: {sid}")

with st.expander("Parties (Dealers / Buyers)"):
    with st.form("party_form"):
        name = st.text_input("Name")
        kind = st.text_input("Kind (Dealer/Show/Marketplace)")
        contact = st.text_area("Contact")
        if st.form_submit_button("Add/Find Party"):
            pid = upsert_party(name, kind or None, contact or None)
            st.success(f"Party ID: {pid}")
