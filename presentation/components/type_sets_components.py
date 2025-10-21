# presentation/components/type_sets_components.py
import streamlit as st
import pandas as pd
from typing import Optional
from infrastructure.database.repositories.type_sets_repository import TypeSetsDataRepository
from infrastructure.database.cached_queries import (
    get_cached_all_series,
    get_cached_type_set_value_data,
    get_cached_type_set_summary,
    get_cached_type_set_progress
)
from presentation.components.helpers.type_sets_helpers import (
    format_coin_type_label, format_progress_display_dataframe, filter_progress_data,
    prepare_progress_display_columns, format_summary_display_dataframe,
    build_criteria_text, calculate_summary_metrics, build_year_range_from_inputs,
    format_coin_preview_dataframe, build_coin_label_options, filter_available_coins,
    build_new_set_metadata, format_value_display, format_percentage_display,
    prepare_download_filename, get_status_legend_text, format_metadata_for_display,
    convert_dataclass_list_to_dict_list, sort_type_sets_alphabetically,
    prepare_type_set_options, validate_set_name, validate_year_range
)
from core.constants import GRADE_COMPANIES, GRADE_TEXT_VALUES


class TypeSetsRenderer:
    """UI renderer for Type Sets functionality"""

    def __init__(self, repository: TypeSetsDataRepository):
        self.repository = repository

    def render_set_summary_tab(self):
        """Render the Set Summary tab"""
        st.subheader("Type Set Summary")

        type_sets = self.repository.get_all_type_sets()

        if not type_sets:
            st.info("No Type Sets yet. Use 'Define Set' tab to create one.")
            return

        # Get value and cost data for each set - USE CACHED VERSION
        from infrastructure.database.cached_queries import get_cached_type_set_value_data, \
            get_cached_type_set_summary
        repo_id = id(self.repository)

        summary_data = []
        summaries = []

        for type_set in type_sets:
            set_id = type_set.id

            # USE CACHED QUERIES - This is the critical fix!
            summary = get_cached_type_set_summary(repo_id, set_id)
            summaries.append(summary.__dict__ if summary else None)

            # USE CACHED QUERY - This was reading 157,000 rows each time!
            value_data = get_cached_type_set_value_data(repo_id, set_id)

            summary_data.append({
                'Set Name': type_set.name,
                'Total Coins': summary.total_coins if summary else 0,
                'Coins Owned': summary.coins_owned if summary else 0,
                'Percent Complete': format_percentage_display(
                    summary.percent_complete) if summary else "0.0%",
                'Est. Value (USD)': format_value_display(value_data.total_est_value),
                'Total Cost (USD)': format_value_display(value_data.total_cost)
            })

        # Create DataFrame and display
        summary_df = format_summary_display_dataframe(summary_data)

        # Display the summary table
        st.dataframe(
            summary_df,
            width='stretch',
            hide_index=True,
            column_config={
                'Set Name': st.column_config.TextColumn(width='medium'),
                'Total Coins': st.column_config.NumberColumn(format='%d'),
                'Coins Owned': st.column_config.NumberColumn(format='%d'),
                'Percent Complete': st.column_config.TextColumn(),
                'Est. Value (USD)': st.column_config.TextColumn(),
                'Total Cost (USD)': st.column_config.TextColumn()
            }
        )

        # Summary metrics at the bottom
        type_sets_dict = convert_dataclass_list_to_dict_list(type_sets)
        metrics = calculate_summary_metrics(type_sets_dict, summaries)

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Type Sets", metrics['total_sets'])
        col2.metric("Total Coins Needed", metrics['total_coins_needed'])
        col3.metric("Total Coins Owned", metrics['total_coins_owned'])

        # Download button
        csv = summary_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Download Summary CSV",
            data=csv,
            file_name=prepare_download_filename(0, "summary"),
            mime="text/csv"
        )

    def render_my_sets_tab(self):
        """Render the My Sets tab - View Progress"""
        type_sets = self.repository.get_all_type_sets()

        if not type_sets:
            st.info("No Type Sets yet. Use 'Define Set' tab to create one.")
            return

        # Convert dataclass to dict for helpers
        type_set_options = prepare_type_set_options(type_sets)
        sorted_names = sort_type_sets_alphabetically(convert_dataclass_list_to_dict_list(type_sets))

        selected_label = st.selectbox(
            "Choose a Type Set",
            [""] + sorted_names,
            index=0
        )

        # Only proceed if a set is selected
        if not selected_label:
            st.info("👆 Select a Type Set above to view progress")
            return

        selected_set = type_set_options[selected_label]
        set_id = selected_set.id

        # Show set details and metadata
        st.subheader(f"📚 {selected_set.name}")
        if selected_set.description:
            st.caption(selected_set.description)

        # Get and display set metadata/criteria if it exists
        metadata = self.repository.get_type_set_metadata(set_id)
        if metadata:
            formatted_metadata = format_metadata_for_display(metadata)
            with st.expander("Set Criteria", expanded=False):
                criteria_text = build_criteria_text(formatted_metadata)
                for line in criteria_text:
                    st.markdown(line)

        # Progress section
        st.subheader("Collection Progress")

        # USE CACHED QUERIES
        from infrastructure.database.cached_queries import get_cached_type_set_progress, \
            get_cached_type_set_summary
        repo_id = id(self.repository)

        progress_df = get_cached_type_set_progress(repo_id, set_id)

        if progress_df.empty:
            st.warning("This set has no coins defined yet. Use 'Modify Set' tab to add coins.")
            return

        # Format the dataframe for display
        formatted_df = format_progress_display_dataframe(progress_df)

        # Calculate statistics using summary
        summary = get_cached_type_set_summary(repo_id, set_id)
        if summary:
            # Display metrics
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Coins in Set", summary.total_coins)
            col2.metric("Coins Owned", summary.coins_owned)
            col3.metric("Meeting Requirements", summary.coins_meeting_requirements)
            col4.metric("Complete", format_percentage_display(summary.percent_complete))

            # Progress bar
            st.progress(summary.percent_complete / 100 if summary.percent_complete else 0)

        # Legend for status icons
        st.caption(get_status_legend_text())

        # Display the full list
        st.subheader("Detailed Progress")

        # Filter options
        col1, col2 = st.columns(2)
        show_filter = col1.selectbox("Show", ["All", "Have", "Need", "Need Upgrade"], index=0)

        # Apply filter
        filtered_df = filter_progress_data(formatted_df, show_filter)
        display_df = prepare_progress_display_columns(filtered_df)

        st.dataframe(display_df, width='stretch', hide_index=True)

        # Download buttons
        col1, col2 = st.columns(2)

        # Full progress CSV
        csv = progress_df.to_csv(index=False).encode('utf-8')
        col1.download_button(
            "📥 Download Full Progress",
            data=csv,
            file_name=prepare_download_filename(set_id, "progress"),
            mime="text/csv"
        )

        # Missing/upgrade analysis
        if col2.button("Show Upgrade Targets"):
            upgrade_targets = self.repository.get_type_set_upgrade_targets(set_id)
            if upgrade_targets:
                st.subheader("Coins Needing Upgrade")
                upgrade_df = pd.DataFrame(upgrade_targets)
                st.dataframe(upgrade_df, width='stretch', hide_index=True)

    def render_define_set_tab(self):
        """Render the Define Set tab - Create new sets with criteria"""
        st.subheader("Define a New Type Set")

        # Wrap entire form in st.form() to prevent reruns on tab
        with st.form("define_new_set_form", clear_on_submit=False):
            # Basic set information
            st.markdown("### Basic Information")
            new_name = st.text_input("Set Name*", placeholder="e.g., Susan B Anthony NGC PF70 Set")
            new_desc = st.text_area("Description",
                                    placeholder="Optional description of your set goals")

            # Set criteria
            st.markdown("### Set Criteria")
            st.caption("Define which coins should be included in this set")

            col1, col2 = st.columns(2)

            with col1:
                # Series selection - USE CACHED VERSION
                from infrastructure.database.cached_queries import get_cached_all_series
                repo_id = id(self.repository)
                all_series = get_cached_all_series(repo_id)
                selected_series = st.multiselect("Series", all_series,
                                                 help="Which series to include")

                # Year range
                st.markdown("**Year Range**")
                c1, c2 = st.columns(2)
                start_year = c1.number_input("From", min_value=0, value=0, step=1,
                                             help="0 = no limit")
                end_year = c2.number_input("To", min_value=0, value=0, step=1, help="0 = no limit")

            with col2:
                # Proof filter
                proof_filter = st.selectbox("Type", ["Any", "Proofs only", "Business strikes only"])

                # Grade requirements
                st.markdown("**Grade Requirements (Optional)**")
                grade_company_filter = st.selectbox("Grading Company", ["Any"] + GRADE_COMPANIES)

                c1, c2 = st.columns(2)
                min_grade_filter = c1.selectbox("Min Grade", ["Any"] + GRADE_TEXT_VALUES)
                max_grade_filter = c2.selectbox("Max Grade", ["Any"] + GRADE_TEXT_VALUES)

            # Additional requirements
            st.markdown("### Additional Requirements")
            col1, col2 = st.columns(2)
            require_slab = col1.checkbox("Must be slabbed (have cert #)")
            specific_varieties = col2.checkbox("Include specific varieties")

            # Preview button - this is what triggers form submission
            preview_clicked = st.form_submit_button("🔍 Preview Coins That Will Be In This Set",
                                                    type="secondary")

        # Process form OUTSIDE the form block (important!)
        if preview_clicked:
            if not validate_set_name(new_name):
                st.error("Please enter a set name first")
            elif not selected_series:
                st.error("Please select at least one series")
            elif not validate_year_range(start_year, end_year):
                st.error("Invalid year range: end year must be greater than or equal to start year")
            else:
                # Build year range
                year_range = build_year_range_from_inputs(start_year, end_year)

                # Search catalog for coins that match criteria
                catalog_matches = self.repository.search_coin_types_catalog(
                    series=selected_series,
                    year_range=year_range,
                    proof_filter=proof_filter,
                    include_varieties=specific_varieties
                )

                if catalog_matches:
                    st.success(f"This set will contain {len(catalog_matches)} coins")

                    # Show preview
                    matches_dict = convert_dataclass_list_to_dict_list(catalog_matches)
                    preview_df = format_coin_preview_dataframe(matches_dict)

                    # Show first 20 and total count
                    if len(preview_df) > 20:
                        st.dataframe(preview_df[['coin']].head(20), width='stretch',
                                     hide_index=True)
                        st.caption(f"Showing first 20 of {len(catalog_matches)} coins")
                    else:
                        st.dataframe(preview_df[['coin']], width='stretch', hide_index=True)

                    # Store EVERYTHING in session state for creation (including form values!)
                    st.session_state['new_set_coins'] = catalog_matches
                    st.session_state['new_set_name'] = new_name
                    st.session_state['new_set_desc'] = new_desc
                    st.session_state['new_set_metadata'] = build_new_set_metadata(
                        grade_company_filter, min_grade_filter, max_grade_filter,
                        require_slab, proof_filter, specific_varieties, start_year, end_year
                    )
                else:
                    st.warning("No coins found matching these criteria in the catalog")

        # Create button - OUTSIDE the form, shows only after preview
        if 'new_set_coins' in st.session_state and st.session_state['new_set_coins']:
            st.markdown("---")

            if st.button(
                    f"✅ Create Set '{st.session_state.get('new_set_name', '')}' with {len(st.session_state['new_set_coins'])} coins",
                    type="primary", key="create_set_btn"):
                if validate_set_name(st.session_state.get('new_set_name', '')):
                    # Create the set with metadata
                    set_id = self.repository.create_type_set(
                        st.session_state['new_set_name'],
                        st.session_state.get('new_set_desc', ''),
                        st.session_state.get('new_set_metadata')
                    )

                    # Add all the coins to the set
                    coin_type_ids = [c.id for c in st.session_state['new_set_coins']]
                    added = self.repository.add_type_set_members(set_id, coin_type_ids)

                    st.success(f"Created '{st.session_state['new_set_name']}' with {added} coins!")

                    # Clear session state
                    for key in ['new_set_coins', 'new_set_metadata', 'new_set_name',
                                'new_set_desc']:
                        if key in st.session_state:
                            del st.session_state[key]

                    st.rerun()
                else:
                    st.error("Please enter a set name")

    def render_modify_set_tab(self):
        """Render the Modify Set tab - Add/remove coins from existing sets"""
        type_sets = self.repository.get_all_type_sets()

        if not type_sets:
            st.info("No sets to modify. Create one in the 'Define Set' tab first.")
            return

        st.subheader("Modify Existing Set")

        # Select set to modify (OUTSIDE form - we want this to trigger rerun)
        type_set_options = prepare_type_set_options(type_sets)
        selected_set_label = st.selectbox("Select set to modify", list(type_set_options.keys()))
        selected_set = type_set_options[selected_set_label]
        work_set_id = selected_set.id

        # Edit basic details - WRAP IN FORM
        with st.expander("Edit Set Details"):
            with st.form("edit_set_details_form"):
                edit_name = st.text_input("Set name", value=selected_set.name)
                edit_desc = st.text_area("Description", value=selected_set.description or '')

                col1, col2 = st.columns(2)
                save_clicked = col1.form_submit_button("Save Changes", type="primary")
                delete_clicked = col2.form_submit_button("Delete Set", type="secondary")

            # Process form submissions OUTSIDE the form
            if save_clicked:
                if validate_set_name(edit_name):
                    self.repository.update_type_set(work_set_id, edit_name, edit_desc)
                    st.success("Updated!")
                    st.rerun()
                else:
                    st.error("Please enter a valid set name")

            if delete_clicked:
                st.session_state['confirm_delete'] = work_set_id

            # Show confirmation outside of form
            if st.session_state.get('confirm_delete') == work_set_id:
                st.warning("⚠️ Are you sure you want to delete this set? This cannot be undone.")
                col_confirm, col_cancel = st.columns(2)

                if col_confirm.button("Yes, Delete", type="primary", key="confirm_del"):
                    self.repository.delete_type_set(work_set_id)
                    st.success("Set deleted!")
                    if 'confirm_delete' in st.session_state:
                        del st.session_state['confirm_delete']
                    st.rerun()

                if col_cancel.button("Cancel", key="cancel_del"):
                    del st.session_state['confirm_delete']
                    st.rerun()

        # Current members
        current_members = self.repository.get_type_set_members(work_set_id)

        st.markdown(f"### Current Contents: {len(current_members)} coins")

        if current_members:
            with st.expander("View current members", expanded=False):
                members_data = convert_dataclass_list_to_dict_list(current_members)
                members_df = pd.DataFrame(members_data)
                members_df['coin'] = members_df.apply(
                    lambda r: format_coin_type_label(r.to_dict()),
                    axis=1
                )
                st.dataframe(members_df[['coin']], width='stretch', hide_index=True)

        # Add coins section
        st.markdown("### Add Coins")
        self._render_add_coins_section(work_set_id, current_members)

        # Remove coins section
        if current_members:
            st.markdown("### Remove Coins")
            self._render_remove_coins_section(work_set_id, current_members)

    def _render_add_by_filter(self, work_set_id: int, current_members: list):
        """Render add coins by filter interface - WRAPPED IN FORM"""
        with st.form("add_by_filter_form"):
            col1, col2 = st.columns(2)

            with col1:
                repo_id = id(self.repository)
                all_series = get_cached_all_series(repo_id)
                add_series = st.multiselect("Filter by series", all_series, key="add_series")

            with col2:
                c1, c2 = st.columns(2)
                add_start_year = c1.number_input("Start year", 0, step=1, key="add_start")
                add_end_year = c2.number_input("End year", 0, step=1, key="add_end")

                add_proof_filter = st.selectbox("Type filter",
                                                ["Any", "Proofs only", "Non-proof only"],
                                                key="add_proof")

            # Preview button inside form
            preview_clicked = st.form_submit_button("Preview Coins to Add")

        # Process OUTSIDE form
        if preview_clicked:
            # Build year range
            add_year_range = build_year_range_from_inputs(add_start_year, add_end_year)

            if not validate_year_range(add_start_year, add_end_year):
                st.error("Invalid year range")
            else:
                matches = self.repository.search_coin_types(
                    series=add_series if add_series else None,
                    year_range=add_year_range,
                    proof_filter=add_proof_filter
                )

                # Filter out already added
                current_ids = {m.coin_type_id for m in current_members}
                new_matches = [m for m in matches if m.id not in current_ids]

                if new_matches:
                    st.session_state['add_matches'] = new_matches
                    st.write(f"Found {len(new_matches)} new coins to add:")

                    matches_data = convert_dataclass_list_to_dict_list(new_matches)
                    matches_df = pd.DataFrame(matches_data)
                    matches_df['coin'] = matches_df.apply(
                        lambda r: format_coin_type_label(r.to_dict()),
                        axis=1
                    )
                    st.dataframe(matches_df[['coin']], width='stretch', hide_index=True)
                else:
                    st.info("No new coins found with those filters (or all are already in the set)")

        # Add button - OUTSIDE form
        if 'add_matches' in st.session_state and st.session_state['add_matches']:
            if st.button(f"Add {len(st.session_state['add_matches'])} coins to set",
                         type="primary", key="do_add"):
                coin_type_ids = [m.id for m in st.session_state['add_matches']]
                added = self.repository.add_type_set_members(work_set_id, coin_type_ids)
                st.success(f"Added {added} coins!")
                del st.session_state['add_matches']
                st.rerun()

    def _render_add_coins_section(self, work_set_id: int, current_members: list):
        """Render the add coins section of modify tab"""
        add_method = st.radio("Add method", ["By Filter", "Individual Selection"])

        if add_method == "By Filter":
            self._render_add_by_filter(work_set_id, current_members)
        else:
            self._render_add_individual(work_set_id, current_members)

    def _render_add_individual(self, work_set_id: int, current_members: list):
        """Render add individual coins interface"""
        all_types = self.repository.search_coin_types()

        if all_types:
            # Filter out already added
            current_ids = {m.coin_type_id for m in current_members}
            all_types_dict = convert_dataclass_list_to_dict_list(all_types)
            available = filter_available_coins(all_types_dict, current_ids)

            if available:
                # Limit display for performance
                display_limit = min(200, len(available))
                if len(available) > display_limit:
                    st.caption(f"Showing first {display_limit} of {len(available)} available coins")

                add_options = build_coin_label_options(available[:display_limit], include_id=True)
                to_add = st.multiselect("Select coins to add", list(add_options.keys()))

                if to_add and st.button("Add Selected", type="primary"):
                    ids = [add_options[label] for label in to_add]
                    added = self.repository.add_type_set_members(work_set_id, ids)
                    st.success(f"Added {added} coins!")
                    st.rerun()
            else:
                st.info("All available coins are already in the set.")

    def _render_remove_coins_section(self, work_set_id: int, current_members: list):
        """Render the remove coins section"""
        members_dict = convert_dataclass_list_to_dict_list(current_members)
        remove_options = build_coin_label_options(members_dict, include_id=True)

        to_remove = st.multiselect("Select coins to remove", list(remove_options.keys()))

        if to_remove and st.button("Remove Selected", type="secondary"):
            ids = [remove_options[label] for label in to_remove]
            removed = self.repository.remove_type_set_members(work_set_id, ids)
            st.success(f"Removed {removed} coins!")
            st.rerun()
