
# pages/9_Coin_Type_Editor.py
import streamlit as st
import pandas as pd
from db import get_conn

st.header("🧩 Coin Type & Guide Price Editor")

# ---------- Helpers ----------

def _list_coin_types_for_picker():
    with get_conn() as cx:
        rows = cx.execute(
            '''
            SELECT ct.id,
                   cm.country, cm.denomination, cm.series,
                   ct.year, ct.mint_mark, COALESCE(ct.variety,'') AS variety,
                   ct.is_proof
            FROM coin_type ct
            JOIN coin_master cm ON cm.id = ct.master_id
            ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety
            '''
        ).fetchall()
        labels = []
        ids = []
        for r in rows:
            mm = (r['mint_mark'] or '').strip()
            lab = f"{r['series']} {r['year']}{(' ' + mm) if mm else ''}{(' • ' + r['variety']) if r['variety'] else ''}  (#{r['id']})"
            labels.append(lab)
            ids.append(r['id'])
        return labels, ids

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

def _update_coin_type(ct_id: int, mint_mark: str, variety: str, is_proof: int, mintage, designer, obv_desc, rev_desc):
    mint_mark = (mint_mark or '').strip()
    variety = (variety or '').strip()
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
            (mint_mark, variety, int(bool(is_proof)), int(mintage) if mintage not in (None,'') else None,
             designer or None, obv_desc or None, rev_desc or None, ct_id)
        )

def _list_guide_prices(ct_id: int):
    with get_conn() as cx:
        rows = cx.execute(
            '''
            SELECT id, grade_text, numeric_grade, price_usd, as_of, COALESCE(source,'') AS source
            FROM guide_price
            WHERE coin_type_id = ?
            ORDER BY as_of DESC, numeric_grade NULLS LAST, grade_text
            ''',
            (ct_id,)
        ).fetchall()
        return [dict(r) for r in rows]

def _upsert_guide_price(ct_id: int, grade_text: str, numeric_grade, price_usd: float, as_of: str, source: str):
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
            (ct_id, grade_text, float(numeric_grade) if numeric_grade not in (None,'') else None,
             float(price_usd), as_of, source or None)
        )

def _delete_guide_price_by_id(gp_id: int):
    with get_conn() as cx:
        cx.execute("DELETE FROM guide_price WHERE id = ?", (gp_id,))

# ---------- UI ----------

labels, ids = _list_coin_types_for_picker()
if not ids:
    st.info("No coin types found. Add some via Import or Add Transaction (BUY).")
    st.stop()

pick_label = st.selectbox("Select a coin type", labels, index=0)
ct_id = ids[labels.index(pick_label)]
ct = _load_coin_type(ct_id)

st.subheader(f"{ct['series']} — {ct['year']} {(ct['mint_mark'] or '').strip()} {('• ' + ct['variety']) if ct['variety'] else ''}")

tab_details, tab_prices = st.tabs(["Coin Type details", "Guide Prices"])

with tab_details:
    st.caption("Edit descriptive fields for this specific year/mint/variety (coin_type).")
    col1, col2 = st.columns(2)
    mint_mark = col1.text_input("Mint Mark ('' for none)", value=(ct['mint_mark'] or ''))
    variety   = col2.text_input("Variety", value=(ct['variety'] or ''))
    is_proof  = st.checkbox("Is Proof?", value=bool(ct['is_proof']))
    col3, col4 = st.columns(2)
    mintage   = col3.number_input("Mintage", min_value=0, step=1, value=int(ct['mintage'] or 0))
    designer  = col4.text_input("Designer", value=(ct['designer'] or ''))
    obv_desc  = st.text_area("Obverse Description", value=(ct['obv_desc'] or ''), height=70)
    rev_desc  = st.text_area("Reverse Description", value=(ct['rev_desc'] or ''), height=70)

    if st.button("Save Coin Type"):
        try:
            _update_coin_type(ct_id, mint_mark, variety, is_proof, mintage, designer, obv_desc, rev_desc)
            st.success("Coin Type updated.")
        except Exception as e:
            st.error(str(e))

with tab_prices:
    st.caption("Maintain per-grade price guides for this coin type (used in GUIDE_ONLY/AUTO valuation).")
    rows = _list_guide_prices(ct_id)
    if rows:
        df = pd.DataFrame(rows)
        df = df.rename(columns={
            "grade_text": "Grade",
            "numeric_grade": "Num",
            "price_usd": "Price (USD)",
            "as_of": "As Of",
            "source": "Source",
        })
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No guide prices yet for this type. Add some below.")

    st.markdown("---")
    st.subheader("Add / Update Guide Price")
    with st.form("gp_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        grade_text = c1.text_input("Grade Text", placeholder="e.g., G4, VF20, AU50, MS65")
        numeric_grade = c2.number_input("Numeric Grade (optional)", min_value=0.0, step=0.5, value=0.0, format="%.1f")
        price_usd = c3.number_input("Price (USD)", min_value=0.0, step=0.01, value=0.00)
        as_of = c1.date_input("As-Of Date")
        source = c2.text_input("Source (optional)", placeholder="e.g., PCGS, CDN Greysheet")

        submitted = st.form_submit_button("Save Guide Price")
        if submitted:
            try:
                _upsert_guide_price(ct_id, grade_text, numeric_grade if numeric_grade != 0 else None, price_usd, as_of.isoformat(), source)
                st.success("Guide price saved.")
            except Exception as e:
                st.error(str(e))

    # Delete section
    with st.expander("Delete a guide price row"):
        if rows:
            id_map = {f"{r['grade_text']} @ {r['as_of']} — ${r['price_usd']} (id {r['id']})": r['id'] for r in rows}
            sel = st.selectbox("Choose row to delete", list(id_map.keys()))
            if st.button("Delete selected row", type="secondary"):
                try:
                    _delete_guide_price_by_id(id_map[sel])
                    st.success("Deleted.")
                except Exception as e:
                    st.error(str(e))
        else:
            st.caption("Nothing to delete.")
