# pages/35_Type_Sets.py
import streamlit as st
import pandas as pd
from type_sets_helpers import (
    check_type_set_schema,
    get_all_type_sets,
    create_type_set,
    update_type_set,
    delete_type_set,
    get_type_set_members,
    add_type_set_members,
    remove_type_set_members,
    get_type_set_progress,
    analyze_missing_coins,
    get_type_set_assignments,
    get_unassigned_specimens,
    assign_specimen_to_set,
    unassign_specimen_from_set,
    search_coin_types,
    get_all_series,
    format_coin_type_label
)

st.header("Type Sets")

# Create tabs
tabs = st.tabs(["My Sets", "Define & Build"])

# =====================================================
# Tab 1: My Sets
# =====================================================
with tabs[0]:
    type_sets = get_all_type_sets()

    if not type_sets:
        st.info("No Type Sets yet. Use 'Define & Build' to create one.")
    else:
        # Select type set
        set_options = {f"{s['name']} (#{s['id']})": s for s in type_sets}
        selected_label = st.selectbox("Choose a Type Set", list(set_options.keys()))
        selected_set = set_options[selected_label]
        set_id = selected_set['id']

        # Edit set details
        with st.expander("Edit set details"):
            new_name = st.text_input("Set name", value=selected_set['name'])
            new_desc = st.text_area("Description", value=selected_set.get('description', ''))

            col1, col2 = st.columns(2)
            if col1.button("Save Changes", type="primary"):
                update_type_set(set_id, new_name, new_desc)
                st.success("Updated!")
                st.rerun()

            if col2.button("Delete Set", type="secondary"):
                if st.checkbox("Confirm deletion"):
                    delete_type_set(set_id)
                    st.success("Deleted!")
                    st.rerun()

        # Progress section
        st.subheader("Collection Progress")
        view_name, progress_df = get_type_set_progress(set_id)

        if view_name:
            st.caption(f"Using view: {view_name}")

            if not progress_df.empty:
                # Display progress
                st.dataframe(progress_df, width='stretch', hide_index=True)

                # Download button
                csv = progress_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "Download Progress CSV",
                    data=csv,
                    file_name=f"type_set_{set_id}_progress.csv",
                    mime="text/csv"
                )

                # Missing coins analysis
                missing_df = analyze_missing_coins(progress_df)

                if not missing_df.empty:
                    st.subheader("Missing Coins")

                    # Select columns to display
                    id_cols = ['series', 'year', 'mint_mark', 'variety', 'coin_type_id']
                    display_cols = [c for c in id_cols if c in missing_df.columns]

                    if display_cols:
                        st.dataframe(missing_df[display_cols], width='stretch', hide_index=True)

                        # Download missing list
                        missing_csv = missing_df[display_cols].to_csv(index=False).encode('utf-8')
                        st.download_button(
                            "Download Missing List CSV",
                            data=missing_csv,
                            file_name=f"type_set_{set_id}_missing.csv",
                            mime="text/csv"
                        )
                else:
                    st.success("✅ Collection complete! No missing coins.")
            else:
                st.info("No coins in this set yet.")
        else:
            st.warning("Progress views not found. Create v_type_set_progress view for tracking.")

        # Specimen assignment section (if available)
        assignment_schema = check_type_set_schema()
        if all([assignment_schema['type_set_assignment'], assignment_schema['specimen']]):
            st.subheader("Specimen Assignments")

            # Get current assignments
            assignments = get_type_set_assignments(set_id)

            if assignments:
                st.write("Current assignments:")
                assignments_df = pd.DataFrame(assignments)
                st.dataframe(assignments_df, width='stretch', hide_index=True)

                # Unassign option
                specimen_codes = [a['specimen_code'] for a in assignments]
                to_unassign = st.selectbox("Unassign specimen", ["None"] + specimen_codes)

                if to_unassign != "None" and st.button("Unassign"):
                    unassign_specimen_from_set(set_id, to_unassign)
                    st.success("Unassigned!")
                    st.rerun()

            # Assign new specimen
            if not progress_df.empty and 'coin_type_id' in progress_df.columns:
                st.markdown("**Assign new specimen:**")

                # Select coin type
                coin_types = progress_df[
                    ['coin_type_id', 'series', 'year', 'mint_mark', 'variety']].drop_duplicates()
                coin_labels = {
                    format_coin_type_label(row.to_dict(), include_id=True): row['coin_type_id']
                    for _, row in coin_types.iterrows()
                }

                selected_coin = st.selectbox("Select coin type", list(coin_labels.keys()))
                coin_type_id = coin_labels[selected_coin]

                # Get available specimens
                available = get_unassigned_specimens(coin_type_id, set_id)

                if available:
                    specimen_map = {s['code']: s['id'] for s in available}
                    selected_specimen = st.selectbox("Available specimens",
                                                     list(specimen_map.keys()))

                    if st.button("Assign Specimen", type="primary"):
                        assign_specimen_to_set(set_id, coin_type_id,
                                               specimen_map[selected_specimen])
                        st.success("Assigned!")
                        st.rerun()
                else:
                    st.info("No unassigned specimens available for this coin type.")

