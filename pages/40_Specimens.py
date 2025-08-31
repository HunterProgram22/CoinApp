# pages/40_Specimens.py
import streamlit as st
import pandas as pd
from typing import List, Tuple, Optional, Dict, Any
from db_operations import execute_query_all, execute_query_single, execute_insert, execute_update, \
    execute_delete
from queries import (
    get_specimen_by_code,
    get_specimens_on_hand,
    create_specimens_for_lot,
    create_or_update_series_code,
    get_all_lots,
)

st.header("🏷️ Specimens (Flip IDs)")


# ---------------------------------
# Data Access Functions
# ---------------------------------
def count_specimens_for_lot(lot_id: int) -> int:
    """Count specimens assigned to a specific lot."""
    query = "SELECT COUNT(*) AS count FROM specimen WHERE lot_id = ?"
    result = execute_query_single(query, (lot_id,))
    return result['count'] if result else 0


def create_specific_codes_for_lot(lot_id: int, codes: List[str]) -> Tuple[List[str], List[str]]:
    """Create specific specimen codes for a lot."""
    created = []
    errors = []

    # Clean and validate codes
    codes = [c.strip().upper() for c in codes if str(c).strip()]
    if not codes:
        return created, ["No codes provided."]

    # Get coin_type_id for the lot
    lot_query = "SELECT coin_type_id FROM lot WHERE id = ?"
    lot_result = execute_query_single(lot_query, (lot_id,))

    if not lot_result:
        return created, [f"Unknown lot_id {lot_id}"]

    coin_type_id = lot_result['coin_type_id']

    # Process each code
    for code in codes:
        # Check if code already exists
        exists_query = "SELECT 1 FROM specimen WHERE code = ?"
        exists = execute_query_single(exists_query, (code,))

        if exists:
            errors.append(f"{code} already exists.")
            continue

        # Create the specimen
        try:
            execute_insert(
                "INSERT INTO specimen(code, coin_type_id, lot_id) VALUES (?, ?, ?)",
                (code, coin_type_id, lot_id)
            )
            created.append(code)
        except Exception as e:
            errors.append(f"Error creating {code}: {str(e)}")

    return created, errors


def update_specimen(old_code: str, new_code: Optional[str] = None,
                    new_lot_id: Optional[int] = None, notes: Optional[str] = None) -> Tuple[
    bool, str]:
    """Update an existing specimen."""
    # Get current specimen
    query = "SELECT id, sold_line_id FROM specimen WHERE code = ?"
    specimen = execute_query_single(query, (old_code,))

    if not specimen:
        return False, "Specimen not found."

    # Check if new code already exists
    if new_code:
        exists = execute_query_single("SELECT 1 FROM specimen WHERE code = ?", (new_code,))
        if exists:
            return False, "The new code already exists."

    # Build update query
    updates = []
    params = []

    if new_code:
        updates.append("code = ?")
        params.append(new_code)

    if new_lot_id is not None:
        # Don't allow moving sold specimens
        if specimen['sold_line_id'] is not None:
            return False, "Cannot move a sold specimen."
        updates.append("lot_id = ?")
        params.append(new_lot_id)

    if notes is not None:
        updates.append("notes = ?")
        params.append(notes)

    if not updates:
        return True, "Nothing to update."

    # Execute update
    params.append(specimen['id'])
    update_query = f"UPDATE specimen SET {', '.join(updates)} WHERE id = ?"

    try:
        execute_update(update_query, tuple(params))
        return True, "Updated."
    except Exception as e:
        return False, f"Update failed: {str(e)}"


def delete_specimen(code: str) -> Tuple[bool, str]:
    """Delete a specimen if not sold."""
    # Check if specimen exists and is not sold
    query = "SELECT sold_line_id FROM specimen WHERE code = ?"
    specimen = execute_query_single(query, (code,))

    if not specimen:
        return False, "Specimen not found."

    if specimen['sold_line_id'] is not None:
        return False, "Cannot delete a specimen that has been sold."

    # Delete the specimen
    try:
        execute_delete("DELETE FROM specimen WHERE code = ?", (code,))
        return True, "Deleted."
    except Exception as e:
        return False, f"Delete failed: {str(e)}"


def get_lots_for_coin_type(coin_type_id: int) -> List[Dict[str, Any]]:
    """Get all lots for a specific coin type."""
    query = "SELECT id, qty_remaining FROM lot WHERE coin_type_id = ?"
    return execute_query_all(query, (coin_type_id,))


