
# pages/8_Admin.py
import streamlit as st
import sqlite3
from datetime import datetime, date
from pathlib import Path as _Path
from db import get_conn, DB_PATH, init_db
from queries import upsert_coin_master, upsert_coin_type

st.header("Admin")

# ==============================
# Helper label + pick functions
# ==============================
_BAD_EMPTY = {'-', '—', 'None', 'none', 'null', 'nan', 'NaN'}

def _norm_text(v: str) -> str:
    if v is None:
        return ''
    s = str(v).strip()
    return '' if s in _BAD_EMPTY else s

def _label_master(m: dict) -> str:
    # Keep labels clean; don't show IDs
    return f"{m['country']} — {m['denomination']} — {m['series']}"

def _label_type(t: dict) -> str:
    mm  = f" {t['mint_mark']}" if t.get('mint_mark') else ""
    var = f" • {t['variety']}" if t.get('variety') else ""
    return f"{t['series']} {t['year']}{mm}{var}"

def _label_storage(s: dict) -> str:
    return f"{s['name']}" + (f" ({s['category']})" if s.get('category') else "")

def _label_lot(l: dict) -> str:
    mm  = f" {l['mint_mark']}" if l.get('mint_mark') else ""
    var = f" • {l['variety']}" if l.get('variety') else ""
    return f"{l['series']} {l['year']}{mm}{var} — {l['qty_remaining']}×"

def _load_masters():
    with get_conn() as cx:
        rows = cx.execute("""
          SELECT id, country, denomination, series,
                 metal, fineness, weight_grams, diameter_mm, thickness_mm, edge,
                 years_start, years_end, COALESCE(notes,'') AS notes,
                 COALESCE(asset_category,'COIN') AS asset_category
          FROM coin_master
          ORDER BY country, denomination, series
        """ ).fetchall()
    return [dict(r) for r in rows]

def _load_types(master_id: int | None = None):
    where = "WHERE ct.master_id=?" if master_id else ""
    params = (master_id,) if master_id else ()
    with get_conn() as cx:
        rows = cx.execute(f"""
          SELECT ct.id, ct.master_id, cm.series, ct.year, ct.mint_mark, COALESCE(ct.variety,'') AS variety,
                 ct.mintage, ct.is_proof, ct.designer, ct.obv_desc, ct.rev_desc
          FROM coin_type ct
          JOIN coin_master cm ON cm.id=ct.master_id
          {where}
          ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety
        """, params).fetchall()
    return [dict(r) for r in rows]

def _load_storage():
    with get_conn() as cx:
        rows = cx.execute("""
          SELECT id, name, COALESCE(category,'') AS category, COALESCE(description,'') AS description
          FROM storage_location ORDER BY name
        """ ).fetchall()
    return [dict(r) for r in rows]

def _load_lots(only_open=True):
    where = "WHERE l.qty_remaining>0" if only_open else ""
    with get_conn() as cx:
        rows = cx.execute(f"""
          SELECT l.id, l.qty_remaining,
                 cm.series, ct.year, ct.mint_mark, COALESCE(ct.variety,'') AS variety
          FROM lot l
          JOIN coin_type ct ON ct.id=l.coin_type_id
          JOIN coin_master cm ON cm.id=ct.master_id
          {where}
          ORDER BY l.acquired_date DESC, l.id DESC
        """ ).fetchall()
    return [dict(r) for r in rows]

def _load_guide_prices(coin_type_id: int):
    with get_conn() as cx:
        rows = cx.execute("""
           SELECT id, grade_text, numeric_grade, price_usd, as_of, COALESCE(source,'') AS source
           FROM guide_price
           WHERE coin_type_id=?
           ORDER BY as_of DESC, numeric_grade DESC, grade_text
        """, (coin_type_id,)).fetchall()
    return [dict(r) for r in rows]

def _latest_spot_rows():
    with get_conn() as cx:
        rows = cx.execute("""
          SELECT metal, price_per_oz_usd, quoted_at_utc
          FROM metal_price mp
          WHERE quoted_at_utc = (
            SELECT MAX(quoted_at_utc) FROM metal_price x WHERE x.metal = mp.metal
          )
          ORDER BY metal
        """ ).fetchall()
    return [dict(r) for r in rows]

def pick_coin_master(label: str, key: str | None = None, allow_none: bool = False) -> int | None:
    masters = _load_masters()
    if allow_none:
        masters = [{"id": None, "country": "", "denomination": "", "series": "(none)"}] + masters
    sel = st.selectbox(label, masters, format_func=_label_master, key=key)
    return sel["id"] if sel else None

