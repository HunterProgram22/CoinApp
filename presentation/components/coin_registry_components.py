# presentation/components/coin_registry_components.py
"""Coin Registry UI components."""
import streamlit as st
import pandas as pd
from typing import Optional
from infrastructure.database.repositories.coin_registry_repository import CoinRegistryDataRepository
from presentation.components.helpers.coin_registry_helpers import (
    format_lot_label,
    parse_codes_input,
    prepare_slabbed_coins_dataframe,
    prepare_grading_company_dataframe,
    prepare_specimens_dataframe,
    prepare_enhanced_specimens_dataframe,
    format_specimen_details,
    calculate_specimens_summary
)


class CoinRegistryRenderer:
    """Renderer for coin registry UI components."""

    def __init__(self, repository: CoinRegistryDataRepository):
        """Initialize with repository dependency."""
        self.repo = repository

    def render_slabbed_coins_tab(self):
        """Render the slabbed coins tab."""
        st.subheader("Slabbed Coin Registry")

        # Summary metrics
        summary = self.repo.get_slabbed_summary()
        if summary and summary.total_slabs:
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Total Slabs", f"{summary.total_slabs:,}")
            col2.metric("Total Coins", f"{summary.total_coins:,}")
            col3.metric("Series", summary.total_series)
            col4.metric("Grading Cos", summary.grading_companies)
            col5.metric("Total Cost", f"${summary.total_cost:,.2f}")

            # Breakdown by grading company
            with st.expander("Breakdown by Grading Company"):
                company_data = self.repo.get_slabbed_by_grade_company()
                if company_data:
                    company_df = prepare_grading_company_dataframe(company_data)
                    st.dataframe(company_df, hide_index=True, use_container_width=True)

        st.divider()

        # Filter and display
        series_list = self.repo.get_slabbed_series_list()

        if not series_list:
            st.info("No slabbed coins found. Slabbed coins must have a certificate number.")
        else:
            # Series filter and cert search
            col1, col2 = st.columns([2, 3])
            selected_series = col1.selectbox(
                "Filter by Series",
                ["All"] + series_list,
                key="slabbed_series_filter"
            )

            cert_search = col2.text_input(
                "Search by Cert #",
                placeholder="Enter certificate number",
                key="cert_search"
            )

            # Get and display data
            if cert_search:
                # Search by cert number
                slabbed_coins = self.repo.search_slabbed_by_cert(cert_search)
            else:
                # Filter by series
                series_filter = None if selected_series == "All" else selected_series
                slabbed_coins = self.repo.get_slabbed_coins_by_series(series_filter)

            if slabbed_coins:
                # Convert to DataFrame for display
                display_df = prepare_slabbed_coins_dataframe(slabbed_coins)

                # Display count
                st.write(f"**Found {len(slabbed_coins)} slabbed coins**")

                # Display table
                st.dataframe(
                    display_df,
                    use_container_width=True,
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

    def render_browse_specimens_tab(self):
        """Render the browse specimens by series tab."""
        st.subheader("Browse Specimens by Series")

        # Get list of series that have specimens
        series_with_specimens = self.repo.get_series_with_specimens()

        if not series_with_specimens:
            st.info("No specimens found in the database.")
            return

        # Create dropdown with "All" as default
        series_options = ["All"] + series_with_specimens
        selected_series = st.selectbox(
            "Select Series",
            options=series_options,
            index=0,
            key="browse_series_filter"
        )

        # Get and display specimens
        try:
            specimens = self.repo.get_specimens_by_series_enhanced(selected_series)

            if specimens:
                # Calculate summary statistics
                summary = calculate_specimens_summary(specimens)

                # Display metrics
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Specimens", len(specimens))

                # Show series count if "All" is selected
                if selected_series == "All":
                    unique_series = len(set(s.series for s in specimens))
                    col2.metric("Series Count", unique_series)

                # Calculate total value if available
                if summary['total_value'] > 0:
                    col3.metric("Total Est. Value", f"${summary['total_value']:,.2f}")

                # Convert to DataFrame and display
                df = prepare_enhanced_specimens_dataframe(specimens)
                st.dataframe(df, use_container_width=True, hide_index=True)

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

    def render_add_flips_tab(self):
        """Render the add flips to lots tab."""
        st.subheader("Add Flip IDs to Existing Lots")

        lots = self.repo.get_all_lots()
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
            existing = self.repo.count_specimens_for_lot(lot_id)
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

            if st.button(f"Auto-create {needed} code(s)", disabled=(needed == 0),
                         key="auto_create"):
                try:
                    codes = self.repo.create_specimens_for_lot(lot_id, needed,
                                                               start_code.strip() or None)
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

                    created, errors = self.repo.create_specific_codes_for_lot(lot_id, raw)

                    if created:
                        st.success(f"Created: {', '.join(created)}")
                    if errors:
                        st.warning("Some issues:")
                        for e in errors:
                            st.write("• ", e)

    def render_edit_flip_tab(self):
        """Render the edit/move/delete specimen tab."""
        st.subheader("Edit / Move / Delete a Specimen")

        edit_code = st.text_input("Existing code", placeholder="e.g., P12", key="edit_code")

        if st.button("Load", key="load_specimen"):
            rec = self.repo.get_specimen_by_code(edit_code.strip())
            if not rec:
                st.error("Not found.")
            else:
                st.session_state["_rec"] = rec

        rec = st.session_state.get("_rec")
        if rec:
            st.write("**Current**")
            formatted = format_specimen_details(rec)
            for key, value in formatted.items():
                if value:
                    st.write(f"• **{key}:** {value}")

            # Get lot options for the same coin type
            ct_id = self.repo.get_coin_type_for_specimen(rec["code"])
            if ct_id:
                lots_same_type = self.repo.get_lots_for_coin_type(ct_id)
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
                ok, msg = self.repo.update_specimen(
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
                ok, msg = self.repo.delete_specimen(rec["code"])
                if ok:
                    st.success(msg)
                    st.session_state.pop("_rec", None)
                    st.rerun()
                else:
                    st.error(msg)

            if colC.button("Cancel", key="cancel_edit"):
                st.session_state.pop("_rec", None)
                st.rerun()

    def render_lookup_flip_tab(self):
        """Render the lookup by flip code tab."""
        st.subheader("Lookup by Flip Code")

        code = st.text_input(
            "Flip code (e.g., P1, M23, CB7)",
            help="Codes are series prefix + sequence, like P17 for Peace Dollars.",
            key="lookup_code"
        )

        col_search, col_clear = st.columns([1, 1])

        if col_search.button("Search", key="lookup_search") and code:
            result = self.repo.get_specimen_by_code(code.strip())

            if not result:
                st.warning(f"No specimen found for code '{code}'.")
            else:
                left, right = st.columns([2, 1])
                with left:
                    st.write("**Details**")
                    details = format_specimen_details(result)
                    for key, value in details.items():
                        st.write(f"• **{key}:** {value}")
                with right:
                    st.success("Match found ✅")

        if col_clear.button("Clear", key="lookup_clear"):
            st.rerun()