def get_coin_type_for_specimen(code: str) -> Optional[int]:
    """Get coin_type_id for a specimen."""
    query = "SELECT coin_type_id FROM specimen WHERE code = ?"
    result = execute_query_single(query, (code,))
    return result['coin_type_id'] if result else None


# ---------------------------------
# Helper Functions
# ---------------------------------
def format_lot_label(lot: Dict[str, Any]) -> str:
    """Format lot for display in selectbox."""
    label = f"[Lot {lot['id']}] {lot['series']} {lot['year']}"
    if lot.get('mint_mark'):
        label += f" {lot['mint_mark']}"
    if lot.get('variety'):
        label += f" • {lot['variety']}"
    label += f" — on hand: {lot['qty_remaining']}"
    return label


def parse_codes_input(text: str) -> List[str]:
    """Parse user input for specimen codes."""
    if not text:
        return []
    # Replace commas with newlines and split
    return [x.strip() for x in text.replace(",", "\n").splitlines() if x.strip()]


# ---------------------------------
# UI Components
# ---------------------------------
def render_lookup_section():
    """Render the specimen lookup section."""
    st.subheader("Lookup by Flip Code")

    code = st.text_input(
        "Flip code (e.g., P1, M23, CB7)",
        help="Codes are series prefix + sequence, like P17 for Peace Dollars.",
        key="lookup_code"
    )

    col_search, col_clear = st.columns([1, 1])

    if col_search.button("Search", key="lookup_search") and code:
        result = get_specimen_by_code(code.strip())

        if not result:
            st.warning(f"No specimen found for code '{code}'.")
        else:
            left, right = st.columns([2, 1])
            with left:
                st.write("**Details**")
                details = {
                    "Code": result.get("code"),
                    "Series": result.get("series"),
                    "Year": result.get("year"),
                    "Mint Mark": result.get("mint_mark") or "—",
                    "Variety": result.get("variety") or "—",
                    "Lot ID": result.get("lot_id"),
                }
                for key, value in details.items():
                    st.write(f"• **{key}:** {value}")
            with right:
                st.success("Match found ✅")

    if col_clear.button("Clear", key="lookup_clear"):
        st.rerun()


def render_add_flip_ids_section():
    """Render the section for adding flip IDs to lots."""
    st.subheader("Add Flip IDs to Existing Lots")

    lots = get_all_lots()
    open_lots = [l for l in lots if (l.get("qty_remaining") or 0) > 0]

    if not open_lots:
        st.info("No open lots found. Add a BUY transaction first.")
        return

    # Create lot selection
    options = {format_lot_label(l): l['id'] for l in open_lots}
    label = st.selectbox("Choose lot", list(options.keys()), key="lot_select")
    lot_id = options[label]

    # Get metrics for selected lot
    selected_lot = next(l for l in open_lots if l['id'] == lot_id)
    on_hand = selected_lot['qty_remaining']
    existing = count_specimens_for_lot(lot_id)
    needed = max(0, on_hand - existing)

    # Display metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Qty on hand", on_hand)
    c2.metric("Specimens already assigned", existing)
    c3.metric("Missing flip IDs", needed)

    # Option A: Auto-create
    st.markdown("**Option A — Auto-create missing codes**")
    start_code = st.text_input(
        "Optional: specify the first code (e.g., P101). Leave blank to auto-assign.",
        key="start_code_auto"
    )

    if st.button(f"Auto-create {needed} code(s)", disabled=(needed == 0), key="auto_create"):
        try:
            codes = create_specimens_for_lot(lot_id, needed, start_code.strip() or None)
            if codes:
                display_codes = codes[:20]
                suffix = " ..." if len(codes) > 20 else ""
                st.success(f"Created {len(codes)} code(s): " + ", ".join(display_codes) + suffix)
            else:
                st.info("No codes created (nothing missing).")
        except Exception as e:
            st.error(str(e))

    st.markdown("---")

    # Option B: Paste specific codes
    st.markdown("**Option B — Paste specific codes**")
    pasted = st.text_area(
        "Enter codes separated by commas or new lines",
        height=110,
        placeholder="P1, P2, P3, P4",
        key="paste_codes"
    )

    if st.button("Create these codes", key="create_specific"):
        raw = parse_codes_input(pasted)

        if not raw:
            st.error("Please enter at least one code.")
        else:
            # Limit to needed quantity
            if len(raw) > needed:
                st.warning(
                    f"You entered {len(raw)} codes but only {needed} are missing. We'll create the first {needed}.")
                raw = raw[:needed]

            created, errors = create_specific_codes_for_lot(lot_id, raw)

            if created:
                st.success(f"Created: {', '.join(created)}")
            if errors:
                st.warning("Some issues:")
                for e in errors:
                    st.write("• ", e)


