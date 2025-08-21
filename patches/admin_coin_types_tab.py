# patches/admin_coin_types_tab.py
import streamlit as st
import pandas as pd
import sqlite3
from db import get_conn
from queries import upsert_coin_master, upsert_coin_type

_BAD_EMPTY = {'-', '—', 'None', 'none', 'null', 'nan', 'NaN'}

def _norm_text(v: str) -> str:
    if v is None:
        return ''
    s = str(v).strip()
    return '' if s in _BAD_EMPTY else s

def _list_coin_masters():
    with get_conn() as cx:
        rows = cx.execute(
            """SELECT id, country, denomination, series FROM coin_master
                   ORDER BY country, denomination, series"""
        ).fetchall()
        return [dict(r) for r in rows]

def _list_coin_types_full():
    with get_conn() as cx:
        rows = cx.execute(
            """
            SELECT
              ct.id, ct.master_id, ct.year, ct.mint_mark, COALESCE(ct.variety,'') AS variety,
              ct.mintage, ct.is_proof, ct.designer, ct.obv_desc, ct.rev_desc,
              cm.country, cm.denomination, cm.series
            FROM coin_type ct
            JOIN coin_master cm ON cm.id = ct.master_id
            ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety
            """
        ).fetchall()
        return [dict(r) for r in rows]

def _update_coin_type(ct_id: int, fields: dict):
    sets = []
    params = []
    for k, v in fields.items():
        sets.append(f"{k}=?")
        params.append(v)
    params.append(ct_id)
    with get_conn() as cx:
        cx.execute(f"UPDATE coin_type SET {', '.join(sets)} WHERE id=?", params)

def _insert_coin_type(master_id: int, year: int, mint_mark: str, variety: str,
                     mintage, is_proof, designer, obv_desc, rev_desc) -> int:
    mint_mark = _norm_text(mint_mark)
    variety = _norm_text(variety)
    try:
        return upsert_coin_type(master_id, year, mint_mark, variety,
                                mintage=mintage if mintage not in ('', None) else None,
                                is_proof=1 if is_proof else 0,
                                designer=_norm_text(designer),
                                obv_desc=_norm_text(obv_desc),
                                rev_desc=_norm_text(rev_desc))
    except sqlite3.IntegrityError:
        raise

def _master_label(m):
    return f"{m['country']} — {m['denomination']} — {m['series']}  (#{m['id']})"

def _type_label(t):
    mm = f" {t['mint_mark']}" if t['mint_mark'] else ''
    var = f" • {t['variety']}" if t['variety'] else ''
    return f"{t['series']} {t['year']}{mm}{var}  (type #{t['id']})"