def pick_coin_type(label: str, key: str | None = None, master_id: int | None = None) -> dict | None:
    types = _load_types(master_id)
    if not types:
        st.warning("No coin types found. Add one in Coin Types tab.")
        return None
    sel = st.selectbox(label, types, format_func=_label_type, key=key)
    return sel

def pick_storage(label: str, key: str | None = None, allow_none: bool = True) -> int | None:
    stores = _load_storage()
    if allow_none:
        stores = [{"id": None, "name": "(none)", "category": "", "description": ""}] + stores
    sel = st.selectbox(label, stores, format_func=_label_storage, key=key)
    return sel["id"] if sel else None

def pick_lot(label: str, key: str | None = None, only_open=True) -> int | None:
    lots = _load_lots(only_open=only_open)
    if not lots:
        st.info("No lots available.")
        return None
    sel = st.selectbox(label, lots, format_func=_label_lot, key=key)
    return sel["id"] if sel else None

# ==============================
# Tabs (including Reset DB at the end)
# ==============================
tab_master, tab_types, tab_guide, tab_prices, tab_void, tab_delete, tab_reset = st.tabs(
    ["Coin Master", "Coin Types", "Guide Prices", "Metal Prices", "Void Tools", "Delete Lot", "Reset DB"]
)

# ------------------------------
# Coin Master (Add & Edit)
# ------------------------------
with tab_master:
    st.subheader("Coin Master Editor")
    add_col, edit_col = st.columns(2)

    with add_col:
        st.markdown("**Add / Upsert Coin Master**")
        c1, c2, c3 = st.columns(3)
        country = c1.text_input("Country", value="USA", key="cm_add_country")
        denom   = c2.text_input("Denomination", value="Dollar", key="cm_add_denom")
        series  = c3.text_input("Series", value="Morgan", key="cm_add_series")
        c4, c5, c6 = st.columns(3)
        metal    = c4.text_input("Metal (Ag/Au/Pt/Pd)", value="Ag", key="cm_add_metal")
        fineness = c5.number_input("Fineness", min_value=0.0, max_value=1.0, step=0.001, value=0.9, key="cm_add_fineness")
        weight_g = c6.number_input("Weight (grams)", min_value=0.0, step=0.01, value=26.73, key="cm_add_weight")
        c7, c8, c9 = st.columns(3)
        diam_mm = c7.number_input("Diameter (mm)", min_value=0.0, step=0.01, value=38.10, key="cm_add_diam")
        thick_mm = c8.number_input("Thickness (mm)", min_value=0.0, step=0.01, value=2.40, key="cm_add_thick")
        edge = c9.text_input("Edge", value="Reeded", key="cm_add_edge")
        c10, c11 = st.columns(2)
        years_start = c10.number_input("First Year", min_value=0, max_value=3000, step=1, value=1878, key="cm_add_y0")
        years_end   = c11.number_input("Last Year", min_value=0, max_value=3000, step=1, value=1921, key="cm_add_y1")
        asset_category = st.selectbox("Asset Category", ["COIN","ROUND","BAR"], index=0, key="cm_add_category")
        notes = st.text_area("Notes", height=70, key="cm_add_notes")
        if st.button("Save Master", type="primary", key="cm_add_btn"):
            mid = upsert_coin_master(country, denom, series, metal or None, float(fineness or 0) or None,
                                     float(weight_g or 0) or None, float(diam_mm or 0) or None,
                                     float(thick_mm or 0) or None, edge or None,
                                     int(years_start) if years_start else None, int(years_end) if years_end else None,
                                     notes or None)
            # Ensure category is saved even if upsert found an existing row
            with get_conn() as cx:
                cx.execute("UPDATE coin_master SET asset_category=? WHERE id=?", (asset_category, mid))
            st.success(f"Saved/Upserted master: {country} {denom} {series} → {asset_category} (id #{mid})")
            try: st.rerun()
            except Exception: pass

    with edit_col:
        st.markdown("**Edit Existing Master**")
        masters = _load_masters()
        if not masters:
            st.info("No coin masters yet.")
        else:
            sel = st.selectbox("Pick master", masters, format_func=_label_master, key="cm_edit_pick")
            if sel:
                c1, c2, c3 = st.columns(3)
                e_country = c1.text_input("Country", value=sel["country"], key="cm_e_country")
                e_denom   = c2.text_input("Denomination", value=sel["denomination"], key="cm_e_denom")
                e_series  = c3.text_input("Series", value=sel["series"], key="cm_e_series")
                c4, c5, c6 = st.columns(3)
                e_metal    = c4.text_input("Metal", value=sel.get("metal") or "", key="cm_e_metal")
                e_fineness = c5.number_input("Fineness", min_value=0.0, max_value=1.0, step=0.001, value=float(sel.get("fineness") or 0.0), key="cm_e_fineness")
                e_weight_g = c6.number_input("Weight (grams)", min_value=0.0, step=0.01, value=float(sel.get("weight_grams") or 0.0), key="cm_e_weight")
                c7, c8, c9 = st.columns(3)
                e_diam_mm = c7.number_input("Diameter (mm)", min_value=0.0, step=0.01, value=float(sel.get("diameter_mm") or 0.0), key="cm_e_diam")
                e_thick_mm = c8.number_input("Thickness (mm)", min_value=0.0, step=0.01, value=float(sel.get("thickness_mm") or 0.0), key="cm_e_thick")
                e_edge = c9.text_input("Edge", value=sel.get("edge") or "", key="cm_e_edge")
                c10, c11, c12 = st.columns(3)
                e_y0 = c10.number_input("First Year", min_value=0, max_value=3000, step=1, value=int(sel.get("years_start") or 0), key="cm_e_y0")
                e_y1 = c11.number_input("Last Year", min_value=0, max_value=3000, step=1, value=int(sel.get("years_end") or 0), key="cm_e_y1")
                e_cat = c12.selectbox("Asset Category", ["COIN","ROUND","BAR"], index=["COIN","ROUND","BAR"].index(sel.get("asset_category","COIN")), key="cm_e_cat")
                e_notes = st.text_area("Notes", value=sel.get("notes") or "", height=70, key="cm_e_notes")

                if st.button("Save Changes", type="primary", key="cm_e_save"):
                    try:
                        with get_conn() as cx:
                            cx.execute("""
                              UPDATE coin_master
                              SET country=?, denomination=?, series=?, metal=?, fineness=?, weight_grams=?,
                                  diameter_mm=?, thickness_mm=?, edge=?, years_start=?, years_end=?, notes=?,
                                  asset_category=?
                              WHERE id=?
                            """, (e_country, e_denom, e_series, _norm_text(e_metal) or None, float(e_fineness or 0) or None,
                                    float(e_weight_g or 0) or None, float(e_diam_mm or 0) or None, float(e_thick_mm or 0) or None,
                                    _norm_text(e_edge) or None, int(e_y0) if e_y0 else None, int(e_y1) if e_y1 else None,
                                    _norm_text(e_notes) or None, e_cat, sel["id"]))
                        st.success("Master updated.")
                        try: st.rerun()
                        except Exception: pass
                    except sqlite3.IntegrityError:
                        st.error("Another master already has this Country + Denomination + Series.")

