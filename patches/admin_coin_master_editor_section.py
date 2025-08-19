
# ---- CATALOG: COIN MASTER EDITOR (Admin section) ----
# Paste this into pages/8_Admin.py (after imports) and call render_catalog_coin_master_editor()
import sqlite3
import pandas as pd
import streamlit as st
from db import get_conn
from queries import upsert_coin_master

def _safe_rerun():
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()

def _cm_nullify(x):
    if x is None:
        return None
    s = str(x).strip()
    return None if s == '' or s.lower() in {'none','nan','na','-','—'} else s

def _cm_nullify_float(x):
    try:
        if x is None or str(x).strip() == '':
            return None
        return float(x)
    except Exception:
        return None

def _cm_fetch(search: str | None = None) -> list[dict]:
    sql = """
    SELECT id, country, denomination, series, metal, fineness, weight_grams,
           diameter_mm, thickness_mm, edge, years_start, years_end, notes
    FROM coin_master
    WHERE (? IS NULL OR lower(country||' '||denomination||' '||series||' '||COALESCE(metal,'')) LIKE '%'||lower(?)||'%')
    ORDER BY country, denomination, series
    """
    with get_conn() as cx:
        rows = cx.execute(sql, (search, search)).fetchall()
        return [dict(r) for r in rows]

def _cm_choices(rows: list[dict]) -> dict:
    return {f"{r['country']} — {r['denomination']} — {r['series']} (#{r['id']})": r['id'] for r in rows}

def _cm_get(master_id: int) -> dict | None:
    with get_conn() as cx:
        r = cx.execute("""
            SELECT id, country, denomination, series, metal, fineness, weight_grams,
                   diameter_mm, thickness_mm, edge, years_start, years_end, notes
            FROM coin_master WHERE id=?
        """, (master_id,)).fetchone()
        return dict(r) if r else None

def _cm_update(master_id: int, **kw) -> tuple[bool,str]:
    cols = ["country","denomination","series","metal","fineness","weight_grams","diameter_mm","thickness_mm","edge","years_start","years_end","notes"]
    sets = ",".join([f"{c}=?" for c in cols])
    vals = [kw.get(c) for c in cols] + [master_id]
    try:
        with get_conn() as cx:
            cx.execute(f"UPDATE coin_master SET {sets} WHERE id=?", vals)
        return True, "Saved."
    except sqlite3.IntegrityError as e:
        return False, f"Unique constraint failed (country+denomination+series): {e!s}"
    except Exception as e:
        return False, f"Update failed: {e!s}"

def _cm_delete(master_id: int) -> tuple[bool,str]:
    with get_conn() as cx:
        # Block delete if any coin_type rows exist
        n = cx.execute("SELECT COUNT(*) AS c FROM coin_type WHERE master_id=?", (master_id,)).fetchone()[0]
        if n > 0:
            return False, f"Cannot delete: {n} coin type(s) exist for this master."
        try:
            cx.execute("DELETE FROM coin_master WHERE id=?", (master_id,))
            return True, "Deleted."
        except Exception as e:
            return False, f"Delete failed: {e!s}"

_PRESETS = {
    "US 90% Silver Dime (Roosevelt 1946–64)": {"metal":"Ag","fineness":0.900,"weight_grams":2.5},
    "US 90% Silver Quarter (1932–64)": {"metal":"Ag","fineness":0.900,"weight_grams":6.25},
    "US 90% Silver Half (Walker/Franklin/Kennedy 1964)": {"metal":"Ag","fineness":0.900,"weight_grams":12.5},
    "US 40% Silver Half (Kennedy 1965–70)": {"metal":"Ag","fineness":0.400,"weight_grams":11.5},
    "American Silver Eagle (1 oz)": {"metal":"Ag","fineness":0.999,"weight_grams":31.1035},
}

