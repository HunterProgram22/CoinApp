# pages/3_Inventory.py
import streamlit as st
import pandas as pd
from queries import inventory_by_type, inventory_by_series_summary, list_lots
from db import get_conn

st.header("Inventory")

# --------------------- Views ---------------------
view = st.radio("View", ["By Type", "By Series (summary)"], horizontal=True)

if view == "By Type":
    inv = inventory_by_type()
    if inv:
        st.subheader("By Type")
        df = pd.DataFrame(inv)
        # Hide internal ID and put Series first
        if 'coin_type_id' in df.columns:
            df = df.drop(columns=['coin_type_id'])
        first_order = [c for c in ['series','year','mint_mark','variety','coins_on_hand'] if c in df.columns]
        df = df[first_order + [c for c in df.columns if c not in first_order]]
        # Friendly labels (minimal)
        rename = {
            'mint_mark': 'Mint Mark',
            'coins_on_hand': 'Qty on Hand',
            'series': 'Series',
            'year': 'Year',
        }
        df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No inventory yet.")
else:
    summary = inventory_by_series_summary()
    if summary:
        st.subheader("By Series — Summary")
        df = pd.DataFrame(summary)
        col_order = [c for c in ['series','coins','est_value_usd'] if c in df.columns]
        df = df[col_order + [c for c in df.columns if c not in col_order]]
        df = df.rename(columns={'series': 'Series', 'coins': 'Coins', 'est_value_usd': 'Est. Value (USD)'})
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No inventory yet.")

# Lots table (for context)
lots = list_lots()
if lots and view == "By Type":
    st.subheader("Lots")
    st.dataframe(pd.DataFrame(lots), use_container_width=True)

# --------------------- Maintenance ---------------------
st.divider()
st.subheader("🧹 Maintenance — Delete a Lot (safe)")
st.caption("Delete an inventory **lot** that was added by mistake. Only allowed if the lot has no sales, no attached specimens, and no quantity has been relieved.")

def _fetch_lot_candidates():
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

def _can_delete_lot(row):
    reasons = []
    if row['qty_remaining'] != row['qty_acquired']:
        reasons.append("some coins already sold/relieved")
    if row['relief_cnt'] > 0:
        reasons.append("linked to sales (lot_relief)")
    if row['specimen_cnt'] > 0:
        reasons.append("has specimens attached")
    return (len(reasons) == 0), reasons

def _delete_lot(lot_id: int):
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
        # If tx has no more lines, delete the tx header too
        left = cx.execute("SELECT COUNT(*) AS c FROM tx_line WHERE tx_id=?", (tx_id,)).fetchone()["c"]
        if left == 0:
            cx.execute("DELETE FROM tx WHERE id=?", (tx_id,))

cands = _fetch_lot_candidates()
if not cands:
    st.caption("No lots found.")
else:
    # Show only the most recent 100 for convenience
    dfc = pd.DataFrame(cands[:100])
    dfc['Deletable'] = dfc.apply(lambda r: _can_delete_lot(r)[0], axis=1)
    dfc['Reason (if blocked)'] = dfc.apply(lambda r: "; ".join(_can_delete_lot(r)[1]), axis=1)
    nice_cols = ['id','acquired_date','series','year','mint_mark','variety','qty_acquired','qty_remaining','Deletable','Reason (if blocked)']
    st.dataframe(dfc[nice_cols], use_container_width=True, hide_index=True)

    st.write("")
    with st.form("delete_lot_form", clear_on_submit=False):
        lot_id_in = st.number_input("Lot ID to delete", min_value=1, step=1)
        confirm = st.checkbox("I understand this permanently removes the lot and its BUY line.")
        submitted = st.form_submit_button("Delete lot", type="primary")
        if submitted:
            row = next((r for r in cands if r['id'] == int(lot_id_in)), None)
            if not row:
                st.error("That Lot ID isn't in the table above (or outside the first 100 rows shown).")
            else:
                ok, reasons = _can_delete_lot(row)
                if not ok:
                    st.error("Cannot delete this lot: " + "; ".join(reasons))
                elif not confirm:
                    st.warning("Please check the confirmation box.")
                else:
                    try:
                        _delete_lot(int(lot_id_in))
                        st.success(f"Deleted lot #{int(lot_id_in)}.")
                        try:
                            st.rerun()
                        except AttributeError:
                            st.experimental_rerun()
                    except Exception as e:
                        st.error(str(e))