# ------------------------------
# Coin Types (Add & Edit)
# ------------------------------
with tab_types:
    st.subheader("Coin Types")
    tab_add, tab_edit = st.tabs(["Add Type", "Edit Type"])

    with tab_add:
        st.caption("Create a new coin type. You can reuse an existing master or create one inline.")
        mode = st.radio("Master", ["Choose existing", "Create new"], horizontal=True, key="ct_mode_admin")
        if mode == "Create new":
            with st.expander("New Coin Master", expanded=True):
                c1, c2, c3 = st.columns(3)
                cm_country = c1.text_input("Country", value="USA", key="cm_country_admin")
                cm_denom   = c2.text_input("Denomination", value="Dollar", key="cm_denom_admin")
                cm_series  = c3.text_input("Series", value="Morgan", key="cm_series_admin")
                c4, c5, c6 = st.columns(3)
                cm_metal    = c4.text_input("Metal (Ag/Au/Pt/Pd)", value="Ag", key="cm_metal_admin")
                cm_fineness = c5.number_input("Fineness", min_value=0.0, max_value=1.0, step=0.001, value=0.9, key="cm_fineness_admin")
                cm_weight   = c6.number_input("Weight (grams)", min_value=0.0, step=0.01, value=26.73, key="cm_weight_admin")
                cm_cat      = st.selectbox("Asset Category", ["COIN","ROUND","BAR"], index=0, key="cm_cat_admin")
                if st.button("Save Master (or reuse if it exists)", key="save_master_admin"):
                    mid = upsert_coin_master(cm_country, cm_denom, cm_series, cm_metal, cm_fineness, cm_weight)
                    with get_conn() as cx:
                        cx.execute("UPDATE coin_master SET asset_category=? WHERE id=?", (cm_cat, mid))
                    st.success(f"Master ready: id #{mid} ({cm_country} {cm_denom} {cm_series}) → {cm_cat}")
                    st.session_state.setdefault("_new_master_id_admin", mid)
            master_id = st.session_state.get("_new_master_id_admin")
            if not master_id:
                st.info("Save the new master above (or switch to existing)." )
        else:
            master_id = pick_coin_master("Coin Master", key="ct_master_pick_admin")

        st.markdown("---")
        c1, c2, c3 = st.columns([1,1,2])
        year = c1.number_input("Year", min_value=0, max_value=3000, step=1, value=1881, key="ct_year_admin")
        mint_mark = c2.text_input("Mint Mark (blank for none)", value="", key="ct_mint_admin")
        variety   = c3.text_input("Variety (optional)", value="", key="ct_variety_admin")
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
                    ct_id = upsert_coin_type(mid, int(year), _norm_text(mint_mark), _norm_text(variety),
                                             mintage=int(mintage) if mintage else None,
                                             is_proof=1 if is_proof else 0,
                                             designer=_norm_text(designer),
                                             obv_desc=_norm_text(obv_desc),
                                             rev_desc=_norm_text(rev_desc))
                    st.success(f"Added/Upserted coin type id #{ct_id}.")
                    try: st.rerun()
                    except Exception: pass
            except sqlite3.IntegrityError:
                st.error("Unique conflict: master/year/mint/variety already exists.")
            except Exception as e:
                st.error(str(e))

    with tab_edit:
        types = _load_types()
        if not types:
            st.info("No coin types yet.")
        else:
            st.caption("Edit existing coin types.")
            row = st.selectbox("Coin Type", types, format_func=_label_type, key="ct_edit_pick_admin")
            c1, c2, c3 = st.columns([1,1,2])
            e_year = c1.number_input("Year", min_value=0, max_value=3000, step=1, value=int(row["year"]), key="e_ct_year_admin")
            e_mint = c2.text_input("Mint Mark", value=row["mint_mark"], key="e_ct_mint_admin")
            e_var  = c3.text_input("Variety", value=row["variety"], key="e_ct_var_admin")
            c4, c5, c6 = st.columns(3)
            e_mintage = c4.number_input("Mintage", min_value=0, step=1, value=int(row["mintage"]) if row["mintage"] is not None else 0, key="e_ct_mintage_admin")
            e_proof   = c5.checkbox("Is Proof?", value=bool(row["is_proof"]), key="e_ct_proof_admin")
            e_des     = c6.text_input("Designer", value=row["designer"] or "", key="e_ct_des_admin")
            e_obv = st.text_area("Obverse description", value=row["obv_desc"] or "", height=60, key="e_ct_obv_admin")
            e_rev = st.text_area("Reverse description", value=row["rev_desc"] or "", height=60, key="e_ct_rev_admin")

            colA, colB = st.columns([1,1])
            if colA.button("Save Changes", type="primary", key="ct_save_edit_admin"):
                try:
                    with get_conn() as cx:
                        cx.execute("""
                          UPDATE coin_type
                          SET year=?, mint_mark=?, variety=?, mintage=?, is_proof=?, designer=?, obv_desc=?, rev_desc=?
                          WHERE id=?
                        """, (int(e_year), _norm_text(e_mint), _norm_text(e_var),
                                int(e_mintage) if e_mintage else None, 1 if e_proof else 0,
                                _norm_text(e_des), _norm_text(e_obv), _norm_text(e_rev), row["id"]))
                    st.success("Saved.")
                except sqlite3.IntegrityError:
                    st.error("Unique conflict: another type already uses that master/year/mint/variety.")
                except Exception as e:
                    st.error(str(e))

            with st.expander("Dangerous actions"):
                st.caption("Delete this coin type (no lots can reference it)." )
                if st.button("Delete coin type", type="secondary", key="ct_del_admin"):
                    try:
                        with get_conn() as cx:
                            cx.execute("DELETE FROM coin_type WHERE id=?", (row["id"],))
                        st.success("Deleted coin type.")
                        try: st.rerun()
                        except Exception: pass
                    except sqlite3.IntegrityError:
                        st.error("Cannot delete: transactions/lots reference this type.")