def render_catalog_coin_master_editor():
    st.subheader("📖 Catalog — Coin Master Editor")
    st.caption("Edit master-level attributes (metal, fineness, weight, etc.). These drive melt valuation when valuation method is MELT_ONLY.")

    # Search + list
    search = st.text_input("Search (country / denomination / series)", placeholder="e.g., USA dime 90%" )
    masters = _cm_fetch(search if search and search.strip() else None)
    if masters:
        df = pd.DataFrame(masters)[[
            "id","country","denomination","series","metal","fineness","weight_grams","years_start","years_end"
        ]]
        df = df.rename(columns={"id":"Master ID","weight_grams":"Wt (g)"})
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No master coins yet.")

    st.divider()

    # Edit existing
    if masters:
        pick_map = _cm_choices(masters)
        label = st.selectbox("Select a master to edit", list(pick_map.keys()))
        master_id = pick_map[label]
        rec = _cm_get(master_id) or {}

        with st.form("cm_edit", clear_on_submit=False):
            col1, col2, col3 = st.columns(3)
            country = col1.text_input("Country", value=rec.get("country",""))
            denom   = col2.text_input("Denomination", value=rec.get("denomination",""))
            series  = col3.text_input("Series", value=rec.get("series",""))

            col4, col5, col6 = st.columns(3)
            metal   = col4.text_input("Metal (Ag/Au/Pt/etc.)", value=rec.get("metal") or "")
            fineness= col5.number_input("Fineness", min_value=0.0, max_value=1.0, step=0.001, value=float(rec.get("fineness") or 0.0))
            wt      = col6.number_input("Weight (grams)", min_value=0.0, step=0.001, value=float(rec.get("weight_grams") or 0.0))

            col7, col8, col9 = st.columns(3)
            dia     = col7.number_input("Diameter (mm)", min_value=0.0, step=0.01, value=float(rec.get("diameter_mm") or 0.0))
            thick   = col8.number_input("Thickness (mm)", min_value=0.0, step=0.01, value=float(rec.get("thickness_mm") or 0.0))
            edge    = col9.text_input("Edge", value=rec.get("edge") or "" )

            colA, colB = st.columns(2)
            ystart = colA.number_input("Years start", min_value=0, step=1, value=int(rec.get("years_start") or 0))
            yend   = colB.number_input("Years end", min_value=0, step=1, value=int(rec.get("years_end") or 0))

            notes = st.text_area("Notes", value=rec.get("notes") or "", height=80)

            preset = st.selectbox("Quick preset (optional)", ["(none)"] + list(_PRESETS.keys()))
            apply_preset = st.checkbox("Apply preset values to Metal/Fineness/Weight", value=False)

            left, mid, right = st.columns([1,1,1])
            do_save   = left.form_submit_button("💾 Save changes", type="primary")
            do_delete = right.form_submit_button("🗑️ Delete master", type="secondary")

        if do_delete:
            ok, msg = _cm_delete(master_id)
            (st.success if ok else st.error)(msg)
            _safe_rerun()

        if do_save:
            if apply_preset and preset and preset != "(none)" and preset in _PRESETS:
                preset_vals = _PRESETS[preset]
                if not metal:   metal = preset_vals.get("metal", metal)
                if not fineness or fineness == 0.0: fineness = preset_vals.get("fineness", fineness) or 0.0
                if not wt or wt == 0.0:             wt = preset_vals.get("weight_grams", wt) or 0.0

            ok, msg = _cm_update(
                master_id,
                country=_cm_nullify(country),
                denomination=_cm_nullify(denom),
                series=_cm_nullify(series),
                metal=_cm_nullify(metal),
                fineness=_cm_nullify_float(fineness),
                weight_grams=_cm_nullify_float(wt),
                diameter_mm=_cm_nullify_float(dia),
                thickness_mm=_cm_nullify_float(thick),
                edge=_cm_nullify(edge),
                years_start=int(ystart) if ystart else None,
                years_end=int(yend) if yend else None,
                notes=_cm_nullify(notes),
            )
            (st.success if ok else st.error)(msg)
            _safe_rerun()

    st.divider()

    # Add new
    with st.expander("➕ Add new master coin", expanded=False):
        with st.form("cm_add", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            country = col1.text_input("Country", value="USA")
            denom   = col2.text_input("Denomination", value="")
            series  = col3.text_input("Series", value="")

            col4, col5, col6 = st.columns(3)
            metal   = col4.text_input("Metal (Ag/Au/Pt/etc.)", value="")
            fineness= col5.number_input("Fineness", min_value=0.0, max_value=1.0, step=0.001, value=0.0)
            wt      = col6.number_input("Weight (grams)", min_value=0.0, step=0.001, value=0.0)

            col7, col8 = st.columns(2)
            ystart = col7.number_input("Years start", min_value=0, step=1, value=0)
            yend   = col8.number_input("Years end", min_value=0, step=1, value=0)

            notes = st.text_area("Notes", value="", height=60)

            preset = st.selectbox("Quick preset (optional)", ["(none)"] + list(_PRESETS.keys()))
            apply_preset = st.checkbox("Apply preset to Metal/Fineness/Weight", value=False)

            submitted = st.form_submit_button("Create master", type="primary")
        if submitted:
            if apply_preset and preset and preset != "(none)" and preset in _PRESETS:
                pv = _PRESETS[preset]
                if not metal:    metal = pv.get("metal", metal)
                if not fineness: fineness = pv.get("fineness", fineness) or 0.0
                if not wt:       wt = pv.get("weight_grams", wt) or 0.0

            mid = upsert_coin_master(
                _cm_nullify(country), _cm_nullify(denom), _cm_nullify(series),
                _cm_nullify(metal), _cm_nullify_float(fineness), _cm_nullify_float(wt),
                None, None, None,
                int(ystart) if ystart else None,
                int(yend) if yend else None,
                _cm_nullify(notes)
            )
            st.success(f"Created/Found master with ID #{mid}")
            _safe_rerun()
# ---- END COIN MASTER EDITOR ----
