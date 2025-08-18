
# pages/7_Specimens.py
import streamlit as st
import pandas as pd

st.header("🏷️ Specimens (Flip IDs)")

# Import specimen helpers (requires updated queries.py)
try:
    from queries import (
        get_specimen_by_code,
        list_specimens_on_hand,
        create_specimens_for_lot,
        upsert_series_code,
        list_lots,
    )
    from db import get_conn
    HAVE_SPECIMEN = True
except Exception as e:
    HAVE_SPECIMEN = False
    IMPORT_ERR = str(e)

if not HAVE_SPECIMEN:
    st.error("This page requires the updated schema_sql.py and queries.py with Specimen support. "
             "Please replace those files with the latest versions, then restart Streamlit.\n\n"
             f"Import error: {IMPORT_ERR}")
    st.stop()

# ---------- Low-level helpers (local) ----------

def _count_specimens_for_lot(lot_id: int) -> int:
    with get_conn() as cx:
        row = cx.execute("SELECT COUNT(*) AS n FROM specimen WHERE lot_id=?", (lot_id,)).fetchone()
        return int(row["n"] or 0)

def _create_specific_codes_for_lot(lot_id: int, codes):
    created, errors = [], []
    codes = [c.strip().upper() for c in codes if str(c).strip()]
    if not codes:
        return created, ["No codes provided."]
    with get_conn() as cx:
        r = cx.execute("SELECT coin_type_id FROM lot WHERE id=?", (lot_id,)).fetchone()
        if not r:
            return created, [f"Unknown lot_id {lot_id}"]
        coin_type_id = r["coin_type_id"]
        for code in codes:
            # prevent duplicates
            exists = cx.execute("SELECT 1 FROM specimen WHERE code=?", (code,)).fetchone()
            if exists:
                errors.append(f"{code} already exists.")
                continue
            cx.execute("INSERT INTO specimen(code, coin_type_id, lot_id) VALUES (?,?,?)",
                       (code, coin_type_id, lot_id))
            created.append(code)
    return created, errors

def _update_specimen(old_code: str, new_code: str = None, new_lot_id: int = None, notes: str = None):
    with get_conn() as cx:
        row = cx.execute("SELECT id, sold_line_id FROM specimen WHERE code=?", (old_code,)).fetchone()
        if not row:
            return False, "Specimen not found."
        if new_code:
            exists = cx.execute("SELECT 1 FROM specimen WHERE code=?", (new_code,)).fetchone()
            if exists:
                return False, "The new code already exists."
        sets, params = [], []
        if new_code:
            sets.append("code=?"); params.append(new_code)
        if new_lot_id is not None:
            # Optional safety: don't allow moving sold specimens
            if row["sold_line_id"] is not None:
                return False, "Cannot move a sold specimen."
            sets.append("lot_id=?"); params.append(new_lot_id)
        if notes is not None:
            sets.append("notes=?"); params.append(notes)
        if not sets:
            return True, "Nothing to update."
        params.append(row["id"])
        cx.execute(f"UPDATE specimen SET {', '.join(sets)} WHERE id=?", params)
    return True, "Updated."

def _delete_specimen(code: str):
    with get_conn() as cx:
        row = cx.execute("SELECT sold_line_id FROM specimen WHERE code=?", (code,)).fetchone()
        if not row:
            return False, "Specimen not found."
        if row["sold_line_id"] is not None:
            return False, "Cannot delete a specimen that has been sold."
        cx.execute("DELETE FROM specimen WHERE code=?", (code,))
    return True, "Deleted."

# ---------------- Lookup by Flip Code ----------------
st.subheader("Lookup by Flip Code")
code = st.text_input("Flip code (e.g., P1, M23, CB7)", help="Codes are series prefix + sequence, like P17 for Peace Dollars.")

col_search, col_clear = st.columns([1,1])
if col_search.button("Search") and code:
    result = get_specimen_by_code(code.strip())
    if not result:
        st.warning(f"No specimen found for code '{code}'.")
    else:
        left, right = st.columns([2, 1])
        with left:
            st.write("**Details**")
            st.write({
                "Code": result.get("code"),
                "Series": result.get("series"),
                "Year": result.get("year"),
                "Mint Mark": result.get("mint_mark"),
                "Variety": result.get("variety"),
                "Status": result.get("status"),
                "Lot ID": result.get("lot_id"),
            })
        with right:
            st.success("Match found ✅")
if col_clear.button("Clear"):
    st.experimental_rerun()

st.divider()

# ---------------- Backfill / Add Flip IDs to Existing Lots ----------------
st.subheader("Add Flip IDs to Existing Lots")

lots = list_lots()
open_lots = [l for l in lots if (l.get("qty_remaining") or 0) > 0]
if not open_lots:
    st.info("No open lots found. Add a BUY transaction first.")
