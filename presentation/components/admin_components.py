# presentation/components/admin_components.py
import streamlit as st
import pandas as pd
from typing import Optional, List
from infrastructure.database.repositories.admin_repository import (
    AdminDataRepository, CoinMaster, CoinType, MetalPrice, Transaction, Lot
)
from presentation.components.helpers.admin_helpers import (
    normalize_text, format_master_label, format_type_label,
    format_transaction_label, format_lot_label, validate_master_fields,
    validate_price, get_current_timestamp, fetch_yahoo_prices,
    calculate_grams_from_troy_oz, format_price_display,
    WEIGHT_PRESETS
)
from core.constants import ASSET_CATEGORIES
from infrastructure.database.db import create_backup_data, get_backup_filename


class AdminRenderer:
    """UI rendering for admin functions with dependency injection"""

    def __init__(self, repository: AdminDataRepository):
        self.repository = repository

    def render_coin_master_tab(self):
        """Render Coin Master Editor tab"""
        st.subheader("Coin Master Editor")

        # Weight conversion helper
        self._render_weight_helper()

        masters = self.repository.get_coin_masters()

        # Add new master form
        with st.expander("➕ Add a Coin Master", expanded=False):
            self._render_add_master_form()

        # Edit existing master
        st.markdown("### Edit Existing Master")
        if not masters:
            st.info("No masters yet. Add one above.")
        else:
            self._render_edit_master_form(masters)

    def render_coin_type_tab(self):
        """Render Coin Type Editor tab"""
        st.subheader("Coin Type Editor")

        masters = self.repository.get_coin_masters()
        if not masters:
            st.info("Add a Coin Master first.")
            return

        # Add new type form
        with st.expander("➕ Add a Coin Type", expanded=False):
            self._render_add_type_form(masters)

        # Edit existing types
        st.markdown("### Edit Existing Type")
        types = self.repository.get_coin_types()

        if not types:
            st.info("No coin types yet.")
        else:
            self._render_edit_type_form(types)

    def render_metal_prices_tab(self):
        """Render Metal Prices tab"""
        st.subheader("Metal Prices")

        # Display current prices
        prices = self.repository.get_latest_metal_prices()
        if prices:
            df = pd.DataFrame(format_price_display(prices))
            st.dataframe(df, width='stretch', hide_index=True)
        else:
            st.info("No prices yet. Add some below.")

        # Manual price entry
        st.markdown("### Add/Update Price")
        col1, col2 = st.columns(2)
        metal = col1.selectbox("Metal", ["Ag", "Au", "Pt", "Pd"])
        price_str = col2.text_input("Price per oz (USD)", value="0.00")

        if st.button("Save Price", type="primary"):
            is_valid, price_val, error = validate_price(price_str)
            if not is_valid:
                st.error(error)
            else:
                try:
                    price = MetalPrice(
                        metal=metal,
                        price_per_oz_usd=price_val,
                        quoted_at_utc=get_current_timestamp()
                    )
                    self.repository.create_metal_price(price)
                    st.success(f"Saved {metal} = ${price_val:,.2f}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Save failed: {e}")

        # Yahoo Finance update
        st.markdown("### Auto-Update from Yahoo Finance")
        if st.button("Fetch Current Prices from Yahoo", type="secondary"):
            self._fetch_yahoo_prices()

    def render_maintenance_tab(self):
        """Render Maintenance Tools tab"""
        st.subheader("Maintenance Tools")

        # Transaction void
        with st.expander("Void Transaction", expanded=True):
            self._render_void_transaction()

        # Lot deletion
        with st.expander("Delete Lot"):
            self._render_delete_lot()

    def render_database_tab(self):
        """Render Database Management tab"""
        st.subheader("Database Management")
        from infrastructure.database.db import DB_PATH, get_secret

        db_type = get_secret("DB_TYPE", "sqlite")

        if db_type == "turso":
            st.info("🌩️ Using Turso Cloud Database")
            turso_url = get_secret("TURSO_DATABASE_URL", "Not configured")
            st.caption(f"Database: `{turso_url}`")
        else:
            st.caption(f"Database location: `{DB_PATH}`")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### Backup")
            st.write("Download a complete backup of your database.")

            if st.button("Create Backup", type="primary"):
                try:
                    backup_data = create_backup_data()
                    st.download_button(
                        label="📥 Download Backup",
                        data=backup_data,
                        file_name=get_backup_filename(),
                        mime="application/octet-stream",
                        width='stretch'
                    )
                except Exception as e:
                    st.error(f"Backup failed: {e}")

        with col2:
            st.markdown("### Reset Database")
            st.warning("⚠️ This will delete ALL data and cannot be undone!")

            confirm = st.checkbox("I understand this will delete all data")

            if st.button("🔥 Reset Database", type="primary", disabled=not confirm):
                try:
                    self.repository.reset_database()
                    st.success("Database reset complete!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Reset failed: {e}")

    def _render_weight_helper(self):
        """Render weight conversion helper"""
        with st.expander("Weight Conversion Helper"):
            col1, col2 = st.columns(2)
            with col1:
                preset = st.selectbox("Common weights", list(WEIGHT_PRESETS.keys()))
                st.info(f"{preset} = {WEIGHT_PRESETS[preset]} grams")
            with col2:
                troy_oz = st.number_input("Troy ounces", min_value=0.0, step=0.01, value=1.0)
                grams = calculate_grams_from_troy_oz(troy_oz)
                st.info(f"{troy_oz} troy oz = {grams:.6f} grams")

    def _render_add_master_form(self):
        """Render form to add a coin master"""
        with st.form("add_master_form"):
            # Basic required fields
            col1, col2, col3 = st.columns(3)
            new_country = col1.text_input("Country*")
            new_denomination = col2.text_input("Denomination*")
            new_series = col3.text_input("Series*")

            # Metal specs
            col1, col2, col3 = st.columns(3)
            new_metal = col1.text_input("Metal (Ag/Au/Pt/Pd)")
            new_fineness = col2.number_input("Fineness", 0.0, 1.0, 0.999, step=0.001, format="%.4f")
            new_weight = col3.number_input("Weight (grams)", 0.0, step=0.000001, format="%.6f")

            # Weight preset helper
            weight_preset = st.selectbox("Or select weight preset",
                                         ["Custom"] + list(WEIGHT_PRESETS.keys()))
            if weight_preset != "Custom":
                st.info(f"Will use: {WEIGHT_PRESETS[weight_preset]} grams")

            # Physical dimensions
            col1, col2, col3 = st.columns(3)
            new_diameter = col1.number_input("Diameter (mm)", 0.0, step=0.1)
            new_thickness = col2.number_input("Thickness (mm)", 0.0, step=0.01)
            new_edge = col3.text_input("Edge")

            # Years and category
            col1, col2, col3 = st.columns(3)
            new_years_start = col1.number_input("Years start", 0, step=1)
            new_years_end = col2.number_input("Years end", 0, step=1)
            new_asset_category = col3.selectbox("Asset Category", ASSET_CATEGORIES)

            # Reference URLs
            new_numista = st.text_input("Numista URL (optional)")
            new_ngc = st.text_input("NGC URL (optional)")
            new_pcgs = st.text_input("PCGS URL (optional)")

            # Notes
            new_notes = st.text_area("Notes", height=80)

            if st.form_submit_button("Create Master", type="primary"):
                is_valid, error = validate_master_fields(new_country, new_denomination, new_series)
                if not is_valid:
                    st.error(error)
                else:
                    try:
                        # Use preset weight if selected
                        final_weight = WEIGHT_PRESETS[
                            weight_preset] if weight_preset != "Custom" else new_weight

                        master = CoinMaster(
                            id=0,  # Will be assigned by database
                            country=new_country,
                            denomination=new_denomination,
                            series=new_series,
                            metal=new_metal or None,
                            fineness=new_fineness if new_fineness else None,
                            weight_grams=final_weight if final_weight else None,
                            diameter_mm=new_diameter if new_diameter else None,
                            thickness_mm=new_thickness if new_thickness else None,
                            edge=new_edge or None,
                            years_start=new_years_start or None,
                            years_end=new_years_end or None,
                            asset_category=new_asset_category,
                            numista_url=new_numista or None,
                            ngc_url=new_ngc or None,
                            pcgs_url=new_pcgs or None,
                            notes=new_notes or None
                        )
                        result_id = self.repository.create_coin_master(master)
                        st.success(f"Created master with ID: {result_id}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Creation failed: {e}")

    def _render_edit_master_form(self, masters: List[CoinMaster]):
        """Render form to edit a coin master"""
        labels = [format_master_label(m) for m in masters]

        # Add placeholder option and default to it
        options = ["-- Select a coin master to edit --"] + labels
        selected = st.selectbox("Select a coin master", options, index=0, key="cm_select")

        # Only show edit form if a master is selected
        if selected == options[0]:
            st.info("Select a coin master from the dropdown to edit its details.")
            return

        master = masters[options.index(selected) - 1]  # Adjust index for placeholder
        mid = master.id

        # Basic info
        col1, col2, col3 = st.columns(3)
        country = col1.text_input("Country", master.country, key=f"cm_country_{mid}")
        denomination = col2.text_input("Denomination", master.denomination, key=f"cm_denom_{mid}")
        series = col3.text_input("Series", master.series, key=f"cm_series_{mid}")

        # Metal specifications
        col1, col2, col3 = st.columns(3)
        metal = col1.text_input("Metal (Ag/Au/Pt/Pd)", master.metal or "", key=f"cm_metal_{mid}")
        fineness = col2.number_input("Fineness (0-1)", 0.0, 1.0,
                                     value=float(master.fineness or 0.0),
                                     step=0.001, format="%.4f", key=f"cm_fineness_{mid}")
        weight_grams = col3.number_input("Weight (grams)", 0.0, step=0.000001,
                                         value=float(master.weight_grams or 0.0),
                                         format="%.6f", key=f"cm_weight_{mid}")

        # Physical dimensions
        col1, col2, col3 = st.columns(3)
        diameter_mm = col1.number_input("Diameter (mm)", 0.0, step=0.1,
                                        value=float(master.diameter_mm or 0.0),
                                        key=f"cm_diameter_{mid}")
        thickness_mm = col2.number_input("Thickness (mm)", 0.0, step=0.01,
                                         value=float(master.thickness_mm or 0.0),
                                         key=f"cm_thickness_{mid}")
        edge = col3.text_input("Edge", master.edge or "", key=f"cm_edge_{mid}")

        # Years and category
        col1, col2, col3 = st.columns(3)
        years_start = col1.number_input("Years start", 0, step=1,
                                        value=int(master.years_start or 0),
                                        key=f"cm_ystart_{mid}")
        years_end = col2.number_input("Years end", 0, step=1,
                                      value=int(master.years_end or 0),
                                      key=f"cm_yend_{mid}")
        asset_category = col3.selectbox("Asset Category", ASSET_CATEGORIES,
                                        index=ASSET_CATEGORIES.index(master.asset_category),
                                        key=f"cm_assetcat_{mid}")

        # Reference URLs
        st.markdown("#### Reference URLs")
        numista_url = st.text_input("Numista URL", master.numista_url or "",
                                    key=f"cm_numista_{mid}")
        ngc_url = st.text_input("NGC URL", master.ngc_url or "", key=f"cm_ngc_{mid}")
        pcgs_url = st.text_input("PCGS URL", master.pcgs_url or "", key=f"cm_pcgs_{mid}")

        # Link buttons
        col1, col2, col3 = st.columns(3)
        if numista_url:
            col1.link_button("Open Numista", numista_url)
        if ngc_url:
            col2.link_button("Open NGC", ngc_url)
        if pcgs_url:
            col3.link_button("Open PCGS", pcgs_url)

        # Notes
        notes = st.text_area("Notes", master.notes or "", height=80, key=f"cm_notes_{mid}")

        # Save button
        if st.button("Save Changes", type="primary", key=f"cm_save_{mid}"):
            try:
                updated_master = CoinMaster(
                    id=mid,
                    country=country,
                    denomination=denomination,
                    series=series,
                    metal=metal or None,
                    fineness=fineness,
                    weight_grams=weight_grams,
                    diameter_mm=diameter_mm,
                    thickness_mm=thickness_mm,
                    edge=edge or None,
                    years_start=years_start or None,
                    years_end=years_end or None,
                    asset_category=asset_category,
                    numista_url=numista_url or None,
                    ngc_url=ngc_url or None,
                    pcgs_url=pcgs_url or None,
                    notes=notes or None
                )
                rows = self.repository.update_coin_master(updated_master)
                st.success(f"Updated successfully! Rows affected: {rows}")
                st.rerun()
            except Exception as e:
                st.error(f"Update failed: {e}")

    def _render_edit_type_form(self, types: List[CoinType]):
        """Render form to edit a coin type"""
        type_labels = [format_type_label(t) for t in types]

        # Add placeholder option and default to it
        options = ["-- Select a coin type to edit --"] + type_labels
        selected_type = st.selectbox("Select coin type", options, index=0)

        # Only show edit form if a type is selected
        if selected_type == options[0]:
            st.info("Select a coin type from the dropdown to edit its details.")
            return

        type_data = types[options.index(selected_type) - 1]  # Adjust index for placeholder
        tid = type_data.id

        # Initialize session state for delete confirmation
        if f'delete_confirm_{tid}' not in st.session_state:
            st.session_state[f'delete_confirm_{tid}'] = False

        col1, col2, col3 = st.columns(3)
        edit_year = col1.number_input("Year", value=type_data.year, key=f"type_year_{tid}")
        edit_mint = col2.text_input("Mint Mark", value=type_data.mint_mark, key=f"type_mint_{tid}")
        edit_variety = col3.text_input("Variety", value=type_data.variety,
                                       key=f"type_variety_{tid}")

        col1, col2 = st.columns(2)
        edit_mintage = col1.number_input("Mintage", value=type_data.mintage or 0,
                                         key=f"type_mintage_{tid}")
        edit_proof = col2.checkbox("Is Proof?", value=type_data.is_proof, key=f"type_proof_{tid}")

        # Show delete confirmation if flag is set
        if st.session_state[f'delete_confirm_{tid}']:
            st.warning(
                f"⚠️ Are you sure you want to delete this coin type? This action cannot be undone.")
            col_confirm, col_cancel, col_empty = st.columns([1, 1, 3])
            with col_confirm:
                if st.button("Yes, Delete", type="primary", key=f"confirm_delete_{tid}"):
                    try:
                        if self.repository.delete_coin_type(tid):
                            # Clear the confirmation state
                            st.session_state[f'delete_confirm_{tid}'] = False
                            st.success(f"Coin type deleted successfully!")
                            st.rerun()
                        else:
                            st.session_state[f'delete_confirm_{tid}'] = False
                            st.error(
                                "Cannot delete coin type - inventory lots exist for this type.")
                    except Exception as e:
                        st.session_state[f'delete_confirm_{tid}'] = False
                        st.error(f"Delete failed: {e}")
            with col_cancel:
                if st.button("Cancel", key=f"cancel_delete_{tid}"):
                    st.session_state[f'delete_confirm_{tid}'] = False
                    st.rerun()
        else:
            # Show normal buttons
            col1, col2, col3 = st.columns([1, 1, 3])

            with col1:
                if st.button("Save Changes", type="primary", key=f"save_type_{tid}"):
                    try:
                        updated_type = CoinType(
                            id=tid,
                            master_id=type_data.master_id,
                            country=type_data.country,
                            denomination=type_data.denomination,
                            series=type_data.series,
                            year=edit_year,
                            mint_mark=edit_mint,
                            variety=edit_variety,
                            mintage=edit_mintage,
                            is_proof=edit_proof
                        )
                        rows = self.repository.update_coin_type(updated_type)
                        st.success(f"Updated successfully! Rows affected: {rows}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Update failed: {e}")

            with col2:
                if st.button("🗑️ Delete Type", type="secondary", key=f"delete_type_{tid}"):
                    st.session_state[f'delete_confirm_{tid}'] = True
                    st.rerun()

    def _render_add_type_form(self, masters: List[CoinMaster]):
        """Render form to add a coin type"""
        with st.form("add_type_form"):
            labels = [format_master_label(m) for m in masters]
            master_index = st.selectbox("Master", range(len(labels)),
                                        format_func=lambda x: labels[x])
            selected_master = masters[master_index]

            col1, col2, col3 = st.columns(3)
            year = col1.number_input("Year*", min_value=0, step=1)
            mint_mark = col2.text_input("Mint Mark")
            variety = col3.text_input("Variety")

            col1, col2 = st.columns(2)
            mintage = col1.number_input("Mintage", min_value=0, step=1)
            is_proof = col2.checkbox("Is Proof?")

            if st.form_submit_button("Create Type", type="primary"):
                try:
                    coin_type = CoinType(
                        id=0,  # Will be assigned by database
                        master_id=selected_master.id,
                        country=selected_master.country,
                        denomination=selected_master.denomination,
                        series=selected_master.series,
                        year=year,
                        mint_mark=normalize_text(mint_mark) or '',
                        variety=normalize_text(variety) or '',
                        mintage=mintage or None,
                        is_proof=is_proof
                    )
                    result_id = self.repository.create_coin_type(coin_type)
                    st.success(f"Created type with ID: {result_id}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Creation failed: {e}")

    def _fetch_yahoo_prices(self):
        """Fetch and save prices from Yahoo Finance"""
        try:
            prices = fetch_yahoo_prices()
            if not prices:
                st.warning("No prices fetched")
                return

            timestamp = get_current_timestamp()
            updated = []

            for metal, price_val in prices.items():
                try:
                    price = MetalPrice(
                        metal=metal,
                        price_per_oz_usd=price_val,
                        quoted_at_utc=timestamp
                    )
                    self.repository.create_metal_price(price)
                    updated.append(f"{metal}: ${price_val:,.2f}")
                except Exception as e:
                    st.warning(f"Failed to save {metal}: {e}")

            if updated:
                st.success("Updated: " + ", ".join(updated))
                st.rerun()
        except ImportError:
            st.error("yfinance not installed. Add it to requirements.txt")
        except Exception as e:
            st.error(f"Failed to fetch prices: {e}")

    def _render_void_transaction(self):
        """Render transaction void interface"""
        transactions = self.repository.get_recent_transactions(100)
        if not transactions:
            st.info("No transactions found.")
        else:
            tx_options = [format_transaction_label(t) for t in transactions]
            selected_tx = st.selectbox("Select transaction to void", tx_options)
            tx = transactions[tx_options.index(selected_tx)]

            if st.button("Void Transaction", type="primary"):
                try:
                    rows = self.repository.void_transaction(tx.id)
                    st.success(f"Transaction #{tx.id} voided. Rows deleted: {rows}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Void failed: {e}")

    def _render_delete_lot(self):
        """Render lot deletion interface"""
        lots = self.repository.get_open_lots()
        if not lots:
            st.info("No lots available.")
        else:
            lot_options = [format_lot_label(l) for l in lots]
            selected_lot = st.selectbox("Select lot to delete", lot_options)
            lot = lots[lot_options.index(selected_lot)]

            if st.button("Delete Lot", type="secondary"):
                try:
                    if self.repository.delete_lot(lot.id):
                        st.success(f"Lot #{lot.id} deleted.")
                        st.rerun()
                    else:
                        st.error("Cannot delete lot with sales history.")
                except Exception as e:
                    st.error(f"Delete failed: {e}")