# =====================================================
# Tab 2: Define & Build
# =====================================================
with tabs[1]:
    st.subheader("Create or Modify Type Sets")

    # Create new set
    with st.expander("➕ Create New Type Set", expanded=False):
        with st.form("create_set_form"):
            new_name = st.text_input("Set name*")
            new_desc = st.text_area("Description")

            if st.form_submit_button("Create Set", type="primary"):
                if not new_name:
                    st.error("Set name is required")
                else:
                    set_id = create_type_set(new_name, new_desc)
                    st.success(f"Created set #{set_id}")
                    st.rerun()

    # Modify existing set
    type_sets = get_all_type_sets()

    if type_sets:
        st.markdown("### Modify Existing Set")

        set_options = {f"{s['name']} (#{s['id']})": s['id'] for s in type_sets}
        selected_set = st.selectbox("Select set to modify", list(set_options.keys()))
        work_set_id = set_options[selected_set]

        # Current members
        current_members = get_type_set_members(work_set_id)

        if current_members:
            st.write(f"Current members: {len(current_members)} coins")
            with st.expander("View current members"):
                members_df = pd.DataFrame(current_members)
                members_df['label'] = members_df.apply(
                    lambda r: format_coin_type_label(r.to_dict()),
                    axis=1
                )
                st.dataframe(members_df[['label']], width='stretch', hide_index=True)

        # Build from catalog
        st.markdown("### Build from Catalog")

        col1, col2 = st.columns(2)

        with col1:
            all_series = get_all_series()
            selected_series = st.multiselect("Filter by series", all_series)

        with col2:
            c1, c2 = st.columns(2)
            start_year = c1.number_input("Start year", 0, step=1, help="0 = no filter")
            end_year = c2.number_input("End year", 0, step=1, help="0 = no filter")

            proof_filter = st.selectbox("Proof filter", ["Any", "Proofs only", "Non-proof only"])

        # Build year range
        year_range = None
        if start_year > 0 and end_year > 0 and end_year >= start_year:
            year_range = (start_year, end_year)
        elif start_year > 0:
            year_range = (start_year, 9999)
        elif end_year > 0:
            year_range = (0, end_year)

        # Preview matches
        if st.button("Preview Matches", type="secondary"):
            matches = search_coin_types(
                series=selected_series if selected_series else None,
                year_range=year_range,
                proof_filter=proof_filter
            )

            if matches:
                st.write(f"Found {len(matches)} matches:")

                matches_df = pd.DataFrame(matches)
                matches_df['label'] = matches_df.apply(
                    lambda r: format_coin_type_label(r.to_dict()),
                    axis=1
                )
                st.dataframe(matches_df[['label']], width='stretch', hide_index=True)

                # Add all to set
                if st.button(f"Add all {len(matches)} to set", type="primary"):
                    coin_type_ids = [m['id'] for m in matches]
                    added = add_type_set_members(work_set_id, coin_type_ids)
                    st.success(f"Added {added} coins to set!")
                    st.rerun()
            else:
                st.info("No matches found with those filters.")

        # Manual add/remove
        st.markdown("### Manual Add/Remove")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Add specific coins:**")
            all_types = search_coin_types()  # Get all

            if all_types:
                # Filter out already added
                current_ids = {m['coin_type_id'] for m in current_members}
                available = [t for t in all_types if t['id'] not in current_ids]

                if available:
                    add_options = {
                        format_coin_type_label(t, include_id=True): t['id']
                        for t in available[:100]  # Limit to 100 for performance
                    }

                    to_add = st.multiselect("Select coins to add", list(add_options.keys()))

                    if to_add and st.button("Add Selected", type="primary"):
                        ids = [add_options[label] for label in to_add]
                        added = add_type_set_members(work_set_id, ids)
                        st.success(f"Added {added} coins!")
                        st.rerun()
                else:
                    st.info("All available coins are already in the set.")

        with col2:
            st.markdown("**Remove coins:**")

            if current_members:
                remove_options = {
                    format_coin_type_label(m, include_id=True): m['coin_type_id']
                    for m in current_members
                }

                to_remove = st.multiselect("Select coins to remove", list(remove_options.keys()))

                if to_remove and st.button("Remove Selected", type="secondary"):
                    ids = [remove_options[label] for label in to_remove]
                    removed = remove_type_set_members(work_set_id, ids)
                    st.success(f"Removed {removed} coins!")
                    st.rerun()
