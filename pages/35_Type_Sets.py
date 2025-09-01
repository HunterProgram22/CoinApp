# pages/35_Type_Sets.py
import streamlit as st
import pandas as pd
from type_sets_helpers import (
    get_all_type_sets,
    create_type_set,
    update_type_set,
    delete_type_set,
    get_type_set_members,
    add_type_set_members,
    remove_type_set_members,
    get_type_set_progress,
    get_type_set_summary,
    get_type_set_upgrade_targets,
    get_type_set_metadata,
    save_type_set_metadata,
    search_coin_types,
    get_all_series,
    format_coin_type_label,
    search_coin_types_catalog
)
from constants import GRADE_COMPANIES, GRADE_TEXT_VALUES

st.header("Type Sets")

# Create tabs
tabs = st.tabs(["📊 My Sets", "➕ Define Set", "✏️ Modify Set"])

# =====================================================
# Tab 1: My Sets - View Progress
# =====================================================
with tabs[0]:
    type_sets = get_all_type_sets()

    if not type_sets:
        st.info("No Type Sets yet. Use 'Define Set' tab to create one.")
    else:
        # Select type set
        set_options = {f"{s['name']} (#{s['id']})": s for s in type_sets}
        selected_label = st.selectbox("Choose a Type Set", list(set_options.keys()))
        selected_set = set_options[selected_label]
        set_id = selected_set['id']

        # Show set details and metadata
        st.subheader(f"📚 {selected_set['name']}")
        if selected_set.get('description'):
            st.caption(selected_set['description'])
        
        # Get and display set metadata/criteria if it exists
        metadata = get_type_set_metadata(set_id) if 'get_type_set_metadata' in dir() else {}
        if metadata:
            with st.expander("Set Criteria", expanded=False):
                criteria_text = []
                if metadata.get('series'):
                    criteria_text.append(f"**Series:** {', '.join(metadata['series'])}")
                if metadata.get('year_range'):
                    criteria_text.append(f"**Years:** {metadata['year_range'][0]}-{metadata['year_range'][1]}")
                if metadata.get('grade_company'):
                    criteria_text.append(f"**Grading Company:** {metadata['grade_company']}")
                if metadata.get('min_grade'):
                    criteria_text.append(f"**Minimum Grade:** {metadata['min_grade']}")
                if metadata.get('require_slab'):
                    criteria_text.append("**Must be slabbed**")
                
                if criteria_text:
                    for line in criteria_text:
                        st.markdown(line)

        # Progress section
        st.subheader("Collection Progress")
        
        # Get progress using the new view
        progress_df = get_type_set_progress(set_id)
        
        if progress_df.empty:
            st.warning("This set has no coins defined yet. Use 'Modify Set' tab to add coins.")
        else:
            # Format the dataframe for display
            progress_df['have'] = progress_df.apply(
                lambda r: '✅' if r['meets_requirements'] else ('🔶' if r['qty_on_hand'] > 0 else '❌'),
                axis=1
            )
            progress_df['is_proof'] = progress_df['is_proof'].apply(lambda x: '✓' if x else '')
            progress_df['grade_info'] = progress_df.apply(
                lambda r: f"{r['best_grade_company']}/{r['best_grade_text']}" 
                if r['best_grade_company'] and r['best_grade_text'] else "",
                axis=1
            )
            
            # Calculate statistics using summary view
            summary = get_type_set_summary(set_id)
            if summary:
                total_needed = summary['total_coins']
                total_have = summary['coins_owned']
                total_meeting_requirements = summary['coins_meeting_requirements']
                percent_complete = summary['percent_complete']
                
                # Display metrics
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Coins in Set", total_needed)
                col2.metric("Coins Owned", total_have)
                col3.metric("Meeting Requirements", total_meeting_requirements)
                col4.metric("Complete", f"{percent_complete:.1f}%")
                
                # Progress bar
                st.progress(percent_complete / 100 if percent_complete else 0)
            
            # Legend for status icons
            st.caption("✅ = Meets all requirements | 🔶 = Have but doesn't meet requirements | ❌ = Don't have")
            
            # Display the full list
            st.subheader("Detailed Progress")
            
            # Filter options
            col1, col2 = st.columns(2)
            show_filter = col1.selectbox("Show", ["All", "Have", "Need", "Need Upgrade"], index=0)
            
            if show_filter == "Have":
                display_df = progress_df[progress_df['meets_requirements'] == 1]
            elif show_filter == "Need":
                display_df = progress_df[progress_df['qty_on_hand'] == 0]
            elif show_filter == "Need Upgrade":
                display_df = progress_df[(progress_df['qty_on_hand'] > 0) & (progress_df['meets_requirements'] == 0)]
            else:
                display_df = progress_df
            
            # Select columns to display
            display_columns = ['have', 'series', 'year', 'mint_mark', 'variety', 'is_proof', 
                             'qty_on_hand', 'grade_info']
            
            st.dataframe(display_df[display_columns], width='stretch', hide_index=True)
            
            # Download buttons
            col1, col2 = st.columns(2)
            
            # Full progress CSV
            csv = progress_df.to_csv(index=False).encode('utf-8')
            col1.download_button(
                "📥 Download Full Progress",
                data=csv,
                file_name=f"type_set_{set_id}_progress.csv",
                mime="text/csv"
            )
            
            # Missing/upgrade analysis
            if col2.button("Show Upgrade Targets"):
                upgrade_targets = get_type_set_upgrade_targets(set_id)
                if upgrade_targets:
                    st.subheader("Coins Needing Upgrade")
                    upgrade_df = pd.DataFrame(upgrade_targets)
                    st.dataframe(upgrade_df, width='stretch', hide_index=True)

