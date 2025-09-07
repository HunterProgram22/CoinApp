# pages/40_Coin_Registry.py
import streamlit as st
from auth_utils import require_auth

# Check authentication first
require_auth()
# pages/40_Coin_Registry.py
import streamlit as st
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from db_operations import execute_query_all, execute_query_single, execute_insert, execute_update, \
    execute_delete
from queries import (
    get_specimen_by_code,
    get_specimens_on_hand,
    create_specimens_for_lot,
    create_or_update_series_code,
    get_all_lots,
)

st.header("🏷️ Coin Registry")

# Create tabs
tabs = st.tabs(
    ["🛡️ Slabbed Coins", "📚 Browse Specimens", "➕ Add Flips", "✏️ Edit Flip", "🔍 Lookup Flip"])


# ---------------------------------
# Slabbed Coins Functions
# ---------------------------------
def get_slabbed_series_list() -> List[str]:
    """Get list of series that have slabbed coins."""
    query = """
        SELECT DISTINCT cm.series
        FROM lot l
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        WHERE l.qty_remaining > 0 
        AND l.slab_cert IS NOT NULL 
        AND TRIM(l.slab_cert) != ''
        ORDER BY cm.series
    """
    results = execute_query_all(query)
    return [r['series'] for r in results]


def get_slabbed_coins_by_series(series: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get all slabbed coins, optionally filtered by series."""
    conditions = [
        "l.qty_remaining > 0",
        "l.slab_cert IS NOT NULL",
        "TRIM(l.slab_cert) != ''"
    ]
    params = []

    if series:
        conditions.append("cm.series = ?")
        params.append(series)

    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT 
            l.id as lot_id,
            cm.series,
            ct.year,
            ct.mint_mark,
            COALESCE(ct.variety, '') as variety,
            l.qty_remaining as quantity,
            COALESCE(l.purchase_grade_company, '') as grade_company,
            COALESCE(l.purchase_grade_text, '') as grade,
            COALESCE(l.purchase_numeric_grade, 0) as numeric_grade,
            l.slab_cert as cert_number,
            l.acquired_date,
            ROUND(l.unit_cost, 2) as cost,
            COALESCE(p.name, '') as acquired_from
        FROM lot l
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        JOIN tx_line tl ON tl.id = l.acquisition_line_id
        JOIN tx t ON t.id = tl.tx_id
        LEFT JOIN party p ON p.id = t.party_id
        WHERE {where_clause}
        ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety, l.purchase_numeric_grade DESC
    """

    return execute_query_all(query, tuple(params))


def get_slabbed_summary() -> Dict[str, Any]:
    """Get summary statistics for slabbed coins."""
    query = """
        SELECT 
            COUNT(DISTINCT l.id) as total_slabs,
            COUNT(DISTINCT cm.series) as total_series,
            SUM(l.qty_remaining) as total_coins,
            COUNT(DISTINCT l.purchase_grade_company) as grading_companies,
            ROUND(SUM(l.qty_remaining * l.unit_cost), 2) as total_cost
        FROM lot l
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        WHERE l.qty_remaining > 0 
        AND l.slab_cert IS NOT NULL 
        AND TRIM(l.slab_cert) != ''
    """
    return execute_query_single(query)


def get_slabbed_by_grade_company() -> List[Dict[str, Any]]:
    """Get breakdown by grading company."""
    query = """
        SELECT 
            COALESCE(l.purchase_grade_company, 'Unknown') as company,
            COUNT(DISTINCT l.id) as slab_count,
            SUM(l.qty_remaining) as coin_count,
            ROUND(AVG(l.purchase_numeric_grade), 1) as avg_grade
        FROM lot l
        WHERE l.qty_remaining > 0 
        AND l.slab_cert IS NOT NULL 
        AND TRIM(l.slab_cert) != ''
        GROUP BY l.purchase_grade_company
        ORDER BY slab_count DESC
    """
    return execute_query_all(query)


# ---------------------------------
# Specimen Helper Functions
# ---------------------------------
def get_specimens_by_series(series: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get specimens optionally filtered by series."""
    conditions = ["s.sold_line_id IS NULL"]
    params = []

    if series and series != "All":
        conditions.append("cm.series = ?")
        params.append(series)

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

    query = f"""
        SELECT 
            s.code,
            cm.series,
            ct.year,
            ct.mint_mark,
            COALESCE(ct.variety, '') as variety,
            s.lot_id,
            COALESCE(s.notes, '') as notes
        FROM specimen s
        JOIN coin_type ct ON ct.id = s.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        {where_clause}
        ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety, s.code
    """

    return execute_query_all(query, tuple(params))


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


def format_lot_label(lot: Dict[str, Any]) -> str:
    """Format lot for display in selectbox."""
    label = f"[Lot {lot['id']}] {lot['series']} {lot['year']}"
    if lot.get('mint_mark'):
        label += f" {lot['mint_mark']}"
    if lot.get('variety'):
        label += f" • {lot['variety']}"
    label += f" – on hand: {lot['qty_remaining']}"
    return label


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


def parse_codes_input(text: str) -> List[str]:
    """Parse user input for specimen codes."""
    if not text:
        return []
    # Replace commas with newlines and split
    return [x.strip() for x in text.replace(",", "\n").splitlines() if x.strip()]


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

            # Format year column
            if "Year" in df.columns:
                df["Year"] = df["Year"].apply(lambda x: str(int(x)) if pd.notna(x) else '')

            # Format money columns for display
            money_columns = ["Cost (USD)", "Est. Value (USD)"]
            for col in money_columns:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: f"${x:,.2f}" if pd.notna(x) and x > 0 else "")

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



# ---------------------------------
# Tab 1: Slabbed Coins
# ---------------------------------
with tabs[0]:
    st.subheader("Slabbed Coin Registry")

    # Summary metrics
    summary = get_slabbed_summary()
    if summary and summary['total_slabs']:
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Slabs", f"{summary['total_slabs']:,}")
        col2.metric("Total Coins", f"{summary['total_coins']:,}")
        col3.metric("Series", summary['total_series'])
        col4.metric("Grading Cos", summary['grading_companies'])
        col5.metric("Total Cost", f"${summary['total_cost']:,.2f}")

        # Breakdown by grading company
        with st.expander("Breakdown by Grading Company"):
            company_data = get_slabbed_by_grade_company()
            if company_data:
                company_df = pd.DataFrame(company_data)
                company_df = company_df.rename(columns={
                    'company': 'Company',
                    'slab_count': 'Slabs',
                    'coin_count': 'Coins',
                    'avg_grade': 'Avg Grade'
                })
                st.dataframe(company_df, hide_index=True, width='stretch')

    st.divider()

    # Filter and display
    series_list = get_slabbed_series_list()

    if not series_list:
        st.info("No slabbed coins found. Slabbed coins must have a certificate number.")
    else:
        # Series filter
        col1, col2 = st.columns([2, 3])
        selected_series = col1.selectbox(
            "Filter by Series",
            ["All"] + series_list,
            key="slabbed_series_filter"
        )

        # Search by cert number
        cert_search = col2.text_input(
            "Search by Cert #",
            placeholder="Enter certificate number",
            key="cert_search"
        )

        # Get and display data
        if cert_search:
            # Search by cert number
            slabbed_coins = execute_query_all("""
                SELECT 
                    l.id as lot_id,
                    cm.series,
                    ct.year,
                    ct.mint_mark,
                    COALESCE(ct.variety, '') as variety,
                    l.qty_remaining as quantity,
                    COALESCE(l.purchase_grade_company, '') as grade_company,
                    COALESCE(l.purchase_grade_text, '') as grade,
                    COALESCE(l.purchase_numeric_grade, 0) as numeric_grade,
                    l.slab_cert as cert_number,
                    l.acquired_date,
                    ROUND(l.unit_cost, 2) as cost,
                    COALESCE(p.name, '') as acquired_from
                FROM lot l
                JOIN coin_type ct ON ct.id = l.coin_type_id
                JOIN coin_master cm ON cm.id = ct.master_id
                JOIN tx_line tl ON tl.id = l.acquisition_line_id
                JOIN tx t ON t.id = tl.tx_id
                LEFT JOIN party p ON p.id = t.party_id
                WHERE l.qty_remaining > 0 
                AND l.slab_cert LIKE ?
                ORDER BY cm.series, ct.year
            """, (f"%{cert_search}%",))
        else:
            # Filter by series
            series_filter = None if selected_series == "All" else selected_series
            slabbed_coins = get_slabbed_coins_by_series(series_filter)

        if slabbed_coins:
            # Convert to DataFrame for display
            df = pd.DataFrame(slabbed_coins)

            # Format year column
            df['year'] = df['year'].apply(lambda x: str(int(x)) if pd.notna(x) else '')

            # Reorder and rename columns
            display_df = df[['series', 'year', 'mint_mark', 'variety', 'quantity',
                             'grade_company', 'grade', 'numeric_grade', 'cert_number',
                             'cost', 'acquired_date', 'acquired_from']].copy()

            display_df = display_df.rename(columns={
                'series': 'Series',
                'year': 'Year',
                'mint_mark': 'Mint',
                'variety': 'Variety',
                'quantity': 'Qty',
                'grade_company': 'Company',
                'grade': 'Grade',
                'numeric_grade': 'Numeric',
                'cert_number': 'Cert #',
                'cost': 'Cost',
                'acquired_date': 'Acquired',
                'acquired_from': 'From'
            })

            # Display count
            st.write(f"**Found {len(slabbed_coins)} slabbed coins**")

            # Display table
            st.dataframe(
                display_df,
                width='stretch',
                hide_index=True,
                column_config={
                    'Cost': st.column_config.NumberColumn(format="$%.2f"),
                    'Numeric': st.column_config.NumberColumn(format="%.1f"),
                }
            )

            # Download button
            csv = display_df.to_csv(index=False).encode('utf-8')
            filename = f"slabbed_{selected_series.lower().replace(' ', '_')}.csv" if selected_series != "All" else "slabbed_all.csv"
            st.download_button(
                "📥 Download CSV",
                data=csv,
                file_name=filename,
                mime="text/csv"
            )
        else:
            st.info("No slabbed coins found matching your criteria.")

# ---------------------------------
# Tab 2: Browse Specimens by Series
# ---------------------------------
with tabs[1]:
    render_browse_tab()

# ---------------------------------
# Tab 3: Add Flip IDs to Lots
# ---------------------------------
with tabs[2]:
    st.subheader("Add Flip IDs to Existing Lots")

    lots = get_all_lots()
    open_lots = [l for l in lots if (l.get("qty_remaining") or 0) > 0]

    if not open_lots:
        st.info("No open lots found. Add a BUY transaction first.")
    else:
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
        st.markdown("**Option A – Auto-create missing codes**")
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
                    st.success(
                        f"Created {len(codes)} code(s): " + ", ".join(display_codes) + suffix)
                else:
                    st.info("No codes created (nothing missing).")
            except Exception as e:
                st.error(str(e))

        st.markdown("---")

        # Option B: Paste specific codes
        st.markdown("**Option B – Paste specific codes**")
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

# ---------------------------------
# Tab 4: Edit/Move/Delete Specimen
# ---------------------------------
with tabs[3]:
    st.subheader("Edit / Move / Delete a Specimen")

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

# ---------------------------------
# Tab 5: Lookup by Flip Code
# ---------------------------------
with tabs[4]:
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