# ------------------------------
# Guide Prices
# ------------------------------
with tab_guide:
    st.subheader("Guide Prices")
    trow = pick_coin_type("Coin Type", key="gp_type_pick")
    if trow:
        st.caption(f"Editing guide prices for: {_label_type(trow)}")
        rows = _load_guide_prices(trow["id"])
        if rows:
            import pandas as pd
            df = pd.DataFrame(rows)
            df = df.rename(columns={
                "grade_text":"Grade", "numeric_grade":"Numeric", "price_usd":"Price (USD)", "as_of":"As Of", "source":"Source"
            })
            if "Price (USD)" in df.columns:
                df["Price (USD)"] = pd.to_numeric(df["Price (USD)"], errors="coerce").map(lambda x: f"${x:,.2f}" if pd.notna(x) else "")
            if "Numeric" in df.columns:
                df["Numeric"] = pd.to_numeric(df["Numeric"], errors="coerce").map(lambda x: f"{x:.1f}" if pd.notna(x) else "")
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No guide prices yet for this type.")

        st.markdown("---")
        st.markdown("**Add a guide price**")
        c1, c2, c3, c4 = st.columns(4)
        grade_text = c1.text_input("Grade (e.g., AU50, MS65, PR70DCAM)", key="gp_grade")
        numeric    = c2.number_input("Numeric (optional)", min_value=0.0, step=0.5, value=0.0, key="gp_num")
        price_usd  = c3.number_input("Price USD", min_value=0.0, step=0.01, value=0.0, key="gp_price")
        as_of      = c4.date_input("As of", value=date.today(), key="gp_asof")
        src        = st.text_input("Source (optional)", key="gp_src")
        if st.button("Add Guide Price", type="primary", key="gp_add"):
            if not grade_text or price_usd <= 0:
                st.error("Grade and positive price are required.")
            else:
                try:
                    with get_conn() as cx:
                        cx.execute("""
                           INSERT INTO guide_price(coin_type_id, grade_text, numeric_grade, price_usd, as_of, source)
                           VALUES (?,?,?,?,?,?)
                        """, (trow["id"], grade_text.strip().upper(),
                                float(numeric) if numeric else None, float(price_usd), as_of.isoformat(), _norm_text(src) or None))
                    st.success("Guide price added.")
                    try: st.rerun()
                    except Exception: pass
                except sqlite3.IntegrityError:
                    st.error("A guide price for this grade/date already exists.")

