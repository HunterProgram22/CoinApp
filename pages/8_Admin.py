
# pages/8_Admin.py
import streamlit as st
import pandas as pd
import sqlite3

from db import get_conn
from queries import list_lots, list_storage_locations

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

tab_lot, tab_series, tab_storage = st.tabs(["Lots (grades & valuation)", "Series specs (for melt calc)", "Storage locations"])

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

render_admin_void_tool()
