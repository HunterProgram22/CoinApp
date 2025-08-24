# pages/7_Coin_Type_Editor.py
import streamlit as st
import pandas as pd
from db import get_conn
from queries import list_coin_types

st.header("Coin Type & Guide Price Editor")


# ---------- Helpers ----------

def _load_coin_type(ct_id: int):
    with get_conn() as cx:
        ct = cx.execute(
            '''
            SELECT ct.*,
                   cm.country, cm.denomination, cm.series
            FROM coin_type ct
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE ct.id = ?
            ''',
            (ct_id,)
        ).fetchone()
    return ct


def _update_coin_type(ct_id: int, mint_mark: str, variety: str, is_proof: int, mintage, designer,
                      obv_desc, rev_desc):
    with get_conn() as cx:
        cx.execute(
            '''
            UPDATE coin_type
               SET mint_mark = ?,
                   variety   = ?,
                   is_proof  = ?,
                   mintage   = ?,
                   designer  = ?,
                   obv_desc  = ?,
                   rev_desc  = ?
             WHERE id = ?
            ''',
            (mint_mark or '', variety or '', int(bool(is_proof)),
             int(mintage) if mintage not in (None, '', 0) else None,
             designer or None, obv_desc or None, rev_desc or None, ct_id)
        )


def _list_guide_prices(ct_id: int):
    with get_conn() as cx:
        rows = cx.execute(
            '''
            SELECT id, grade_text, numeric_grade, price_usd, as_of, COALESCE(source,'') AS source
            FROM guide_price
            WHERE coin_type_id = ?
            ORDER BY as_of DESC, numeric_grade, grade_text
            ''',
            (ct_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def _upsert_guide_price(ct_id: int, grade_text: str, numeric_grade, price_usd: float, as_of: str,
                        source: str):
    grade_text = (grade_text or '').strip().upper()
    if not grade_text or not as_of:
        raise ValueError("Grade Text and As-Of date are required.")
    with get_conn() as cx:
        cx.execute(
            '''
            INSERT INTO guide_price(coin_type_id, grade_text, numeric_grade, price_usd, as_of, source)
            VALUES (?,            ?,          ?,            ?,        ?,     ?)
            ON CONFLICT(coin_type_id, grade_text, as_of)
            DO UPDATE SET numeric_grade = excluded.numeric_grade,
                          price_usd     = excluded.price_usd,
                          source        = excluded.source
            ''',
            (
            ct_id, grade_text, float(numeric_grade) if numeric_grade not in (None, '', 0) else None,
            float(price_usd), as_of, source or None)
        )


def _delete_guide_price_by_id(gp_id: int):
    with get_conn() as cx:
        cx.execute("DELETE FROM guide_price WHERE id = ?", (gp_id,))


# ---------- UI ----------

coin_types = list_coin_types()
if not coin_types:
    st.info("No coin types found. Add some via Admin > Coin Type Editor first.")
    st.stop()

# Create options for selectbox
options = []
for ct in coin_types:
    mm_part = f" {ct['mint_mark']}" if ct['mint_mark'] else ""
    var_part = f" • {ct['variety']}" if ct['variety'] else ""
    label = f"{ct['series']} {ct['year']}{mm_part}{var_part}"
    options.append(label)

# Select coin type
selected_label = st.selectbox("Select a coin type", options)
selected_index = options.index(selected_label)
ct_id = coin_types[selected_index]['id']
ct = _load_coin_type(ct_id)

if not ct:
    st.error("Coin type not found.")
    st.stop()

st.subheader(
    f"{ct['series']} — {ct['year']}{(' ' + ct['mint_mark']) if ct['mint_mark'] else ''}{(' • ' + ct['variety']) if ct['variety'] else ''}")

tab_details, tab_prices = st.tabs(["Coin Type Details", "Guide Prices"])

# ---------- Coin Type Details Tab ----------
with tab_details:
    st.caption("Edit descriptive fields for this specific year/mint/variety.")

    col1, col2 = st.columns(2)
    mint_mark = col1.text_input("Mint Mark", value=ct['mint_mark'] or '')
    variety = col2.text_input("Variety", value=ct['variety'] or '')

    is_proof = st.checkbox("Is Proof?", value=bool(ct['is_proof']))

    col3, col4 = st.columns(2)
    mintage = col3.number_input("Mintage", min_value=0, step=1, value=int(ct['mintage'] or 0))
    designer = col4.text_input("Designer", value=ct['designer'] or '')

    obv_desc = st.text_area("Obverse Description", value=ct['obv_desc'] or '', height=70)
    rev_desc = st.text_area("Reverse Description", value=ct['rev_desc'] or '', height=70)

    if st.button("Save Coin Type Changes"):
        try:
            _update_coin_type(ct_id, mint_mark, variety, is_proof, mintage, designer, obv_desc,
                              rev_desc)
            st.success("Coin Type updated.")
            st.rerun()
        except Exception as e:
            st.error(f"Error updating coin type: {e}")

# ---------- Guide Prices Tab ----------
with tab_prices:
    st.caption(
        "Maintain per-grade price guides for this coin type (used in GUIDE_ONLY/AUTO valuation).")

    prices = _list_guide_prices(ct_id)
    if prices:
        df = pd.DataFrame(prices)
        df = df.rename(columns={
            "grade_text": "Grade",
            "numeric_grade": "Num",
            "price_usd": "Price (USD)",
            "as_of": "As Of",
            "source": "Source",
        })
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No guide prices for this coin type yet.")

    # Add new guide price
    st.markdown("---")
    st.subheader("Add/Update Guide Price")

    with st.form("guide_price_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        grade_text = col1.text_input("Grade Text*", placeholder="e.g., G4, VF20, AU50, MS65")
        numeric_grade = col2.number_input("Numeric Grade", min_value=0.0, step=0.5, value=0.0)
        price_usd = col3.number_input("Price (USD)*", min_value=0.0, step=0.01, value=0.00)

        col4, col5 = st.columns(2)
        as_of = col4.date_input("As-Of Date*")
        source = col5.text_input("Source", placeholder="PCGS, NGC, etc.")

        if st.form_submit_button("Save Guide Price"):
            if not grade_text or price_usd <= 0:
                st.error("Grade Text and Price are required.")
            else:
                try:
                    _upsert_guide_price(ct_id, grade_text,
                                        numeric_grade if numeric_grade > 0 else None,
                                        price_usd, as_of.isoformat(), source)
                    st.success("Guide price saved.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving guide price: {e}")

    # Delete guide prices
    if prices:
        with st.expander("Delete Guide Price"):
            price_options = [f"{p['grade_text']} @ {p['as_of']} — ${p['price_usd']}" for p in
                             prices]
            selected_price = st.selectbox("Select price to delete", price_options)

            if st.button("Delete Selected Price", type="secondary"):
                try:
                    price_id = prices[price_options.index(selected_price)]['id']
                    _delete_guide_price_by_id(price_id)
                    st.success("Guide price deleted.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error deleting guide price: {e}")