# ------------------------------
# Metal Prices
# ------------------------------
with tab_prices:
    st.subheader("Metal Prices (Spot/Futures)")
    rows = _latest_spot_rows()
    if rows:
        import pandas as pd
        df = pd.DataFrame(rows).rename(columns={"metal":"Metal","price_per_oz_usd":"Price per oz (USD)","quoted_at_utc":"Quoted (UTC)"})
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No metal prices yet.")

    st.markdown("---")
    st.markdown("**Add price manually**")
    c1, c2, c3 = st.columns(3)
    metal = c1.selectbox("Metal", ["Ag","Au","Pt","Pd"], index=0, key="mp_metal")
    price = c2.number_input("Price per oz (USD)", min_value=0.0, step=0.01, value=0.0, key="mp_price")
    when  = c3.text_input("Quoted at (UTC, auto if blank)", value="", key="mp_when")
    if st.button("Add metal price", type="primary", key="mp_add"):
        quoted_at = when.strip() or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with get_conn() as cx:
            cx.execute("INSERT INTO metal_price(metal, price_per_oz_usd, quoted_at_utc) VALUES (?,?,?)", (metal, float(price), quoted_at))
        st.success("Metal price added.")
        try: st.rerun()
        except Exception: pass

    st.markdown("**Fetch from Yahoo Finance (if yfinance installed)**")
    st.caption("Mappings used: Au→GC=F, Ag→SI=F, Pt→PL=F, Pd→PA=F")
    if st.button("Fetch latest", key="mp_fetch"):
        try:
            import yfinance as yf
            mapping = {"Au":"GC=F", "Ag":"SI=F", "Pt":"PL=F", "Pd":"PA=F"}
            wrote = 0
            for metal, ticker in mapping.items():
                try:
                    info = yf.Ticker(ticker).info
                    price = info.get("regularMarketPrice") or info.get("lastPrice") or info.get("currentPrice")
                    if price:
                        with get_conn() as cx:
                            cx.execute("INSERT INTO metal_price(metal, price_per_oz_usd, quoted_at_utc) VALUES (?,?,?)",
                                       (metal, float(price), datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))
                        wrote += 1
                except Exception:
                    continue
            if wrote:
                st.success(f"Fetched {wrote} price(s)." )
                try: st.rerun()
                except Exception: pass
            else:
                st.warning("No prices fetched. Check network or ticker availability.")
        except Exception as e:
            st.error("yfinance not available or failed to fetch. Add 'yfinance' to requirements.txt and redeploy.")

