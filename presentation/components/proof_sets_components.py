# presentation/components/proof_sets_components.py
"""Proof Sets UI components."""
import streamlit as st
import pandas as pd
from datetime import date
from typing import Optional
from infrastructure.database.repositories.proof_sets_repository import ProofSetsDataRepository
from presentation.components.helpers.proof_sets_helpers import (
    format_money_columns,
    format_percentage_column,
    prepare_inventory_summary_dataframe,
    prepare_inventory_details_dataframe,
    prepare_masters_dataframe,
    create_download_csv
)
from presentation.components.helpers.input_helpers import safe_float, safe_int, format_float


class ProofSetsRenderer:
    """Renderer for proof sets UI components."""

    def __init__(self, repository: ProofSetsDataRepository):
        """Initialize with repository dependency."""
        self.repo = repository

    def render_overview_tab(self):
        """Render the overview tab."""
        st.subheader("Proof Set Portfolio Overview")

        # Portfolio summary
        portfolio = self.repo.get_portfolio_summary()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Sets", portfolio.items)
        col2.metric("Total Cost", f"${portfolio.total_cost:,.2f}")
        col3.metric("Current Value", f"${portfolio.total_value:,.2f}")

        gl = portfolio.unrealized_gl
        gl_color = "normal" if gl >= 0 else "inverse"
        col4.metric("Unrealized G/L", f"${gl:,.2f}", delta_color=gl_color)

        # Summary table
        st.subheader("Inventory Summary")
        summary = self.repo.get_inventory_summary()

        if summary:
            df = prepare_inventory_summary_dataframe(summary)

            # Format money columns
            money_columns = ['total_cost', 'total_current_value', 'avg_cost', 'min_cost',
                             'max_cost']
            display_df, _ = format_money_columns(df, money_columns)

            st.dataframe(display_df, hide_index=True, width='stretch')
        else:
            st.info("No proof sets in inventory yet.")

        # Detailed inventory
        st.subheader("Detailed Inventory")

        # Filters
        col1, col2, col3, col4 = st.columns(4)

        countries = ["All"] + self.repo.get_distinct_countries()
        country_filter = col1.selectbox("Country", countries)

        years = ["All"] + self.repo.get_distinct_years()
        year_filter = col2.selectbox("Year", years)

        set_types = ['All', 'PROOF', 'SILVER_PROOF', 'MINT', 'PRESTIGE', 'PREMIER', 'DELUXE',
                     'OTHER']
        type_filter = col3.selectbox("Set Type", set_types)

        show_sold = col4.checkbox("Show Sold Sets", value=False)

        # Get filtered inventory
        details = self.repo.get_inventory_details(
            country=country_filter if country_filter != "All" else None,
            year=year_filter if year_filter != "All" else None,
            set_type=type_filter if type_filter != "All" else None,
            show_sold=show_sold
        )

        if details:
            df = prepare_inventory_details_dataframe(details)

            # Format display columns
            money_cols = ['acquisition_price', 'current_value', 'unrealized_gain_loss',
                          'sold_price', 'realized_gain_loss']
            display_df, csv_df = format_money_columns(df, money_cols)

            # Format percentage
            display_df = format_percentage_column(display_df, 'gain_loss_percent')

            # Select columns to display
            display_cols = ['country', 'year', 'set_type', 'set_name', 'condition',
                            'acquisition_date', 'acquisition_price', 'current_value',
                            'unrealized_gain_loss', 'gain_loss_percent', 'storage_location']

            if show_sold:
                display_cols.extend(['sold_date', 'sold_price', 'realized_gain_loss'])

            display_cols = [c for c in display_cols if c in display_df.columns]

            st.dataframe(display_df[display_cols], hide_index=True, width='stretch')

            # Download button
            csv = create_download_csv(csv_df)
            st.download_button(
                "📥 Download Inventory CSV",
                data=csv,
                file_name="proof_set_inventory.csv",
                mime="text/csv"
            )
        else:
            st.info("No sets match the selected filters.")

    def render_add_inventory_tab(self):
        """Render the add to inventory tab."""
        st.subheader("Add Proof Set to Inventory")

        # Get master sets
        masters = self.repo.get_proof_set_masters()

        if not masters:
            st.warning(
                "No proof set types defined yet. Please define set types in the 'Define Set Types' tab first.")
        else:
            # Select master
            master_options = {
                f"{m.country} {m.year} {m.set_type.replace('_', ' ')}: {m.set_name}": m.id
                for m in masters
            }

            selected_master = st.selectbox("Select Proof Set Type", list(master_options.keys()))
            set_master_id = master_options[selected_master]

            # Acquisition details
            st.markdown("### Acquisition Details")

            col1, col2 = st.columns(2)
            acq_date = col1.date_input("Acquisition Date", value=date.today())
            acq_price = col2.text_input("Acquisition Price ($)", value="0.00")

            col1, col2 = st.columns(2)
            party_name = col1.text_input("Acquired From (Dealer/Person)")
            condition = col2.selectbox("Condition", ['SEALED', 'OPENED', 'DAMAGED', 'PARTIAL'])

            col1, col2 = st.columns(2)
            has_coa = col1.checkbox("Has Certificate of Authenticity", value=True)
            has_box = col2.checkbox("Has Original Box/Packaging", value=True)

            # Storage
            storage_locations = self.repo.get_storage_locations()
            storage_options = {f"{s.name} ({s.category})" if s.category
                               else s.name: s.id for s in storage_locations}
            storage_selection = st.selectbox("Storage Location",
                                             ["Not Assigned"] + list(storage_options.keys()))

            # Current value (optional)
            st.markdown("### Current Market Value (Optional)")
            col1, col2 = st.columns(2)
            current_value = col1.text_input("Current Value ($)", value="0.00")
            value_as_of = col2.date_input("Value As Of", value=date.today())

            # Notes
            purchase_notes = st.text_area("Purchase Notes")
            general_notes = st.text_area("General Notes")

            # Save button
            if st.button("Add to Inventory", type="primary"):
                acq_price_val = safe_float(acq_price)
                current_value_val = safe_float(current_value)

                if acq_price_val <= 0:
                    st.error("Please enter an acquisition price.")
                else:
                    storage_id = storage_options.get(
                        storage_selection) if storage_selection != "Not Assigned" else None

                    inv_id = self.repo.add_inventory_item(
                        set_master_id=set_master_id,
                        acquisition_date=acq_date.isoformat(),
                        acquisition_price=acq_price_val,
                        party_name=party_name,
                        condition=condition,
                        has_coa=has_coa,
                        has_original_box=has_box,
                        storage_location_id=storage_id,
                        purchase_notes=purchase_notes,
                        current_value=current_value_val if current_value_val > 0 else None,
                        value_as_of=value_as_of.isoformat() if current_value_val > 0 else None,
                        notes=general_notes
                    )

                    st.success(f"Proof set added to inventory! (ID: {inv_id})")
                    st.rerun()

    def render_manage_inventory_tab(self):
        """Render the manage inventory tab."""
        st.subheader("Manage Inventory Items")

        # Get inventory items not sold
        inventory = self.repo.get_inventory_details(show_sold=False)

        if not inventory:
            st.info("No proof sets in inventory.")
        else:
            # Select item to manage
            inv_options = {}
            for item in inventory:
                price = item.acquisition_price
                label = f"{item.country} {item.year} {item.set_type} - Acquired {item.acquisition_date} - ${price:.2f}"
                inv_options[label] = item.id

            selected_item = st.selectbox("Select Inventory Item", list(inv_options.keys()))
            inv_id = inv_options[selected_item]

            # Get full details
            item = next((i for i in inventory if i.id == inv_id), None)

            if item:
                # Display current details
                st.markdown("### Current Details")
                col1, col2, col3 = st.columns(3)
                col1.write(f"**Set:** {item.set_name}")
                col2.write(f"**Condition:** {item.condition}")
                col3.write(f"**Storage:** {item.storage_location or 'Not Assigned'}")

                col1, col2, col3 = st.columns(3)
                col1.write(f"**Cost:** ${item.acquisition_price:,.2f}")

                if item.current_value:
                    col2.write(f"**Current Value:** ${item.current_value:,.2f}")
                else:
                    col2.write("**Current Value:** Not Set")

                if item.unrealized_gain_loss is not None:
                    color = "🟢" if item.unrealized_gain_loss >= 0 else "🔴"
                    col3.write(f"**Unrealized G/L:** {color} ${item.unrealized_gain_loss:,.2f}")

                # Actions
                st.markdown("### Actions")

                action = st.radio("Select Action", ["Update Value", "Record Sale", "Edit Details"],
                                  key=f"action_radio_{inv_id}")

                if action == "Update Value":
                    col1, col2 = st.columns(2)
                    new_value = col1.text_input("New Current Value ($)",
                                                value=format_float(item.current_value or 0),
                                                key=f"new_value_{inv_id}")
                    new_value_date = col2.date_input("Value As Of",
                                                     value=date.today(),
                                                     key=f"value_date_{inv_id}")

                    if st.button("Update Value", type="primary", key=f"update_value_btn_{inv_id}"):
                        new_value_val = safe_float(new_value)
                        if self.repo.update_current_value(inv_id, new_value_val,
                                                          new_value_date.isoformat()):
                            st.success("Value updated!")
                            st.rerun()

                elif action == "Record Sale":
                    col1, col2, col3 = st.columns(3)
                    sale_date = col1.date_input("Sale Date",
                                                value=date.today(),
                                                key=f"sale_date_{inv_id}")
                    sale_price = col2.text_input("Sale Price ($)",
                                                 value="0.00",
                                                 key=f"sale_price_{inv_id}")
                    sold_to = col3.text_input("Sold To",
                                              key=f"sold_to_{inv_id}")

                    sale_price_val = safe_float(sale_price)
                    if sale_price_val > 0:
                        realized_gl = sale_price_val - item.acquisition_price
                        color = "🟢" if realized_gl >= 0 else "🔴"
                        st.write(f"**Realized Gain/Loss:** {color} ${realized_gl:,.2f}")

                    if st.button("Record Sale", type="primary", key=f"record_sale_btn_{inv_id}"):
                        if sale_price_val <= 0:
                            st.error("Please enter a sale price.")
                        else:
                            if self.repo.record_sale(inv_id, sale_date.isoformat(), sale_price_val,
                                                     sold_to):
                                st.success("Sale recorded!")
                                st.rerun()

    def render_define_sets_tab(self):
        """Render the define set types tab."""
        st.subheader("Define Proof Set Types")

        # Display existing masters
        masters = self.repo.get_proof_set_masters()

        if masters:
            st.markdown("### Existing Set Types")
            df = prepare_masters_dataframe(masters)

            # Format for display
            display_df = df[['country', 'year', 'set_type', 'set_name',
                             'coin_count', 'includes_silver', 'original_mint_price']].copy()
            display_df['includes_silver'] = display_df['includes_silver'].apply(
                lambda x: '✓' if x else '')
            display_df['original_mint_price'] = display_df['original_mint_price'].apply(
                lambda x: f"${float(x):,.2f}" if pd.notna(x) and x is not None else ""
            )
            st.dataframe(display_df, hide_index=True, width='stretch')

        # Add new master
        st.markdown("### Add New Set Type")

        with st.form("add_master_form"):
            col1, col2, col3 = st.columns(3)
            country = col1.text_input("Country*", value="United States")
            year = col2.number_input("Year*", min_value=1900, max_value=2100,
                                     value=date.today().year)
            set_type = col3.selectbox("Set Type*",
                                      ['PROOF', 'SILVER_PROOF', 'MINT', 'PRESTIGE',
                                       'PREMIER', 'DELUXE', 'OTHER'])

            set_name = st.text_input("Set Name*",
                                     placeholder="e.g., US Proof Set, Canadian Silver Proof Set")

            col1, col2, col3 = st.columns(3)
            mint_mark = col1.text_input("Mint Mark (if applicable)")
            coin_count = col2.number_input("Number of Coins", min_value=0, value=0)
            face_value = col3.text_input("Face Value ($)", value="0.00")

            col1, col2, col3 = st.columns(3)
            original_price = col1.text_input("Original Mint Price ($)", value="0.00")
            includes_silver = col2.checkbox("Contains Silver Coins")
            packaging = col3.text_input("Packaging Type",
                                        placeholder="e.g., Plastic Case, Wooden Box")

            special_features = st.text_input("Special Features",
                                             placeholder="e.g., 50 State Quarters, America the Beautiful")
            notes = st.text_area("Notes")

            if st.form_submit_button("Add Set Type", type="primary"):
                if not all([country, year, set_type, set_name]):
                    st.error("Please fill in all required fields (marked with *)")
                else:
                    face_value_val = safe_float(face_value)
                    original_price_val = safe_float(original_price)

                    master_id = self.repo.add_proof_set_master(
                        country=country,
                        year=year,
                        set_type=set_type,
                        set_name=set_name,
                        mint_mark=mint_mark if mint_mark else None,
                        face_value=face_value_val if face_value_val > 0 else None,
                        original_mint_price=original_price_val if original_price_val > 0 else None,
                        coin_count=coin_count if coin_count > 0 else None,
                        includes_silver=includes_silver,
                        special_features=special_features if special_features else None,
                        packaging_type=packaging if packaging else None,
                        notes=notes if notes else None
                    )
                    st.success(f"Set type added! (ID: {master_id})")
                    st.rerun()

    def render_market_values_tab(self):
        """Render the market values tab."""
        st.subheader("Track Market Values")

        masters = self.repo.get_proof_set_masters()

        if not masters:
            st.info("No proof set types defined yet.")
        else:
            # Select master
            master_options = {
                f"{m.country} {m.year} {m.set_type}: {m.set_name}": m.id
                for m in masters
            }

            selected_master = st.selectbox("Select Set Type", list(master_options.keys()))
            master_id = master_options[selected_master]

            # Display value history
            value_history = self.repo.get_market_values(master_id)

            if value_history:
                st.markdown("### Value History")
                history_df = pd.DataFrame([{
                    'value_date': v.value_date,
                    'source': v.source,
                    'condition': v.condition,
                    'market_value': v.market_value,
                    'notes': v.notes
                } for v in value_history])
                history_df['market_value'] = history_df['market_value'].apply(
                    lambda x: f"${x:,.2f}")
                st.dataframe(history_df, hide_index=True, width='stretch')

            # Add new value
            st.markdown("### Add Market Value")

            col1, col2, col3 = st.columns(3)
            value_date = col1.date_input("Date", value=date.today())
            market_value = col2.text_input("Market Value ($)", value="0.00")
            source = col3.text_input("Source", placeholder="e.g., eBay, PCGS, Red Book")

            col1, col2 = st.columns(2)
            condition = col1.selectbox("Condition", ['SEALED', 'OPENED', 'ANY'])
            value_notes = col2.text_input("Notes")

            if st.button("Add Market Value", type="primary"):
                market_value_val = safe_float(market_value)
                if market_value_val <= 0:
                    st.error("Please enter a market value.")
                elif not source:
                    st.error("Please enter a source.")
                else:
                    self.repo.add_market_value(
                        master_id, value_date.isoformat(), source, condition,
                        market_value_val, value_notes if value_notes else None
                    )
                    st.success("Market value added!")
                    st.rerun()

    def render_info_section(self):
        """Render the info/help section."""
        st.markdown("---")
        with st.expander("ℹ️ About Proof Sets"):
            st.markdown("""
            **Proof Set Types:**
            - **Proof Sets** - Regular proof sets with specially struck coins
            - **Silver Proof Sets** - Proof sets where some/all coins contain silver
            - **Mint Sets** - Uncirculated coins from that year (not proof finish)
            - **Prestige Sets** - Premium proof sets with commemorative coins
            - **Premier Sets** - Canadian premium proof sets
            - **Deluxe Sets** - Special packaging or additional coins

            **Tips:**
            - Track both sealed and opened sets separately
            - Update market values periodically to track performance
            - Note storage location for insurance purposes
            - Keep purchase receipts and certificates of authenticity
            """)
