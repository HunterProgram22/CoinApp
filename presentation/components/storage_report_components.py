# presentation/components/storage_report_components.py
"""Storage Report UI components."""
import streamlit as st
import pandas as pd
from typing import Optional
from infrastructure.database.repositories.storage_report_repository import \
    StorageReportDataRepository
from presentation.components.helpers.storage_report_helpers import (
    format_year_columns_for_display,
    format_money_columns,
    prepare_storage_dataframe,
    prepare_inventory_dataframe
)


class StorageReportRenderer:
    """Renderer for storage report UI components."""

    def __init__(self, repository: StorageReportDataRepository):
        """Initialize with repository dependency."""
        self.repo = repository

    def _create_download_button(self, label: str, df: pd.DataFrame, filename: str):
        """Create a CSV download button."""
        st.download_button(
            label,
            data=df.to_csv(index=False).encode("utf-8"),
            file_name=filename,
            mime="text/csv",
        )

    def render_summary_tab(self):
        """Render the storage summary tab with category filtering."""
        st.subheader("Storage Summary")

        # Get available categories
        categories = self.repo.get_storage_categories()
        category_options = ["All"] + categories

        # Category filter dropdown
        selected_category = st.selectbox(
            "Filter by Category:",
            category_options,
            index=0,
            key="storage_category_filter"
        )

        st.divider()

        # Show overall or category-specific metrics
        if selected_category == "All":
            # Overall summary metrics
            summary = self.repo.get_storage_summary()

            if summary:
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Storage Locations", summary.total_locations)
                col2.metric("Locations with Inventory", summary.locations_with_inventory)
                col3.metric("Unassigned Coins", summary.unassigned_coins)
                col4.metric("Unassigned Value", f"${summary.unassigned_value:,.2f}")
        else:
            # Category-specific metrics
            category_summary = self.repo.get_category_summary(selected_category)

            if category_summary:
                col1, col2, col3, col4 = st.columns(4)
                col1.metric(f"Locations in '{selected_category}'", category_summary.location_count)
                col2.metric("Total Coins", f"{category_summary.total_coins:,}")
                col3.metric("Total Cost", f"${category_summary.total_cost:,.2f}")
                col4.metric("Total Value", f"${category_summary.total_value:,.2f}")

        st.divider()

        # Storage locations table
        if selected_category == "All":
            st.markdown("### Storage Locations Overview")
        else:
            st.markdown(f"### Storage Locations in '{selected_category}'")

        locations = self.repo.get_storage_locations(
            None if selected_category == "All" else selected_category)

        if not locations:
            if selected_category == "All":
                st.info("No storage locations defined. Add some in Admin → Storage.")
            else:
                st.info(f"No storage locations found in category '{selected_category}'.")
        else:
            # Convert to DataFrame for display
            df = prepare_storage_dataframe(locations)

            # Format money columns
            display_df, csv_df = format_money_columns(df, ["Total Cost (USD)", "Total Value (USD)"])

            st.dataframe(display_df, width='stretch', hide_index=True,
                         column_config={
                             "Lots": st.column_config.NumberColumn(format="%d"),
                             "Coins": st.column_config.NumberColumn(format="%d"),
                         })

            # Download button
            filename = f"storage_summary_{selected_category.lower().replace(' ', '_')}.csv" if selected_category != "All" else "storage_summary.csv"
            self._create_download_button(
                f"📥 Download Storage Summary CSV ({selected_category})",
                csv_df,
                filename
            )

        st.divider()

        # Unassigned Inventory Section (only show when "All" is selected)
        if selected_category == "All":
            self._render_unassigned_inventory_section()

        # Help section
        with st.expander("ℹ️ About Storage Reports"):
            st.markdown("""
            **Storage Location Reports help you:**
            - Track where your coins are physically stored
            - Filter by storage category (Safe, Bank Box, etc.)
            - See the total value stored in each location or category
            - Identify coins that haven't been assigned to a storage location
            - Generate lists for insurance or inventory purposes

            **To assign storage locations:**
            - Use the Transaction Editor to update existing transactions
            - Assign storage when adding new transactions
            - Update lot details in the Admin section

            **Tips:**
            - Set up storage locations in Admin → Storage first
            - Use descriptive names like "Home Safe", "Bank Box #123", etc.
            - Include category information to group similar storage types
            - Use the category filter to view specific types of storage
            """)

    def _render_unassigned_inventory_section(self):
        """Render the unassigned inventory section."""
        with st.expander("🚨 Unassigned Inventory", expanded=False):
            inventory = self.repo.get_unassigned_inventory()

            if not inventory:
                st.info("✅ All inventory is assigned to storage locations.")
            else:
                st.warning(f"Found {len(inventory)} lots not assigned to any storage location.")

                # Summary metrics
                total_coins = sum(item.quantity for item in inventory)
                total_cost = sum(item.lot_cost_usd for item in inventory)
                total_est_value = sum(item.est_value_usd for item in inventory)

                col1, col2, col3 = st.columns(3)
                col1.metric("Unassigned Coins", f"{total_coins:,}")
                col2.metric("Unassigned Cost", f"${total_cost:,.2f}")
                col3.metric("Unassigned Est. Value", f"${total_est_value:,.2f}")

                # Display table
                df = prepare_inventory_dataframe(inventory)

                # Format for display
                display_df = format_year_columns_for_display(df)
                money_columns = ["Unit Cost (USD)", "Lot Cost (USD)", "Est. Value (USD)"]
                display_df, csv_df = format_money_columns(display_df, money_columns)

                st.dataframe(display_df, width='stretch', hide_index=True)

                # Download button
                self._create_download_button(
                    "Download Unassigned Inventory CSV",
                    csv_df,
                    "unassigned_inventory.csv"
                )

                st.info("💡 **Tip:** You can assign storage locations when editing transactions " +
                        "or by updating lots in the Admin section.")

    def render_detail_tab(self):
        """Render the storage detail tab."""
        st.subheader("Storage Location Details")

        # Get all storage locations for dropdown
        locations = self.repo.get_storage_locations()

        if not locations:
            st.info("No storage locations defined. Add some in Admin → Storage.")
            return

        # Create dropdown options
        location_options = {
            f"{loc.name}" + (f" ({loc.category})" if loc.category else ""): loc.id
            for loc in locations
        }

        # Add "Select a location" as the first option
        selected_location = st.selectbox(
            "Select storage location to view contents:",
            ["Select a location..."] + list(location_options.keys()),
            key="storage_detail_select"
        )

        if selected_location == "Select a location...":
            st.info(
                "Please select a storage location from the dropdown above to view its contents.")
            return

        storage_id = location_options[selected_location]

        # Get location info
        location = self.repo.get_storage_location_info(storage_id)

        if not location:
            st.error("Storage location not found.")
            return

        st.divider()

        # Display location info
        st.markdown(f"### 📦 {location['name']}")
        if location['category']:
            st.caption(f"Category: {location['category']}")
        if location['description']:
            st.caption(f"Description: {location['description']}")

        # Get inventory
        inventory = self.repo.get_inventory_by_storage(storage_id)

        if not inventory:
            st.info("No inventory found in this storage location.")
            return

        # Display summary stats
        total_coins = sum(item.quantity for item in inventory)
        total_cost = sum(item.lot_cost_usd for item in inventory)
        total_est_value = sum(item.est_value_usd for item in inventory)

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Coins", f"{total_coins:,}")
        col2.metric("Total Cost", f"${total_cost:,.2f}")
        col3.metric("Est. Value", f"${total_est_value:,.2f}")

        st.divider()

        # Display inventory table
        df = prepare_inventory_dataframe(inventory)

        # Format for display
        display_df = format_year_columns_for_display(df)
        money_columns = ["Unit Cost (USD)", "Lot Cost (USD)", "Est. Value (USD)"]
        display_df, csv_df = format_money_columns(display_df, money_columns)

        st.dataframe(display_df, width='stretch', hide_index=True)

        # Download button
        location_name = location['name'].replace(" ", "_").replace("/", "_")
        self._create_download_button(
            f"📥 Download CSV ({location['name']})",
            csv_df,
            f"storage_{location_name}_inventory.csv"
        )

    def render_manage_storage_tab(self):
        """Render the manage storage locations tab."""
        st.subheader("Manage Storage Locations")

        # Add new storage location section
        with st.expander("➕ Add New Storage Location", expanded=False):
            with st.form("add_storage_form"):
                col1, col2 = st.columns(2)
                new_name = col1.text_input("Location Name*",
                                           placeholder="e.g., Home Safe, Bank Box #123")
                new_category = col2.text_input("Category",
                                               placeholder="e.g., Safe, Bank, Display")
                new_description = st.text_area("Description",
                                               placeholder="Optional description or notes",
                                               height=80)

                submitted = st.form_submit_button("Create Storage Location", type="primary")

                if submitted:
                    if not new_name:
                        st.error("Location name is required.")
                    else:
                        try:
                            storage_id = self.repo.create_storage_location(
                                new_name,
                                new_category if new_category else None,
                                new_description if new_description else None
                            )
                            st.success(
                                f"✅ Created storage location '{new_name}' (ID: {storage_id})")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to create storage location: {e}")

        st.divider()

        # Edit existing storage locations
        st.markdown("### Edit Existing Storage Locations")

        locations = self.repo.get_storage_locations()

        if not locations:
            st.info("No storage locations defined yet. Add one above.")
        else:
            # Create a selectbox for choosing location to edit
            location_options = {
                f"{loc.name}" + (f" ({loc.category})" if loc.category else ""): loc
                for loc in locations
            }

            selected_location_name = st.selectbox(
                "Select location to edit:",
                list(location_options.keys()),
                key="edit_storage_select"
            )

            if selected_location_name:
                selected_location = location_options[selected_location_name]

                with st.form(f"edit_storage_{selected_location.id}"):
                    col1, col2 = st.columns(2)
                    edit_name = col1.text_input("Location Name*", value=selected_location.name)
                    edit_category = col2.text_input("Category",
                                                    value=selected_location.category or '')
                    edit_description = st.text_area("Description",
                                                    value=selected_location.description or '',
                                                    height=80)

                    # Show inventory count
                    if selected_location.total_coins > 0:
                        st.info(
                            f"📦 This location contains {selected_location.total_coins} coins in {selected_location.lot_count} lots")

                    col1, col2, col3 = st.columns(3)

                    update_btn = col1.form_submit_button("💾 Update", type="primary")
                    delete_btn = col2.form_submit_button("🗑️ Delete", type="secondary")

                    if update_btn:
                        if not edit_name:
                            st.error("Location name is required.")
                        else:
                            try:
                                self.repo.update_storage_location(
                                    selected_location.id,
                                    edit_name,
                                    edit_category if edit_category else None,
                                    edit_description if edit_description else None
                                )
                                st.success(f"✅ Updated storage location '{edit_name}'")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to update: {e}")

                    if delete_btn:
                        if selected_location.total_coins > 0:
                            st.error(
                                "Cannot delete location with inventory. Move or remove items first.")
                        else:
                            if self.repo.delete_storage_location(selected_location.id):
                                st.success(f"✅ Deleted storage location '{selected_location.name}'")
                                st.rerun()
                            else:
                                st.error("Cannot delete location with inventory.")

    def render_bulk_move_tab(self):
        """Render the bulk move items tab."""
        st.subheader("Bulk Move Items Between Storage Locations")

        # Get all storage locations
        locations = self.repo.get_storage_locations()
        location_dict = {loc.name: loc.id for loc in locations}
        location_options = ["Unassigned"] + list(location_dict.keys())

        col1, col2 = st.columns(2)

        # Source location
        source_location = col1.selectbox(
            "From Storage Location:",
            location_options,
            key="bulk_move_source"
        )

        # Destination location
        dest_location = col2.selectbox(
            "To Storage Location:",
            location_options,
            key="bulk_move_dest"
        )

        if source_location == dest_location:
            st.warning("⚠️ Source and destination locations are the same.")
            return

        # Get source location ID
        source_id = None if source_location == "Unassigned" else location_dict[source_location]

        # Get lots in source location
        lots = self.repo.get_lots_in_storage(source_id)

        if not lots:
            st.info(f"No items found in '{source_location}'")
            return

        st.divider()

        # Display lots with checkboxes
        st.markdown(f"### Select items to move from '{source_location}' to '{dest_location}'")
        st.caption(f"Found {len(lots)} lots in {source_location}")

        # Select/Deselect all buttons
        col1, col2, col3 = st.columns([1, 1, 4])
        if col1.button("Select All", key="select_all_btn"):
            for lot in lots:
                st.session_state[f"lot_select_{lot.id}"] = True

        if col2.button("Deselect All", key="deselect_all_btn"):
            for lot in lots:
                st.session_state[f"lot_select_{lot.id}"] = False

        st.divider()

        # Display lots with checkboxes
        selected_lots = []
        total_selected_items = 0
        total_selected_value = 0.0

        for lot in lots:
            col1, col2, col3, col4 = st.columns([0.5, 4, 1, 1])

            # Checkbox - use session state directly
            is_selected = col1.checkbox(
                "Select",
                value=st.session_state.get(f"lot_select_{lot.id}", False),
                key=f"lot_select_{lot.id}",
                label_visibility="collapsed"
            )

            if is_selected:
                selected_lots.append(lot)
                total_selected_items += lot.qty_remaining
                total_selected_value += lot.total_value

            # Description
            col2.write(lot.description)

            # Quantity
            col3.write(f"Qty: {lot.qty_remaining}")

            # Value
            col4.write(f"${lot.total_value:,.2f}")

        st.divider()

        # Summary of selection
        if selected_lots:
            st.info(
                f"**Selected:** {len(selected_lots)} lots containing {total_selected_items} items worth ${total_selected_value:,.2f}")

            # Get destination ID
            dest_id = None if dest_location == "Unassigned" else location_dict[dest_location]

            # Move button
            if st.button(
                    f"🚚 Move {len(selected_lots)} Selected Items to '{dest_location}'",
                    type="primary",
                    key="move_items_btn"
            ):
                try:
                    selected_lot_ids = [lot.id for lot in selected_lots]
                    count = self.repo.bulk_move_lots(selected_lot_ids, dest_id)
                    st.success(
                        f"✅ Successfully moved {len(selected_lot_ids)} lots to '{dest_location}'")
                    # Clear selections after successful move
                    for lot in lots:
                        if f"lot_select_{lot.id}" in st.session_state:
                            del st.session_state[f"lot_select_{lot.id}"]
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to move lots: {e}")
        else:
            st.info("Select items above to enable the move button")
