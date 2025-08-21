# pages/8_Admin.py
import streamlit as st
import pandas as pd
import sqlite3
from db import get_conn
from queries import list_lots, list_storage_locations, upsert_coin_master
import datetime as _dt

from patches.admin_coin_types_tab import render_admin_coin_types_tab



_METALS = [("Ag","Silver"), ("Au","Gold"), ("Pt","Platinum"), ("Pd","Palladium")]



def _now_utc_iso():
    return _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def _mp_insert(metal: str, price_per_oz: float, quoted_at_iso: str | None = None):
    if not quoted_at_iso:
        quoted_at_iso = _now_utc_iso()
    with get_conn() as cx:
        cx.execute(
            "INSERT INTO metal_price(metal, price_per_oz_usd, quoted_at_utc) VALUES (?,?,?)",
            (metal, float(price_per_oz), quoted_at_iso),
        )

def _mp_latest():
    with get_conn() as cx:
        rows = cx.execute("SELECT * FROM v_latest_spot").fetchall()
        return [dict(r) for r in rows]

def _mp_recent(limit: int = 100):
    with get_conn() as cx:
        rows = cx.execute(
            """
            SELECT metal, price_per_oz_usd, quoted_at_utc
            FROM metal_price
            ORDER BY quoted_at_utc DESC
            LIMIT ?
            """, (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

# -------- Live fetchers --------
def _fetch_yahoo_fast(metal_code: str) -> float | None:
    """Return last price in USD/oz using Yahoo Finance via yfinance ticker mapping.
    metal_code: 'Ag','Au','Pt','Pd'
    """
    try:
        import yfinance as yf  # requires: pip install yfinance
    except Exception:
        st.error("yfinance is not installed. In Command Prompt:  pip install yfinance")
        return None

    ticker_map = {
        "Au": "GC=F",
        "Ag": "SI=F",
        "Pt": "PL=F",
        "Pd": "PA=F",
    }
    tkr = ticker_map.get(metal_code)
    if not tkr:
        return None

    try:
        # Try fast_info first (quick)
        T = yf.Ticker(tkr)
        fi = getattr(T, "fast_info", None)
        if fi and isinstance(fi, dict) and fi.get("last_price"):
            return float(fi["last_price"])
        # Fallback: recent history
        h = T.history(period="1d", interval="1m")
        if h is not None and not h.empty:
            return float(h["Close"].dropna().iloc[-1])
        h2 = yf.download(tkr, period="1d")
        if h2 is not None and not h2.empty:
            return float(h2["Close"].dropna().iloc[-1])
    except Exception as e:
        st.error(f"Yahoo fetch failed for {metal_code}: {e}")
    return None

def _safe_rerun():
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()

def render_admin_metal_prices_tool():
    st.subheader("🧮 Metal Prices")
    st.caption("These drive melt valuation when a lot's valuation method is **MELT_ONLY**. Add manual prices or fetch live quotes.")

    # Latest snapshot
    latest = _mp_latest()
    if latest:
        st.write("**Latest spot (per oz, USD)**")
        df_latest = pd.DataFrame(latest)
        df_latest = df_latest.rename(columns={"metal":"Metal","price_per_oz_usd":"Price (USD/oz)"})
        st.dataframe(df_latest, use_container_width=True, hide_index=True)
    else:
        st.info("No metal prices yet. Add one below.")

    st.divider()

    # --- Manual add ---
    with st.form("mp_manual"):
        st.markdown("**Add Manual Price**")
        col1, col2, col3 = st.columns([1,1,2])
        m = col1.selectbox("Metal", [f"{code} — {name}" for code, name in _METALS])
        price = col2.number_input("Price (USD/oz)", min_value=0.0, step=0.01)
        when_iso = col3.text_input("Quoted at (UTC, ISO 8601)", value=_now_utc_iso())
        do_add = st.form_submit_button("Add price", type="primary")
        if do_add:
            code = m.split(" — ", 1)[0]
            try:
                _mp_insert(code, float(price), when_iso.strip() or None)
                st.success(f"Added {code} @ ${price:.4f} ({when_iso}).")
                _safe_rerun()
            except Exception as e:
                st.error(f"Insert failed: {e}")

    st.divider()

    # --- Live fetch ---
    st.markdown("**Fetch Live Quotes (Yahoo Finance via yfinance)**")
    colA, _ = st.columns([2,1])
    metals_pick = colA.multiselect(
        "Select metals to fetch",
        [f"{code} — {name}" for code, name in _METALS],
        default=[f"{code} — {name}" for code, name in _METALS[:2]]  # default Au/Ag
    )
    if st.button("Fetch & Insert Live Quotes"):
        missing = []
        for label in metals_pick:
            code = label.split(" — ", 1)[0]
            px = _fetch_yahoo_fast(code)
            if px is None:
                missing.append(code)
                continue
            _mp_insert(code, px, _now_utc_iso())
            st.success(f"{code}: inserted live price ${px:.4f}")
        if missing:
            st.warning("No price for: " + ", ".join(missing))

    # Recent table
    rec = _mp_recent(100)
    if rec:
        st.write("**Recent quotes (latest 100)**")
        dfr = pd.DataFrame(rec).rename(columns={"metal":"Metal","price_per_oz_usd":"Price (USD/oz)","quoted_at_utc":"Quoted (UTC)"})
        st.dataframe(dfr, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.caption("Quick links:")
    st.link_button("LBMA Prices", "https://www.lbma.org.uk/prices-and-data")
    st.link_button("CME Group Metals", "https://www.cmegroup.com/markets/metals.html")
    st.link_button("Yahoo Finance XAUUSD", "https://finance.yahoo.com/quote/XAUUSD%3DX")
    st.link_button("Yahoo Finance XAGUSD", "https://finance.yahoo.com/quote/XAGUSD%3DX")
# ---- END ADMIN: METAL PRICES ----


def _admin_del_safe_rerun():
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()

def _admin_del_fetch_lot_candidates():
    sql = '''
    SELECT
      l.id,
      l.acquired_date,
      l.qty_acquired,
      l.qty_remaining,
      cm.series,
      ct.year,
      ct.mint_mark,
      COALESCE(ct.variety,'') AS variety,
      (SELECT COUNT(*) FROM lot_relief lr WHERE lr.lot_id = l.id) AS relief_cnt,
      (SELECT COUNT(*) FROM specimen s  WHERE s.lot_id = l.id)   AS specimen_cnt
    FROM lot l
    JOIN coin_type ct ON ct.id = l.coin_type_id
    JOIN coin_master cm ON cm.id = ct.master_id
    ORDER BY l.acquired_date DESC, l.id DESC
    '''
    with get_conn() as cx:
        return [dict(r) for r in cx.execute(sql).fetchall()]

def _admin_del_can_delete(row):
    reasons = []
    if row['qty_remaining'] != row['qty_acquired']:
        reasons.append("some coins already sold/relieved")
    if row['relief_cnt'] > 0:
        reasons.append("linked to sales (lot_relief)")
    if row['specimen_cnt'] > 0:
        reasons.append("has specimens attached")
    return (len(reasons) == 0), reasons

def _admin_del_delete_lot(lot_id: int):
    # Delete the BUY line that created this lot; ON DELETE CASCADE removes the lot.
    with get_conn() as cx:
        row = cx.execute("SELECT acquisition_line_id FROM lot WHERE id=?", (lot_id,)).fetchone()
        if not row:
            raise RuntimeError("Lot not found")
        line_id = row["acquisition_line_id"]
        tx_id_row = cx.execute("SELECT tx_id FROM tx_line WHERE id=?", (line_id,)).fetchone()
        if not tx_id_row:
            raise RuntimeError("Source tx_line not found")
        tx_id = tx_id_row["tx_id"]

        # Safety re-checks just before delete
        rel = cx.execute("SELECT COUNT(*) AS c FROM lot_relief WHERE lot_id=?", (lot_id,)).fetchone()["c"]
        spec = cx.execute("SELECT COUNT(*) AS c FROM specimen WHERE lot_id=?", (lot_id,)).fetchone()["c"]
        qa, qr = cx.execute("SELECT qty_acquired, qty_remaining FROM lot WHERE id=?", (lot_id,)).fetchone()
        if rel or spec or qa != qr:
            raise RuntimeError("Lot is no longer eligible for deletion (changed while you were viewing). Refresh and try again.")

        cx.execute("DELETE FROM tx_line WHERE id=?", (line_id,))  # cascades to delete lot
        # Remove parent tx if empty
        left = cx.execute("SELECT COUNT(*) AS c FROM tx_line WHERE tx_id=?", (tx_id,)).fetchone()["c"]
        if left == 0:
            cx.execute("DELETE FROM tx WHERE id=?", (tx_id,))

def render_admin_delete_lot_tool():
    st.subheader("🧹 Maintenance — Delete a Lot (safe)")
    st.caption("Delete a lot that was added by mistake. Only allowed if the lot has no sales, no attached specimens, and the full quantity remains.")

    cands = _admin_del_fetch_lot_candidates()
    if not cands:
        st.caption("No lots found.")
        return

    # Show only the most recent 100 for convenience
    dfc = pd.DataFrame(cands[:100])
    deletable = []
    reasons_list = []
    for _, r in dfc.iterrows():
        ok, reasons = _admin_del_can_delete(r.to_dict())
        deletable.append(ok)
        reasons_list.append("; ".join(reasons))
    dfc['Deletable'] = deletable
    dfc['Reason (if blocked)'] = reasons_list

    nice_cols = ['id','acquired_date','series','year','mint_mark','variety','qty_acquired','qty_remaining','Deletable','Reason (if blocked)']
    st.dataframe(dfc[nice_cols], use_container_width=True, hide_index=True)

    with st.form("admin_delete_lot_form", clear_on_submit=False):
        lot_id_in = st.number_input("Lot ID to delete", min_value=1, step=1)
        confirm = st.checkbox("I understand this permanently removes the lot and its BUY line.")
        submitted = st.form_submit_button("Delete lot", type="primary")
        if submitted:
            row = next((r for r in cands if r['id'] == int(lot_id_in)), None)
            if not row:
                st.error("That Lot ID isn't in the table above (or outside the first 100 rows shown).")
            else:
                ok, reasons = _admin_del_can_delete(row)
                if not ok:
                    st.error("Cannot delete this lot: " + "; ".join(reasons))
                elif not confirm:
                    st.warning("Please check the confirmation box.")
                else:
                    try:
                        _admin_del_delete_lot(int(lot_id_in))
                        st.success(f"Deleted lot #{int(lot_id_in)}.")
                        _admin_del_safe_rerun()
                    except Exception as e:
                        st.error(str(e))
# ---- END ADMIN: DELETE LOT (safe) TOOL ----

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
def _admin_void_safe_rerun():
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()

def _admin_void_recent_transactions(limit: int = 200):
    sql = '''
    SELECT t.id, t.tx_date, t.tx_type, COALESCE(p.name,'') AS party,
           (SELECT COUNT(*) FROM tx_line tl WHERE tl.tx_id = t.id) AS line_count
    FROM tx t
    LEFT JOIN party p ON p.id = t.party_id
    ORDER BY t.tx_date DESC, t.id DESC
    LIMIT ?
    '''
    with get_conn() as cx:
        return [dict(r) for r in cx.execute(sql, (limit,)).fetchall()]

def _admin_void_buy_blockers(tx_id: int):
    """Reasons a BUY cannot be voided (empty list => OK)."""
    reasons = []
    with get_conn() as cx:
        rows = cx.execute('''
            SELECT l.id AS lot_id, l.qty_acquired, l.qty_remaining,
                   (SELECT COUNT(*) FROM lot_relief lr WHERE lr.lot_id = l.id) AS relief_cnt,
                   (SELECT COUNT(*) FROM specimen s   WHERE s.lot_id = l.id) AS specimen_cnt
            FROM lot l
            JOIN tx_line tl ON tl.id = l.acquisition_line_id
            WHERE tl.tx_id = ?
        ''', (tx_id,)).fetchall()
        for r in rows:
            if r["qty_remaining"] != r["qty_acquired"]:
                reasons.append(f"Lot #{r['lot_id']} has sales (qty remaining != acquired)")
            if r["relief_cnt"] > 0:
                reasons.append(f"Lot #{r['lot_id']} is referenced by lot_relief")
            if r["specimen_cnt"] > 0:
                reasons.append(f"Lot #{r['lot_id']} has specimens attached")
    return reasons

def _admin_void_sell_info(tx_id: int):
    with get_conn() as cx:
        row = cx.execute('''
            SELECT COUNT(*) AS relief_rows
            FROM lot_relief lr
            JOIN tx_line tl ON tl.id = lr.sell_line_id
            WHERE tl.tx_id = ?
        ''', (tx_id,)).fetchone()
        return dict(row) if row else {"relief_rows": 0}

def _admin_void_transaction(tx_id: int) -> tuple[bool, str]:
    with get_conn() as cx:
        tx = cx.execute("SELECT id, tx_type FROM tx WHERE id=?", (tx_id,)).fetchone()
        if not tx:
            return False, "Transaction not found."
        tx_type = tx["tx_type"]

        if tx_type == "BUY":
            reasons = _admin_void_buy_blockers(tx_id)
            if reasons:
                return False, "Not allowed to void BUY: " + "; ".join(reasons)

        try:
            cx.execute("DELETE FROM tx WHERE id=?", (tx_id,))
        except Exception as e:
            return False, f"Failed to void: {e!s}"
        return True, f"Transaction #{tx_id} ({tx_type}) voided."

def render_admin_void_tool():
    st.subheader("⚠️ Void Entire Transaction (safe)")
    st.caption(
        "Use this to remove a transaction you added by mistake. "
        "BUY: only if none of its lots were relieved (sold) and no specimens are attached. "
        "SELL: will remove sell lines and restore quantities to the original lots."
    )

    txs = _admin_void_recent_transactions(200)
    if not txs:
        st.info("No transactions yet.")
        return

    # Compute voidability & notes
    voidable, notes = [], []
    for t in txs:
        if t["tx_type"] == "BUY":
            r = _admin_void_buy_blockers(t["id"])
            voidable.append(len(r) == 0)
            notes.append("; ".join(r))
        elif t["tx_type"] == "SELL":
            info = _admin_void_sell_info(t["id"])
            voidable.append(True)
            notes.append(f"{info.get('relief_rows', 0)} lot relief rows will be removed; quantities restored")
        else:
            voidable.append(True)
            notes.append("")

    import pandas as pd
    df = pd.DataFrame(txs)
    df.insert(3, "Party", df.pop("party"))
    df["Voidable"] = voidable
    df["Notes"] = notes
    df = df.rename(columns={"id":"Tx ID","tx_date":"Date","tx_type":"Type","line_count":"Lines"})
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.write("")
    with st.form("admin_void_tx_form", clear_on_submit=False):
        tx_id = st.number_input("Transaction ID to void", min_value=1, step=1)
        confirm = st.checkbox("I understand this will permanently remove the transaction and any dependent objects.")
        submit = st.form_submit_button("Void Transaction", type="primary")
        if submit:
            if not confirm:
                st.warning("Please check the confirmation box.")
            else:
                ok, msg = _admin_void_transaction(int(tx_id))
                if ok:
                    st.success(msg)
                    _admin_void_safe_rerun()
                else:
                    st.error(msg)
# ---- END VOID ENTIRE TRANSACTION ----
st.header("🛠️ Admin")

tab_coin_editor, tab_coin_types, tab_lot, tab_series, tab_storage, tab_void, tab_maint, tab_prices = (
    st.tabs(
        [
            "Coin Master Editor",
            "Coin Types"
            "Lots (grades & valuation)",
            "Series specs (for melt calc)",
            "Storage locations",
            "Void Transaction Tool",
            "Delete Lot Tool",
            "Metal Prices",
        ]
    ))

# -------------------- COIN EDITOR -------------------
with tab_coin_editor:
    render_catalog_coin_master_editor()

with tab_coin_types:
    render_admin_coin_types_tab()
# -------------------- LOT EDITOR --------------------
with tab_lot:
    st.caption("Edit grades, valuation method, manual value, storage, and notes for a specific lot.")

    lots = list_lots()
    if not lots:
        st.info("No lots found. Add a BUY transaction first.")
    else:
        display = {
            f"[Lot {l['id']}] {l['series']} {l['year']} {l['mint_mark'] or ''}"
            f"{(' • ' + l['variety']) if l.get('variety') else ''} — on hand: {l['qty_remaining']}"
            : l['id'] for l in lots
        }
        sel = st.selectbox("Choose lot", list(display.keys()), key="admin_lot_sel")
        lot_id = display[sel]

        # Load full lot details
        with get_conn() as cx:
            row = cx.execute(
                """
                SELECT id, coin_type_id, acquired_date, qty_acquired, qty_remaining, unit_cost,
                       storage_location_id,
                       purchase_grade_company, purchase_grade_text, purchase_numeric_grade, slab_cert,
                       estimated_grade_text, estimated_numeric_grade,
                       valuation_method, manual_est_unit_value, status, notes
                FROM lot WHERE id = ?
                """,
                (lot_id,)
            ).fetchone()

            # also fetch coin type label
            ct = cx.execute("""
                SELECT cm.series, ct.year, ct.mint_mark, COALESCE(ct.variety,'') AS variety
                FROM coin_type ct JOIN coin_master cm ON cm.id = ct.master_id
                WHERE ct.id = ?
            """, (row["coin_type_id"],)).fetchone()

        st.subheader(f"Lot {row['id']} — {ct['series']} {ct['year']} {ct['mint_mark'] or ''}{(' • ' + ct['variety']) if ct['variety'] else ''}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Acquired", row["qty_acquired"])
        c2.metric("On hand", row["qty_remaining"])
        c3.metric("Unit cost", f"${row['unit_cost']:.2f}")
        c4.metric("Status", row["status"])

        with st.form("edit_lot_form", clear_on_submit=False):
            colA, colB = st.columns(2)
            est_grade_text = colA.text_input("Estimated Grade Text", value=row["estimated_grade_text"] or "")
            est_grade_num = colB.number_input("Estimated Numeric Grade", min_value=0.0, step=0.5, value=float(row["estimated_numeric_grade"] or 0.0))

            val_method = colA.selectbox("Valuation Method", ["AUTO","MELT_ONLY","GUIDE_ONLY","MANUAL"], index=["AUTO","MELT_ONLY","GUIDE_ONLY","MANUAL"].index(row["valuation_method"] or "AUTO"))
            manual_val = colB.number_input("Manual Unit Value (if MANUAL)", min_value=0.0, step=0.01, value=float(row["manual_est_unit_value"] or 0.0))

            # Storage
            stor = list_storage_locations()
            if stor:
                options = {"(none)": None}
                options.update({f"{s['name']} ({s['category']})".strip(): s["id"] for s in stor})
                current_key = next((k for k, v in options.items() if v == row["storage_location_id"]), "(none)")
                storage_label = st.selectbox("Storage Location", list(options.keys()), index=list(options.keys()).index(current_key))
                storage_id = options[storage_label]
            else:
                storage_id = None
                st.info("No storage locations yet. Add some in the Storage tab.")

            notes = st.text_area("Notes", value=row["notes"] or "", height=80)

            if st.form_submit_button("Save changes"):
                with get_conn() as cx:
                    cx.execute(
                        """
                        UPDATE lot
                        SET estimated_grade_text = ?, estimated_numeric_grade = ?,
                            valuation_method = ?, manual_est_unit_value = ?,
                            storage_location_id = ?, notes = ?
                        WHERE id = ?
                        """,
                        (
                            est_grade_text or None,
                            float(est_grade_num) if est_grade_num else None,
                            val_method,
                            float(manual_val) if manual_val else None,
                            storage_id,
                            notes or None,
                            lot_id,
                        )
                    )
                st.success("Lot updated.")

# -------------------- SERIES SPECS EDITOR (coin_master) --------------------
with tab_series:
    st.caption("Edit per-series physical specs that drive melt value calculations.")
    # List series
    with get_conn() as cx:
        cm_rows = cx.execute("""
            SELECT id, country, denomination, series, metal, fineness, weight_grams, diameter_mm, thickness_mm, edge, notes
            FROM coin_master ORDER BY country, denomination, series
        """).fetchall()

    if not cm_rows:
        st.info("No series yet. Add some by creating coin types (BUY/import) or from Settings.")
    else:
        labels = {
            f"{r['country']} • {r['denomination']} • {r['series']}": r["id"]
            for r in cm_rows
        }
        label = st.selectbox("Choose series", list(labels.keys()), key="admin_series_sel")
        cm_id = labels[label]
        row = next(r for r in cm_rows if r["id"] == cm_id)

        with st.form("edit_series_form"):
            col1, col2, col3 = st.columns(3)
            metal = col1.text_input("Metal (e.g., Ag, Au, Pt, CuNi)", value=row["metal"] or "")
            fineness = col2.number_input("Fineness (e.g., 0.900)", min_value=0.0, max_value=1.0, step=0.001, value=float(row["fineness"] or 0.0))
            weight = col3.number_input("Weight (grams per coin)", min_value=0.0, step=0.001, value=float(row["weight_grams"] or 0.0))

            col4, col5, col6 = st.columns(3)
            diameter = col4.number_input("Diameter (mm)", min_value=0.0, step=0.01, value=float(row["diameter_mm"] or 0.0))
            thickness = col5.number_input("Thickness (mm)", min_value=0.0, step=0.01, value=float(row["thickness_mm"] or 0.0))
            edge = col6.text_input("Edge", value=row["edge"] or "")

            notes = st.text_area("Notes", value=row["notes"] or "", height=80)

            if st.form_submit_button("Save series specs"):
                with get_conn() as cx:
                    cx.execute(
                        """
                        UPDATE coin_master
                        SET metal=?, fineness=?, weight_grams=?, diameter_mm=?, thickness_mm=?, edge=?, notes=?
                        WHERE id = ?
                        """,
                        (metal or None,
                         float(fineness) if fineness else None,
                         float(weight) if weight else None,
                         float(diameter) if diameter else None,
                         float(thickness) if thickness else None,
                         edge or None,
                         cm_id)
                    )
                st.success("Series specs updated. Melt valuations will reflect new values.")

# -------------------- STORAGE MANAGER --------------------
with tab_storage:
    st.caption("Add or update storage locations.")
    # List current
    rows = list_storage_locations()
    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df.rename(columns={"id":"ID","name":"Name","category":"Category"}), use_container_width=True)
    else:
        st.info("No storage locations yet. Use the form below to add one.")

    st.subheader("Add new")
    with st.form("add_storage_form", clear_on_submit=True):
        name = st.text_input("Name", placeholder="Safe A - Tray 2")
        category = st.text_input("Category", placeholder="Home Safe / Bank / Album / Tube")
        description = st.text_input("Description", placeholder="Optional")
        if st.form_submit_button("Add"):
            if not name.strip():
                st.error("Name is required.")
            else:
                with get_conn() as cx:
                    # If exists, update instead
                    row = cx.execute("SELECT id FROM storage_location WHERE name=?", (name.strip(),)).fetchone()
                    if row:
                        cx.execute("UPDATE storage_location SET category=?, description=? WHERE id=?",
                                   (category or None, description or None, row["id"]))
                        st.success(f"Updated existing storage '{name.strip()}'")
                    else:
                        cx.execute("INSERT INTO storage_location(name, category, description) VALUES (?,?,?)",
                                   (name.strip(), category or None, description or None))
                        st.success(f"Added storage '{name.strip()}'")

    st.subheader("Edit existing")
    if rows:
        names = {f"{r['name']} ({r['category']})".strip(): r for r in rows}
        pick = st.selectbox("Select storage", list(names.keys()))
        rec = names[pick]
        with st.form("edit_storage_form"):
            new_name = st.text_input("Name", value=rec["name"])
            new_cat = st.text_input("Category", value=rec.get("category") or "")
            new_desc = st.text_input("Description", value=rec.get("description") or "")
            if st.form_submit_button("Save storage"):
                with get_conn() as cx:
                    # Ensure unique by name
                    exists = cx.execute("SELECT id FROM storage_location WHERE name=? AND id<>?", (new_name.strip(), rec["id"])).fetchone()
                    if exists:
                        st.error("Another storage with that name already exists.")
                    else:
                        cx.execute("UPDATE storage_location SET name=?, category=?, description=? WHERE id=?",
                                   (new_name.strip(), new_cat or None, new_desc or None, rec["id"]))
                        st.success("Storage updated.")

# render_catalog_coin_master_editor()
with tab_void:
    render_admin_void_tool()

with tab_maint:
    render_admin_delete_lot_tool()

with tab_prices:
    render_admin_metal_prices_tool()