# =====================================================
# Tab 2: Define Set - Create new sets with criteria
# =====================================================
with tabs[1]:
    st.subheader("Define a New Type Set")
    
    # Basic set information
    st.markdown("### Basic Information")
    new_name = st.text_input("Set Name*", placeholder="e.g., Susan B Anthony NGC PF70 Set")
    new_desc = st.text_area("Description", placeholder="Optional description of your set goals")
    
    # Set criteria
    st.markdown("### Set Criteria")
    st.caption("Define which coins should be included in this set")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Series selection
        all_series = get_all_series()
        selected_series = st.multiselect("Series", all_series, help="Which series to include")
        
        # Year range
        st.markdown("**Year Range**")
        c1, c2 = st.columns(2)
        start_year = c1.number_input("From", min_value=0, value=0, step=1, help="0 = no limit")
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
    
    # Preview section
    st.markdown("### Preview Set Contents")
    
    if st.button("Preview Coins That Will Be In This Set", type="secondary"):
        if not new_name:
            st.error("Please enter a set name first")
        elif not selected_series:
            st.error("Please select at least one series")
        else:
            # Build year range
            year_range = None
            if start_year > 0 and end_year > 0 and end_year >= start_year:
                year_range = (start_year, end_year)
            elif start_year > 0:
                year_range = (start_year, 9999)
            elif end_year > 0:
                year_range = (0, end_year)
            
            # Search catalog for coins that match criteria
            # This searches ALL coins in the catalog, not just what you have
            catalog_matches = search_coin_types_catalog(
                series=selected_series,
                year_range=year_range,
                proof_filter=proof_filter,
                include_varieties=specific_varieties
            )
            
            if catalog_matches:
                st.success(f"This set will contain {len(catalog_matches)} coins")
                
                # Show preview
                preview_df = pd.DataFrame(catalog_matches)
                preview_df['coin'] = preview_df.apply(
                    lambda r: f"{r['series']} {r['year']} {r.get('mint_mark', '')} {r.get('variety', '')}".strip(),
                    axis=1
                )
                
                # Show first 20 and total count
                if len(preview_df) > 20:
                    st.dataframe(preview_df[['coin']].head(20), width='stretch', hide_index=True)
                    st.caption(f"Showing first 20 of {len(catalog_matches)} coins")
                else:
                    st.dataframe(preview_df[['coin']], width='stretch', hide_index=True)
                
                # Store in session state for creation
                st.session_state['new_set_coins'] = catalog_matches
                st.session_state['new_set_metadata'] = {
                    'grade_company': grade_company_filter if grade_company_filter != "Any" else None,
                    'min_grade': min_grade_filter if min_grade_filter != "Any" else None,
                    'max_grade': max_grade_filter if max_grade_filter != "Any" else None,
                    'require_slab': require_slab,
                    'proof_only': proof_filter == "Proofs only",
                    'business_only': proof_filter == "Business strikes only",
                    'include_varieties': specific_varieties,
                    'year_start': start_year if start_year > 0 else None,
                    'year_end': end_year if end_year > 0 else None
                }
            else:
                st.warning("No coins found matching these criteria in the catalog")
    
    # Create button
    if 'new_set_coins' in st.session_state and st.session_state['new_set_coins']:
        st.markdown("---")
        if st.button(f"✅ Create Set with {len(st.session_state['new_set_coins'])} coins", type="primary"):
            if not new_name:
                st.error("Please enter a set name")
            else:
                # Create the set with metadata
                set_id = create_type_set(new_name, new_desc, st.session_state.get('new_set_metadata'))
                
                # Add all the coins to the set
                coin_type_ids = [c['id'] for c in st.session_state['new_set_coins']]
                added = add_type_set_members(set_id, coin_type_ids)
                
                st.success(f"Created '{new_name}' with {added} coins!")
                
                # Clear session state
                del st.session_state['new_set_coins']
                if 'new_set_metadata' in st.session_state:
                    del st.session_state['new_set_metadata']
                
                st.rerun()

