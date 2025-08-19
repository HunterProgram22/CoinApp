# ---- ADMIN: DELETE LOT (safe) TOOL ----
# Paste this into pages/8_Admin.py (after imports) and call render_admin_delete_lot_tool()
# inside your Admin tabs, e.g.:
#   tab_catalog, tab_void, tab_maint = st.tabs(["Catalog", "Void Tx", "Maintenance"])
#   with tab_maint:
#       render_admin_delete_lot_tool()

import sqlite3
import pandas as pd
import streamlit as st
from db import get_conn

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