def render_admin_coin_types_tab():
    st.subheader("Coin Types")  # Add & Edit
    tab_add, tab_edit = st.tabs(["Add Type", "Edit Type"])

    # ===== Add Type =====
    with tab_add:
        masters = _list_coin_masters()
        st.caption("Create a new coin type. You can reuse an existing master or create one inline.")

        mode = st.radio("Master", ["Choose existing", "Create new"], horizontal=True, key="ct_mode_admin" )

        if mode == "Create new":
            with st.expander("New Coin Master", expanded=True):
                c1, c2, c3 = st.columns(3)
                cm_country = c1.text_input("Country", value="USA", key="cm_country_admin")
                cm_denom = c2.text_input("Denomination", value="Dollar", key="cm_denom_admin")
                cm_series = c3.text_input("Series", value="Morgan", key="cm_series_admin")
                c4, c5, c6 = st.columns(3)
                cm_metal = c4.text_input("Metal (Ag/Au/Pt)", value="Ag", key="cm_metal_admin")
                cm_fineness = c5.number_input("Fineness", min_value=0.0, max_value=1.0, step=0.001, value=0.9, key="cm_fineness_admin")
                cm_weight = c6.number_input("Weight (grams)", min_value=0.0, step=0.01, value=26.73, key="cm_weight_admin")
                if st.button("Save Master (or reuse if it exists)", key="save_master_admin"):
                    mid = upsert_coin_master(cm_country, cm_denom, cm_series, cm_metal, cm_fineness, cm_weight)
                    st.success(f"Master ready: id #{mid} ({cm_country} {cm_denom} {cm_series})")
                    st.session_state.setdefault("_new_master_id_admin", mid)
            master_id = st.session_state.get("_new_master_id_admin")
            if not master_id:
                st.info("Save the new master above (or switch to existing)." )
        else:
            if not masters:
                st.warning("No coin masters yet. Switch to 'Create new' to add one.")
                master_id = None
            else:
                options = {_master_label(m): m["id"] for m in masters}
                pick = st.selectbox("Coin Master", list(options.keys()), key="ct_master_pick_admin")
                master_id = options[pick]

        st.markdown("---")
        c1, c2, c3 = st.columns([1,1,2])
        year = c1.number_input("Year", min_value=0, max_value=3000, step=1, value=1881, key="ct_year_admin")
        mint_mark = c2.text_input("Mint Mark (blank for none)", value="", key="ct_mint_admin")
        variety = c3.text_input("Variety (optional)", value="", key="ct_variety_admin")
        c4, c5, c6 = st.columns(3)
        mintage = c4.number_input("Mintage (optional)", min_value=0, step=1, value=0, format="%d", key="ct_mintage_admin")
        is_proof = c5.checkbox("Is Proof?", value=False, key="ct_proof_admin")
        designer = c6.text_input("Designer (optional)", value="", key="ct_designer_admin")
        obv_desc = st.text_area("Obverse description (optional)", height=60, key="ct_obv_admin")
        rev_desc = st.text_area("Reverse description (optional)", height=60, key="ct_rev_admin")

        if st.button("Add Coin Type", type="primary", disabled=(master_id is None), key="ct_add_btn_admin"):
            try:
                mid = int(master_id) if master_id is not None else None
                if not mid:
                    st.error("Pick or create a master first.")
                else:
                    ct_id = _insert_coin_type(mid, int(year), mint_mark, variety, int(mintage) if mintage else None,
                                              is_proof, designer, obv_desc, rev_desc)
                    st.success(f"Added/Upserted coin type id #{ct_id}.")
            except sqlite3.IntegrityError:
                st.error("Unique conflict: a type for this master/year/mint/variety already exists.")
            except Exception as e:
                st.error(str(e))

    # ===== Edit Type =====
    with tab_edit:
        types = _list_coin_types_full()
        if not types:
            st.info("No coin types yet.")
        else:
            st.caption("Edit existing coin types. Changes propagate to new transactions (existing lots remain tied to their types)." )
            options = {_type_label(t): t for t in types}
            label = st.selectbox("Coin Type", list(options.keys()), key="ct_edit_pick_admin")
            row = options[label]

            c1, c2, c3 = st.columns([1,1,2])
            e_year = c1.number_input("Year", min_value=0, max_value=3000, step=1, value=int(row["year"]), key="e_ct_year_admin")
            e_mint = c2.text_input("Mint Mark", value=row["mint_mark"], key="e_ct_mint_admin")
            e_var = c3.text_input("Variety", value=row["variety"], key="e_ct_var_admin")
            c4, c5, c6 = st.columns(3)
            e_mintage = c4.number_input("Mintage", min_value=0, step=1, value=int(row["mintage"]) if row["mintage"] is not None else 0, key="e_ct_mintage_admin")
            e_proof = c5.checkbox("Is Proof?", value=bool(row["is_proof"]), key="e_ct_proof_admin")
            e_des = c6.text_input("Designer", value=row["designer"] or "", key="e_ct_des_admin")
            e_obv = st.text_area("Obverse description", value=row["obv_desc"] or "", height=60, key="e_ct_obv_admin")
            e_rev = st.text_area("Reverse description", value=row["rev_desc"] or "", height=60, key="e_ct_rev_admin")

            colA, colB = st.columns([1,1])
            if colA.button("Save Changes", type="primary", key="ct_save_edit_admin"):
                try:
                    fields = {
                        "year": int(e_year),
                        "mint_mark": _norm_text(e_mint),
                        "variety": _norm_text(e_var),
                        "mintage": int(e_mintage) if e_mintage else None,
                        "is_proof": 1 if e_proof else 0,
                        "designer": _norm_text(e_des),
                        "obv_desc": _norm_text(e_obv),
                        "rev_desc": _norm_text(e_rev),
                    }
                    _update_coin_type(int(row["id"]), fields)
                    st.success("Saved.")
                except sqlite3.IntegrityError:
                    st.error("Unique conflict: another coin type already uses this master/year/mint/variety.")
                except Exception as e:
                    st.error(str(e))

            # Optional: quick delete (guarded)
            with colB.popover("Dangerous actions"):
                st.caption("Delete this coin type (no lots must reference it)." )
                if st.button("Delete coin type", type="secondary", key="ct_del_admin"):
                    try:
                        with get_conn() as cx:
                            cx.execute("DELETE FROM coin_type WHERE id=?", (row["id"],))
                        st.success("Deleted coin type.")
                    except sqlite3.IntegrityError:
                        st.error("Cannot delete: there are transactions/lots referencing this type.")