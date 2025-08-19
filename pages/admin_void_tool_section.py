# ---- VOID ENTIRE TRANSACTION (safe) ----
# Paste this near the top of pages/8_Admin.py (after your imports), or anywhere above where you call render_admin_void_tool().
import sqlite3
import pandas as pd
import streamlit as st
from db import get_conn

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