# =====================================================
# Tab 3: Modify Set - Add/remove coins from existing sets
# =====================================================
with tabs[2]:
    type_sets = get_all_type_sets()
    
    if not type_sets:
        st.info("No sets to modify. Create one in the 'Define Set' tab first.")
    else:
        st.subheader("Modify Existing Set")
        
        # Select set to modify
        set_options = {f"{s['name']} (#{s['id']})": s for s in type_sets}
        selected_set_label = st.selectbox("Select set to modify", list(set_options.keys()))
        selected_set = set_options[selected_set_label]
        work_set_id = selected_set['id']
        
        # Edit basic details
        with st.expander("Edit Set Details"):
            edit_name = st.text_input("Set name", value=selected_set['name'])
            edit_desc = st.text_area("Description", value=selected_set.get('description', ''))
            
            col1, col2 = st.columns(2)
            if col1.button("Save Changes", type="primary"):
                update_type_set(work_set_id, edit_name, edit_desc)
                st.success("Updated!")
                st.rerun()
            
            # Use session state for delete confirmation
            if col2.button("Delete Set", type="secondary"):
                st.session_state['confirm_delete'] = work_set_id
            
            # Show confirmation outside of button click
            if st.session_state.get('confirm_delete') == work_set_id:
                st.warning("⚠️ Are you sure you want to delete this set? This cannot be undone.")
                col_confirm, col_cancel = st.columns(2)
                
                if col_confirm.button("Yes, Delete", type="primary", key="confirm_del"):
                    delete_type_set(work_set_id)
                    st.success("Set deleted!")
                    if 'confirm_delete' in st.session_state:
                        del st.session_state['confirm_delete']
                    st.rerun()
                
                if col_cancel.button("Cancel", key="cancel_del"):
                    del st.session_state['confirm_delete']
                    st.rerun()
        
        # Current members
        current_members = get_type_set_members(work_set_id)
        
        st.markdown(f"### Current Contents: {len(current_members)} coins")
        
        if current_members:
            with st.expander("View current members", expanded=False):
                members_df = pd.DataFrame(current_members)
                members_df['coin'] = members_df.apply(
                    lambda r: format_coin_type_label(r.to_dict()),
                    axis=1
                )
                st.dataframe(members_df[['coin']], width='stretch', hide_index=True)
        
        # Add coins section
        st.markdown("### Add Coins")
        
        add_method = st.radio("Add method", ["By Filter", "Individual Selection"])
        
        if add_method == "By Filter":
            col1, col2 = st.columns(2)
            
            with col1:
                all_series = get_all_series()
                add_series = st.multiselect("Filter by series", all_series, key="add_series")
            
            with col2:
                c1, c2 = st.columns(2)
                add_start_year = c1.number_input("Start year", 0, step=1, key="add_start")
                add_end_year = c2.number_input("End year", 0, step=1, key="add_end")
                
                add_proof_filter = st.selectbox("Type filter", 
                                               ["Any", "Proofs only", "Non-proof only"],
                                               key="add_proof")
            
            # Build year range
            add_year_range = None
            if add_start_year > 0 and add_end_year > 0 and add_end_year >= add_start_year:
                add_year_range = (add_start_year, add_end_year)
            elif add_start_year > 0:
                add_year_range = (add_start_year, 9999)
            elif add_end_year > 0:
                add_year_range = (0, add_end_year)
            
            # Preview matches
            if st.button("Preview Coins to Add", key="preview_add"):
                matches = search_coin_types(
                    series=add_series if add_series else None,
                    year_range=add_year_range,
                    proof_filter=add_proof_filter
                )
                
                # Filter out already added
                current_ids = {m['coin_type_id'] for m in current_members}
                new_matches = [m for m in matches if m['id'] not in current_ids]
                
                if new_matches:
                    st.session_state['add_matches'] = new_matches
                    st.write(f"Found {len(new_matches)} new coins to add:")
                    
                    matches_df = pd.DataFrame(new_matches)
                    matches_df['coin'] = matches_df.apply(
                        lambda r: format_coin_type_label(r.to_dict()),
                        axis=1
                    )
                    st.dataframe(matches_df[['coin']], width='stretch', hide_index=True)
                else:
                    st.info("No new coins found with those filters (or all are already in the set)")
            
            # Add button
            if 'add_matches' in st.session_state and st.session_state['add_matches']:
                if st.button(f"Add {len(st.session_state['add_matches'])} coins to set", 
                           type="primary", key="do_add"):
                    coin_type_ids = [m['id'] for m in st.session_state['add_matches']]
                    added = add_type_set_members(work_set_id, coin_type_ids)
                    st.success(f"Added {added} coins!")
                    del st.session_state['add_matches']
                    st.rerun()
        
        else:  # Individual Selection
            all_types = search_coin_types()  # Get all
            
            if all_types:
                # Filter out already added
                current_ids = {m['coin_type_id'] for m in current_members}
                available = [t for t in all_types if t['id'] not in current_ids]
                
                if available:
                    # Limit display for performance
                    display_limit = min(200, len(available))
                    if len(available) > display_limit:
                        st.caption(f"Showing first {display_limit} of {len(available)} available coins")
                    
                    add_options = {
                        format_coin_type_label(t, include_id=True): t['id']
                        for t in available[:display_limit]
                    }
                    
                    to_add = st.multiselect("Select coins to add", list(add_options.keys()))
                    
                    if to_add and st.button("Add Selected", type="primary"):
                        ids = [add_options[label] for label in to_add]
                        added = add_type_set_members(work_set_id, ids)
                        st.success(f"Added {added} coins!")
                        st.rerun()
                else:
                    st.info("All available coins are already in the set.")
        
        # Remove coins section
        if current_members:
            st.markdown("### Remove Coins")
            
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