else:
    options = {
        f"[Lot {l['id']}] {l['series']} {l['year']} {l['mint_mark'] or ''}"
        f"{(' • ' + l['variety']) if l.get('variety') else ''} — on hand: {l['qty_remaining']}"
        : l['id'] for l in open_lots
    }
    label = st.selectbox("Choose lot", list(options.keys()), key="lot_select")
    lot_id = options[label]

    on_hand = next((l['qty_remaining'] for l in open_lots if l['id'] == lot_id), 0)
    existing = _count_specimens_for_lot(lot_id)
    needed = max(0, int(on_hand) - int(existing))

    c1, c2, c3 = st.columns(3)
    c1.metric("Qty on hand", on_hand)
    c2.metric("Specimens already assigned", existing)
    c3.metric("Missing flip IDs", needed)

    st.markdown("**Option A — Auto-create missing codes**")
    start_code = st.text_input("Optional: specify the first code (e.g., P101). Leave blank to auto-assign.", key="start_code_auto")
    if st.button(f"Auto-create {needed} code(s)", disabled=(needed == 0)):
        try:
            codes = create_specimens_for_lot(lot_id, needed, start_code.strip() or None)
            if codes:
                st.success(f"Created {len(codes)} code(s): " + ", ".join(codes[:20]) + (" ..." if len(codes) > 20 else ""))
            else:
                st.info("No codes created (nothing missing).")
        except Exception as e:
            st.error(str(e))

    st.markdown("---")
    st.markdown("**Option B — Paste specific codes**")
    pasted = st.text_area("Enter codes separated by commas or new lines", height=110, placeholder="P1, P2, P3, P4")
    if st.button("Create these codes"):
        raw = [x.strip() for x in pasted.replace(",", "\n").splitlines() if x.strip()]
        if not raw:
            st.error("Please enter at least one code.")
        else:
            # Don't allow creating more than what's missing
            if len(raw) > needed:
                st.warning(f"You entered {len(raw)} codes but only {needed} are missing. We'll create the first {needed}.")
                raw = raw[:needed]
            created, errors = _create_specific_codes_for_lot(lot_id, raw)
            if created:
                st.success(f"Created: {', '.join(created)}")
            if errors:
                st.warning("Some issues:")
                for e in errors:
                    st.write("• ", e)

st.divider()

# ---------------- Edit existing specimen ----------------
with st.expander("Edit / Move / Delete a Specimen"):
    edit_code = st.text_input("Existing code", placeholder="e.g., P12", key="edit_code")
    if st.button("Load"):
        rec = get_specimen_by_code(edit_code.strip())
        if not rec:
            st.error("Not found.")
        else:
            st.session_state["_rec"] = rec

    rec = st.session_state.get("_rec")
    if rec:
        st.write("**Current**")
        st.write(rec)

        # Prepare lot options (same coin_type only)
        with get_conn() as cx:
            row = cx.execute("SELECT coin_type_id FROM specimen WHERE code=?", (rec["code"],)).fetchone()
            ct_id = row["coin_type_id"] if row else None
            lots_same_type = cx.execute("SELECT id, qty_remaining FROM lot WHERE coin_type_id=?",
                                        (ct_id,)).fetchall()
        lot_options = {f"Lot {r['id']} (on hand {r['qty_remaining']})": r["id"] for r in lots_same_type}

        new_code = st.text_input("New code (leave blank to keep)", key="new_code")
        new_lot_label = st.selectbox("Move to lot (optional)", ["(no change)"] + list(lot_options.keys()))
        new_lot_id = None if new_lot_label == "(no change)" else lot_options[new_lot_label]
        new_notes = st.text_input("Notes (optional)", key="new_notes")

        colA, colB, colC = st.columns(3)
        if colA.button("Save changes"):
            ok, msg = _update_specimen(rec["code"], new_code.strip().upper() or None, new_lot_id, new_notes if new_notes != "" else None)
            if ok:
                st.success(msg)
                st.session_state.pop("_rec", None)
            else:
                st.error(msg)
        if colB.button("Delete (if not sold)"):
            ok, msg = _delete_specimen(rec["code"])
            if ok:
                st.success(msg)
                st.session_state.pop("_rec", None)
            else:
                st.error(msg)
        if colC.button("Cancel"):
            st.session_state.pop("_rec", None)

st.divider()

# ---------------- Series Prefixes (optional) ----------------
with st.expander("Set / Update Series Prefix"):
    st.caption("Define the prefix used when auto-assigning codes (e.g., Peace → P, Morgan → M, Capped Bust → CB).")
    series = st.text_input("Series name (must match your 'series' exactly, e.g., 'Peace')")
    prefix = st.text_input("Prefix (1–3 letters)", placeholder="P, M, CB").upper().strip()
    if st.button("Save Prefix"):
        if not series or not prefix:
            st.error("Both Series and Prefix are required.")
        else:
            try:
                upsert_series_code(series.strip(), prefix[:3])
                st.success(f"Saved: {series.strip()} → {prefix[:3]}")
            except Exception as e:
                st.error(str(e))

# ---------------- Browse (optional) ----------------
with st.expander("Browse current specimens on hand"):
    flt = st.text_input("Filter by series (optional)", placeholder="e.g., Peace, Morgan")
    try:
        rows = list_specimens_on_hand(flt.strip() or None)
        if rows:
            df = pd.DataFrame(rows)
            df = df.rename(columns={"mint_mark": "Mint Mark"})
            st.dataframe(df)
        else:
            st.info("No specimens found (on hand).")
    except Exception as e:
        st.error(str(e))