def render_edit_section():
    """Render the edit/move/delete specimen section."""
    with st.expander("Edit / Move / Delete a Specimen"):
        edit_code = st.text_input("Existing code", placeholder="e.g., P12", key="edit_code")

        if st.button("Load", key="load_specimen"):
            rec = get_specimen_by_code(edit_code.strip())
            if not rec:
                st.error("Not found.")
            else:
                st.session_state["_rec"] = rec

        rec = st.session_state.get("_rec")
        if rec:
            st.write("**Current**")
            for key, value in rec.items():
                if value is not None:
                    st.write(f"• **{key}:** {value}")

            # Get lot options for the same coin type
            ct_id = get_coin_type_for_specimen(rec["code"])
            if ct_id:
                lots_same_type = get_lots_for_coin_type(ct_id)
                lot_options = {
                    f"Lot {r['id']} (on hand {r['qty_remaining']})": r["id"]
                    for r in lots_same_type
                }
            else:
                lot_options = {}

            # Edit form
            new_code = st.text_input("New code (leave blank to keep)", key="new_code")

            new_lot_label = st.selectbox(
                "Move to lot (optional)",
                ["(no change)"] + list(lot_options.keys()),
                key="new_lot"
            )
            new_lot_id = None if new_lot_label == "(no change)" else lot_options.get(new_lot_label)

            new_notes = st.text_input("Notes (optional)", key="new_notes")

            # Action buttons
            colA, colB, colC = st.columns(3)

            if colA.button("Save changes", key="save_changes"):
                ok, msg = update_specimen(
                    rec["code"],
                    new_code.strip().upper() or None,
                    new_lot_id,
                    new_notes if new_notes else None
                )
                if ok:
                    st.success(msg)
                    st.session_state.pop("_rec", None)
                    st.rerun()
                else:
                    st.error(msg)

            if colB.button("Delete (if not sold)", key="delete_specimen"):
                ok, msg = delete_specimen(rec["code"])
                if ok:
                    st.success(msg)
                    st.session_state.pop("_rec", None)
                    st.rerun()
                else:
                    st.error(msg)

            if colC.button("Cancel", key="cancel_edit"):
                st.session_state.pop("_rec", None)
                st.rerun()


def render_series_prefix_section():
    """Render the series prefix configuration section."""
    with st.expander("Set / Update Series Prefix"):
        st.caption(
            "Define the prefix used when auto-assigning codes (e.g., Peace → P, Morgan → M, Capped Bust → CB).")

        series = st.text_input("Series name (must match your 'series' exactly, e.g., 'Peace')",
                               key="prefix_series")
        prefix = st.text_input("Prefix (1–3 letters)", placeholder="P, M, CB", key="prefix_code")

        if st.button("Save Prefix", key="save_prefix"):
            if not series or not prefix:
                st.error("Both Series and Prefix are required.")
            else:
                try:
                    prefix_clean = prefix.strip().upper()[:3]
                    create_or_update_series_code(series.strip(), prefix_clean)
                    st.success(f"Saved: {series.strip()} → {prefix_clean}")
                except Exception as e:
                    st.error(str(e))


def render_browse_section():
    """Render the browse specimens section."""
    with st.expander("Browse current specimens on hand"):
        flt = st.text_input(
            "Filter by series (optional)",
            placeholder="e.g., Peace, Morgan",
            key="browse_filter"
        )

        try:
            rows = get_specimens_on_hand(flt.strip() or None)
            if rows:
                df = pd.DataFrame(rows)
                df = df.rename(columns={"mint_mark": "Mint Mark"})
                st.dataframe(df, width='stretch', hide_index=True)

                # Add download button
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "Download CSV",
                    data=csv,
                    file_name="specimens_on_hand.csv",
                    mime="text/csv"
                )
            else:
                st.info("No specimens found (on hand).")
        except Exception as e:
            st.error(str(e))


# ---------------------------------
# Main UI
# ---------------------------------

# Render sections
render_lookup_section()
st.divider()

render_add_flip_ids_section()
st.divider()

render_edit_section()
st.divider()

render_series_prefix_section()

render_browse_section()