# ------------------------------
# Void Tools
# ------------------------------
with tab_void:
    st.subheader("Void Entire Transaction")
    st.caption("Deletes a transaction and all its lines and lot effects. Use with care.")
    tx_id = st.number_input("Transaction ID to void", min_value=1, step=1, value=1, key="void_tx_id")
    confirm = st.checkbox("I understand this cannot be undone.", key="void_confirm")
    if st.button("Void Transaction", type="primary", disabled=not confirm, key="void_btn"):
        try:
            with get_conn() as cx:
                row = cx.execute("SELECT id FROM tx WHERE id=?", (int(tx_id),)).fetchone()
                if not row:
                    st.error("No such transaction.")
                else:
                    cx.execute("DELETE FROM tx WHERE id=?", (int(tx_id),))
                    st.success(f"Transaction #{int(tx_id)} voided.")
        except Exception as e:
            st.error(str(e))

# ------------------------------
# Delete Lot
# ------------------------------
with tab_delete:
    st.subheader("Delete a Lot (Admin)")
    lot_id = pick_lot("Lot to delete", key="del_lot_pick", only_open=False)
    confirm = st.checkbox("I understand this cannot be undone.", key="del_lot_confirm")
    if st.button("Delete Lot", type="primary", disabled=(not lot_id or not confirm), key="del_lot_btn"):
        try:
            with get_conn() as cx:
                cx.execute("DELETE FROM lot WHERE id=?", (int(lot_id),))
            st.success("Lot deleted.")
            try: st.rerun()
            except Exception: pass
        except sqlite3.IntegrityError:
            st.error("Cannot delete: lot is referenced by sales (lot_relief). Void those first.")
        except Exception as e:
            st.error(str(e))

# ------------------------------
# Reset DB (Danger Zone)
# ------------------------------
with tab_reset:
    st.subheader("Reset Database (Danger Zone)" )
    st.warning("This will DELETE all your data and re-create an empty database. Make a backup first!", icon="⚠️")

    # Offer quick backup download
    if _Path(DB_PATH).exists():
        try:
            with open(DB_PATH, "rb") as fh:
                st.download_button("Download backup (coinapp.sqlite)", data=fh.read(), file_name="coinapp.sqlite.bak", mime="application/octet-stream", key="db_backup_dl")
        except Exception as e:
            st.caption(f"Backup read failed: {e}")

    colA, colB = st.columns([2,1])
    typed = colA.text_input("Type RESET to confirm", key="db_reset_text")
    really = colB.checkbox("Yes, I understand", key="db_reset_ck" )

    def _hard_reset_in_place():
        # Robustly drop views, triggers, and tables even if other sessions hold the file open.
        with get_conn() as cx:
            cx.execute("PRAGMA foreign_keys=OFF;")
            # Drop views first
            for (name,) in cx.execute("SELECT name FROM sqlite_master WHERE type='view' AND name NOT LIKE 'sqlite_%';").fetchall():
                try:
                    cx.execute(f"DROP VIEW IF EXISTS {name};")
                except Exception:
                    pass
            # Drop triggers
            for (name,) in cx.execute("SELECT name FROM sqlite_master WHERE type='trigger';").fetchall():
                try:
                    cx.execute(f"DROP TRIGGER IF EXISTS {name};")
                except Exception:
                    pass
            # Drop tables
            for (name,) in cx.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';").fetchall():
                try:
                    cx.execute(f"DROP TABLE IF EXISTS {name};")
                except Exception:
                    pass
            cx.execute("VACUUM;")
            cx.execute("PRAGMA foreign_keys=ON;")
        # Recreate schema
        init_db()

    if st.button("Erase & Reinitialize DB", type="primary", disabled=not (really and typed.strip().upper() == "RESET"), key="db_reset_btn"):
        try:
            _hard_reset_in_place()
            try:
                st.cache_data.clear()
            except Exception:
                pass
            try:
                st.cache_resource.clear()
            except Exception:
                pass
            st.success("Database has been reset. Reloading...")
            try: st.rerun()
            except Exception: pass
        except Exception as e:
            st.error(f"Reset failed: {e}")
