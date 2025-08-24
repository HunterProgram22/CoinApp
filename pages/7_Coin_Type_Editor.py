
# pages/9_Coin_Type_Editor.py
import streamlit as st
import pandas as pd
from db import get_conn
from queries import list_coin_types

st.header("🧩 Coin Type & Guide Price Editor")

# ---------- Helpers ----------

NAN_LIKE = {"nan", "none", "-", "—"}

def _normalize_mm(mm: str) -> str:
    if mm is None:
        return ""
    mm = str(mm).strip()
    if mm.lower() in NAN_LIKE:
        return ""
    return mm

def _normalize_variety(v: str) -> str:
    if v is None:
        return ""
    v = str(v).strip()
    if v.lower() in NAN_LIKE:
        return ""
    return v

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
    mint_mark = _normalize_mm(mint_mark)
    variety   = _normalize_variety(variety)
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
            ORDER BY as_of DESC, numeric_grade, grade_text
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

def _merge_nan_duplicate_for_key(key):
    """Merge duplicate coin_type rows for a normalized key (handles 'nan/None/-/—' variants).
    Repoints FKs to the clean row and deletes the duplicate."""
    series, year, mm_norm, var_norm = key
    with get_conn() as cx:
        rows = cx.execute(
            '''
            SELECT ct.id, ct.mint_mark, ct.variety
            FROM coin_type ct
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE cm.series = ? AND ct.year = ?
              AND (ct.mint_mark = ? OR (LOWER(TRIM(ct.mint_mark)) IN ('nan','none','-','—') AND ? = ''))
              AND (ct.variety   = ? OR (LOWER(TRIM(ct.variety))   IN ('nan','none','-','—') AND ? = ''))
            ''',
            (series, year, mm_norm, mm_norm, var_norm, var_norm)
        ).fetchall()

        if len(rows) < 2:
            return "No duplicate to merge for this key."

        clean = None
        bad = None
        for r in rows:
            is_bad = (str(r["variety"] or "").strip().lower() in NAN_LIKE) or (str(r["mint_mark"] or "").strip().lower() in NAN_LIKE)
            if is_bad:
                bad = r if bad is None else (bad if bad["id"] < r["id"] else r)
            else:
                clean = r if clean is None else (clean if clean["id"] < r["id"] else r)

        if not clean or not bad:
            return "Nothing to merge (no clear clean/bad pair)."

        good_id = clean["id"]
        bad_id  = bad["id"]

        cx.execute("BEGIN")
        try:
            for table in ["tx_line", "lot", "guide_price", "coin_type_tag", "image", "specimen"]:
                try:
                    cx.execute(f"UPDATE {table} SET coin_type_id = ? WHERE coin_type_id = ?", (good_id, bad_id))
                except Exception:
                    pass
            cx.execute("DELETE FROM coin_type WHERE id = ?", (bad_id,))
            cx.execute("COMMIT")
        except Exception as e:
            cx.execute("ROLLBACK")
            raise e
    return f"Merged duplicate coin_type #{bad_id} into #{good_id}."

# ---------- UI ----------

labels, ids, meta = list_coin_types()
if not ids:
    st.info("No coin types found. Add some via Import or Add Transaction (BUY).")
    st.stop()

pick_label = st.selectbox("Select a coin type", labels, index=0)
ct_id = ids[labels.index(pick_label)]
ct = _load_coin_type(ct_id)

# If key has dup rows, offer a cleanup
key_info = meta[pick_label]
if len(key_info['dups']) > 1:
    with st.expander("⚠️ Duplicate 'nan' variant detected — click to merge"):
        st.caption("You have multiple coin_type rows for the same Series/Year/Mint/Variety due to 'nan/None'. You can merge them below.")
        if st.button("Merge duplicates for this coin type key"):
            try:
                msg = _merge_nan_duplicate_for_key(key_info['key'])
                st.success(msg)
            except Exception as e:
                st.error(str(e))

st.subheader(f"{ct['series']} — {ct['year']} {(_normalize_mm(ct['mint_mark']))}{(' • ' + _normalize_variety(ct['variety'])) if _normalize_variety(ct['variety']) else ''}")

tab_details, tab_prices = st.tabs(["Coin Type details", "Guide Prices"])

with tab_details:
    st.caption("Edit descriptive fields for this specific year/mint/variety (coin_type).")
    col1, col2 = st.columns(2)
    mint_mark = col1.text_input("Mint Mark ('' for none)", value=_normalize_mm(ct['mint_mark']))
    variety   = col2.text_input("Variety", value=_normalize_variety(ct['variety']))
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
