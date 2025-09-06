# pages/40_Specimens.py
import streamlit as st
from auth_utils import require_auth

# Check authentication first
require_auth()
import streamlit as st
import pandas as pd
from typing import List, Tuple, Optional, Dict, Any
from db_operations import execute_query_all, execute_query_single, execute_insert, execute_update, \
    execute_delete
from queries import (
    get_specimen_by_code,
    create_specimens_for_lot,
    create_or_update_series_code,
    get_all_lots,
)

st.header("🏷️ Specimens (Flip IDs)")


# ---------------------------------
# Data Access Functions
# ---------------------------------
def get_series_with_specimens() -> List[str]:
    """Get list of series that have specimens."""
    query = """
        SELECT DISTINCT cm.series
        FROM specimen s
        JOIN coin_type ct ON ct.id = s.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        WHERE s.sold_line_id IS NULL
        ORDER BY cm.series
    """
    results = execute_query_all(query)
    return [r['series'] for r in results]


def get_specimens_by_series_enhanced(filter_series: str = None) -> List[Dict[str, Any]]:
    """Get specimens with enhanced details including acquisition info and values."""
    conditions = ["s.sold_line_id IS NULL"]
    params = []

    if filter_series and filter_series != "All":
        conditions.append("cm.series = ?")
        params.append(filter_series)

    where_clause = "WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT 
            s.code,
            cm.series,
            ct.year,
            ct.mint_mark,
            ct.variety,
            s.lot_id,
            l.acquired_date,
            COALESCE(p.name, '') AS acquired_from,
            ROUND(l.unit_cost, 2) AS unit_cost,
            COALESCE(l.estimated_grade_text, l.purchase_grade_text, '') AS grade,
            ROUND(COALESCE(v.chosen_unit_value, l.unit_cost), 2) AS est_value
        FROM specimen s
        JOIN coin_type ct ON ct.id = s.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        LEFT JOIN lot l ON l.id = s.lot_id
        LEFT JOIN tx_line tl ON tl.id = l.acquisition_line_id
        LEFT JOIN tx t ON t.id = tl.tx_id
        LEFT JOIN party p ON p.id = t.party_id
        LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
        {where_clause}
        ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety, s.code
    """

    return execute_query_all(query, params)


def count_specimens_for_lot(lot_id: int) -> int:
    """Count specimens assigned to a specific lot."""
    query = "SELECT COUNT(*) AS count FROM specimen WHERE lot_id = ?"
    result = execute_query_single(query, (lot_id,))
    return result['count'] if result else 0


def create_specific_codes_for_lot(lot_id: int, codes: List[str]) -> Tuple[List[str], List[str]]:
    """Create specific specimen codes for a lot."""
    created = []
    errors = []

    codes = [c.strip().upper() for c in codes if str(c).strip()]
    if not codes:
        return created, ["No codes provided."]

    lot_query = "SELECT coin_type_id FROM lot WHERE id = ?"
    lot_result = execute_query_single(lot_query, (lot_id,))

    if not lot_result:
        return created, [f"Unknown lot_id {lot_id}"]

    coin_type_id = lot_result['coin_type_id']

    for code in codes:
        exists_query = "SELECT 1 FROM specimen WHERE code = ?"
        exists = execute_query_single(exists_query, (code,))

        if exists:
            errors.append(f"{code} already exists.")
            continue

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
    query = "SELECT id, sold_line_id FROM specimen WHERE code = ?"
    specimen = execute_query_single(query, (old_code,))

    if not specimen:
        return False, "Specimen not found."

    if new_code:
        exists = execute_query_single("SELECT 1 FROM specimen WHERE code = ?", (new_code,))
        if exists:
            return False, "The new code already exists."

    updates = []
    params = []

    if new_code:
        updates.append("code = ?")
        params.append(new_code)

    if new_lot_id is not None:
        if specimen['sold_line_id'] is not None:
            return False, "Cannot move a sold specimen."
        updates.append("lot_id = ?")
        params.append(new_lot_id)

    if notes is not None:
        updates.append("notes = ?")
        params.append(notes)

    if not updates:
        return True, "Nothing to update."

    params.append(specimen['id'])
    update_query = f"UPDATE specimen SET {', '.join(updates)} WHERE id = ?"

    try:
        execute_update(update_query, tuple(params))
        return True, "Updated."
    except Exception as e:
        return False, f"Update failed: {str(e)}"


def delete_specimen(code: str) -> Tuple[bool, str]:
    """Delete a specimen if not sold."""
    query = "SELECT sold_line_id FROM specimen WHERE code = ?"
    specimen = execute_query_single(query, (code,))

    if not specimen:
        return False, "Specimen not found."

    if specimen['sold_line_id'] is not None:
        return False, "Cannot delete a specimen that has been sold."

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
    label += f" – on hand: {lot['qty_remaining']}"
    return label


def parse_codes_input(text: str) -> List[str]:
    """Parse user input for specimen codes."""
    if not text:
        return []
    return [x.strip() for x in text.replace(",", "\n").splitlines() if x.strip()]


# ---------------------------------
# Tab Components
# ---------------------------------
def render_browse_tab():
    """Render the browse specimens by series tab."""
    st.subheader("Browse Specimens by Series")

    # Get list of series that have specimens
    series_with_specimens = get_series_with_specimens()

    if not series_with_specimens:
        st.info("No specimens found in the database.")
        return

    # Create dropdown with "All" as default
    series_options = ["All"] + series_with_specimens
    selected_series = st.selectbox(
        "Select Series",
        options=series_options,
        index=0,  # Default to "All"
        key="browse_series_filter"
    )

    # Get and display specimens
    try:
        rows = get_specimens_by_series_enhanced(selected_series)

        if rows:
            # Convert to DataFrame
            df = pd.DataFrame(rows)

            # Rename columns with proper capitalization
            df = df.rename(columns={
                "code": "Code",
                "series": "Series",
                "year": "Year",
                "mint_mark": "Mint Mark",
                "variety": "Variety",
                "lot_id": "Lot ID",
                "acquired_date": "Acquired Date",
                "acquired_from": "Acquired From",
                "unit_cost": "Cost (USD)",
                "grade": "Estimated Grade",
                "est_value": "Est. Value (USD)"
            })

            # Format money columns for display
            money_columns = ["Cost (USD)", "Est. Value (USD)"]
            for col in money_columns:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "")

            # Display metrics
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Specimens", len(df))

            # Show series count if "All" is selected
            if selected_series == "All":
                unique_series = df["Series"].nunique() if "Series" in df.columns else 0
                col2.metric("Series Count", unique_series)

            # Calculate total value if available
            if rows and 'est_value' in rows[0]:
                total_value = sum(r.get('est_value', 0) for r in rows if r.get('est_value'))
                col3.metric("Total Est. Value", f"${total_value:,.2f}")

            # Display the dataframe
            st.dataframe(df, width='stretch', hide_index=True)

            # Download button
            csv = df.to_csv(index=False).encode('utf-8')
            filename = f"specimens_{selected_series.replace(' ', '_').lower()}.csv" if selected_series != "All" else "specimens_all.csv"
            st.download_button(
                "📥 Download CSV",
                data=csv,
                file_name=filename,
                mime="text/csv"
            )
        else:
            if selected_series == "All":
                st.info("No specimens found in the database.")
            else:
                st.info(f"No specimens found for {selected_series}.")

    except Exception as e:
        st.error(f"Error loading specimens: {str(e)}")


def render_add_tab():
    """Render the add specimen IDs tab."""
    st.subheader("Add Specimen IDs to Lots")

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
    col1, col2, col3 = st.columns(3)
    col1.metric("Qty on hand", on_hand)
    col2.metric("Specimens already assigned", existing)
    col3.metric("Missing flip IDs", needed)

    st.divider()

    # Option A: Auto-create
    st.markdown("### Option A – Auto-create missing codes")

    with st.expander("Series Prefix Configuration", expanded=False):
        st.caption("Define the prefix used when auto-assigning codes")
        col1, col2 = st.columns(2)
        series = col1.text_input("Series name (e.g., 'Peace')", key="prefix_series_add")
        prefix = col2.text_input("Prefix (1–3 letters)", placeholder="P, M, CB",
                                 key="prefix_code_add")

        if st.button("Save Prefix", key="save_prefix_add"):
            if series and prefix:
                try:
                    prefix_clean = prefix.strip().upper()[:3]
                    create_or_update_series_code(series.strip(), prefix_clean)
                    st.success(f"Saved: {series.strip()} → {prefix_clean}")
                except Exception as e:
                    st.error(str(e))

    start_code = st.text_input(
        "Optional: specify the first code (e.g., P101). Leave blank to auto-assign.",
        key="start_code_auto"
    )

    if st.button(f"Auto-create {needed} code(s)", disabled=(needed == 0), type="primary",
                 key="auto_create"):
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

    st.divider()

    # Option B: Paste specific codes
    st.markdown("### Option B – Paste specific codes")
    pasted = st.text_area(
        "Enter codes separated by commas or new lines",
        height=110,
        placeholder="P1, P2, P3, P4",
        key="paste_codes"
    )

    if st.button("Create these codes", type="primary", key="create_specific"):
        raw = parse_codes_input(pasted)

        if not raw:
            st.error("Please enter at least one code.")
        else:
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


def render_edit_tab():
    """Render the edit/move/delete specimen tab."""
    st.subheader("Edit / Move / Delete Specimens")

    edit_code = st.text_input("Enter specimen code", placeholder="e.g., P12", key="edit_code")

    if st.button("Load Specimen", type="primary", key="load_specimen"):
        rec = get_specimen_by_code(edit_code.strip())
        if not rec:
            st.error("Specimen not found.")
        else:
            st.session_state["_rec"] = rec

    rec = st.session_state.get("_rec")
    if rec:
        # Display current details
        with st.expander("Current Details", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Code:**", rec.get("code"))
                st.write("**Series:**", rec.get("series"))
                st.write("**Year:**", rec.get("year"))
            with col2:
                st.write("**Mint Mark:**", rec.get("mint_mark") or "—")
                st.write("**Variety:**", rec.get("variety") or "—")
                st.write("**Lot ID:**", rec.get("lot_id"))

        st.divider()

        # Edit form
        st.markdown("### Edit Details")

        new_code = st.text_input("New code (leave blank to keep)", key="new_code")

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

        new_lot_label = st.selectbox(
            "Move to lot (optional)",
            ["(no change)"] + list(lot_options.keys()),
            key="new_lot"
        )
        new_lot_id = None if new_lot_label == "(no change)" else lot_options.get(new_lot_label)

        new_notes = st.text_input("Notes (optional)", key="new_notes")

        st.divider()

        # Action buttons
        col1, col2, col3 = st.columns(3)

        if col1.button("Save Changes", type="primary", key="save_changes"):
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

        if col2.button("Delete Specimen", type="secondary", key="delete_specimen"):
            ok, msg = delete_specimen(rec["code"])
            if ok:
                st.success(msg)
                st.session_state.pop("_rec", None)
                st.rerun()
            else:
                st.error(msg)

        if col3.button("Cancel", key="cancel_edit"):
            st.session_state.pop("_rec", None)
            st.rerun()


def render_lookup_tab():
    """Render the lookup by specimen ID tab."""
    st.subheader("Lookup by Specimen ID")

    code = st.text_input(
        "Enter flip code",
        placeholder="e.g., P1, M23, CB7",
        help="Codes are series prefix + sequence, like P17 for Peace Dollars.",
        key="lookup_code"
    )

    col1, col2 = st.columns([1, 1])

    if col1.button("Search", type="primary", key="lookup_search") and code:
        result = get_specimen_by_code(code.strip())

        if not result:
            st.warning(f"No specimen found for code '{code}'.")
        else:
            st.success("✅ Specimen found!")

            # Display details in a nice format
            with st.container():
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**Basic Information**")
                    st.write(f"**Code:** {result.get('code')}")
                    st.write(f"**Series:** {result.get('series')}")
                    st.write(f"**Year:** {result.get('year')}")
                    st.write(f"**Mint Mark:** {result.get('mint_mark') or '—'}")
                    st.write(f"**Variety:** {result.get('variety') or '—'}")

                with col2:
                    st.markdown("**Location Information**")
                    st.write(f"**Lot ID:** {result.get('lot_id')}")
                    if result.get('sold_line_id'):
                        st.write(f"**Status:** SOLD (Line #{result.get('sold_line_id')})")
                    else:
                        st.write("**Status:** On Hand")

                    if result.get('notes'):
                        st.write(f"**Notes:** {result.get('notes')}")

    if col2.button("Clear", key="lookup_clear"):
        st.rerun()


# ---------------------------------
# Main UI with Tabs
# ---------------------------------

tabs = st.tabs([
    "📋 Browse Specimens by Series",
    "➕ Add Specimen IDs",
    "✏️ Edit/Move/Delete Specimens",
    "🔍 Lookup by Specimen ID"
])

with tabs[0]:
    render_browse_tab()

with tabs[1]:
    render_add_tab()

with tabs[2]:
    render_edit_tab()

with tabs[3]:
    render_lookup_tab()