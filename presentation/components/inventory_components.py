# presentation/components/inventory_components.py
"""Inventory UI components - Single Responsibility: Inventory rendering logic"""
import streamlit as st
import pandas as pd
from typing import List, Optional, Tuple
from presentation.components.helpers.inventory_helpers import (
    format_year_columns_for_display,
    format_money_columns,
    create_download_button
)
from infrastructure.database.repositories.inventory_repository import (
    InventoryDataRepository,
    InventoryBySeries,
    SeriesDetail,
    FlaggedInventory
)


class InventoryRenderer:
    """Handles all inventory UI rendering - Single Responsibility"""
    
    def __init__(self, repo: InventoryDataRepository):
        """Inject inventory repository dependency"""
        self.repo = repo
    
    def render_series_summary_tab(self):
        """Render the series summary tab with country filtering."""
        # Country filter
        country_filter = st.radio(
            "Filter by:",
            ["All", "US Only", "World Only"],
            horizontal=True,
            key="series_country_filter"
        )

        # Get data from repository
        series_data = self.repo.get_inventory_by_series(country_filter)
        
        if not series_data:
            filter_msg = f" ({country_filter.lower()})" if country_filter != "All" else ""
            st.info(f"No inventory yet{filter_msg}.")
            return

        # Convert to DataFrame for display
        df = self._convert_series_data_to_dataframe(series_data, country_filter)
        
        # Format and display
        display_df, csv_df = format_money_columns(df, ["Est. Value (USD)"])
        st.dataframe(display_df, width='stretch', hide_index=True)

        # Download button
        filename_suffix = self._get_filename_suffix(country_filter)
        create_download_button(
            f"Download CSV (Series Summary{' - ' + country_filter if country_filter != 'All' else ''})",
            csv_df,
            f"inventory_by_series_summary{filename_suffix}.csv"
        )
    
    def render_series_detail_tab(self):
        """Render the series detail tab with country and series selection."""
        countries = self.repo.get_countries_with_inventory()

        if not countries:
            st.info("No inventory found.")
            return

        # Country and series selection
        selected_country, selected_series = self._render_country_series_selection(countries)
        
        # Show results if both are selected
        if selected_country and selected_series:
            self._render_series_detail_results(selected_series)
        elif selected_country:
            st.info("👆 Select a series above to view inventory details")
        else:
            st.info("👆 Select a country above to begin")
    
    def render_flags_tab(self):
        """Render the flags filtering tab."""
        # Flag selection
        col1, col2 = st.columns(2)
        want_proofs = col1.checkbox("Proofs only", value=False, key="inv_flag_proofs")
        want_slabbed = col2.checkbox("Slabbed only (has cert or PCGS/NGC/ANACS/ICG)", 
                                   value=False, key="inv_flag_slabbed")

        # Get filtered data
        flagged_data = self.repo.get_inventory_by_flags(want_proofs, want_slabbed)
        
        if not flagged_data:
            st.info("No lots matched those flags.")
            return

        # Convert to DataFrame and display
        df = self._convert_flagged_data_to_dataframe(flagged_data)
        self._display_formatted_inventory_dataframe(df, "inventory_filter_flags.csv", "Flags")
    
    def _convert_series_data_to_dataframe(self, series_data: List[InventoryBySeries], 
                                        country_filter: str) -> pd.DataFrame:
        """Convert series data to DataFrame with appropriate columns."""
        data = []
        for item in series_data:
            data.append({
                'series': item.series,
                'country': item.country,
                'coins': item.coins,
                'est_value_usd': item.est_value_usd
            })
        
        df = pd.DataFrame(data)
        
        # Optionally show country column for "All" and "World Only" views
        show_country = country_filter in ["All", "World Only"]
        if not show_country and "country" in df.columns:
            df = df.drop(columns=["country"])

        return df.rename(columns={
            "series": "Series",
            "country": "Country", 
            "coins": "Coins",
            "est_value_usd": "Est. Value (USD)"
        })
    
    def _get_filename_suffix(self, country_filter: str) -> str:
        """Get filename suffix based on country filter."""
        if country_filter == "US Only":
            return "_us"
        elif country_filter == "World Only":
            return "_world"
        return ""
    
    def _render_country_series_selection(self, countries: List[str]) -> Tuple[Optional[str], Optional[str]]:
        """Render country and series selection dropdowns."""
        col1, col2 = st.columns(2)

        # Country dropdown (starts blank)
        selected_country = col1.selectbox(
            "Country",
            [""] + countries,
            index=0,
            key="inv_detail_country",
            help="Select a country to filter series"
        )

        # Series dropdown (dependent on country)
        if selected_country:
            series_list = self.repo.get_series_list_for_country(selected_country)
            selected_series = col2.selectbox(
                "Series",
                [""] + series_list,
                index=0,
                key="inv_series_pick"
            )
        else:
            col2.selectbox(
                "Series",
                ["Select a country first"],
                index=0,
                key="inv_series_pick",
                disabled=True
            )
            selected_series = None

        return selected_country, selected_series
    
    def _render_series_detail_results(self, selected_series: str):
        """Render the detailed results for a selected series."""
        detail_data = self.repo.get_inventory_by_series_detail(selected_series)
        
        if not detail_data:
            st.info("No on-hand lots for this series.")
            return

        # Convert to DataFrame
        df = self._convert_detail_data_to_dataframe(detail_data)
        
        # Display formatted DataFrame
        filename = f"{selected_series}_detail.csv".replace(" ", "_")
        self._display_formatted_inventory_dataframe(df, filename, "Series Detail")
    
    def _convert_detail_data_to_dataframe(self, detail_data: List[SeriesDetail]) -> pd.DataFrame:
        """Convert series detail data to DataFrame."""
        data = []
        for item in detail_data:
            data.append({
                'lot_id': item.lot_id,
                'series': item.series,
                'year': item.year,
                'mint_mark': item.mint_mark,
                'variety': item.variety,
                'qty_remaining': item.qty_remaining,
                'unit_cost_usd': item.unit_cost_usd,
                'melt_unit_value': item.melt_unit_value,
                'chosen_unit_value': item.chosen_unit_value,
                'lot_est_value': item.lot_est_value
                # Add other fields as needed
            })
        return pd.DataFrame(data)
    
    def _convert_flagged_data_to_dataframe(self, flagged_data: List[FlaggedInventory]) -> pd.DataFrame:
        """Convert flagged inventory data to DataFrame."""
        data = []
        for item in flagged_data:
            data.append({
                'lot_id': item.lot_id,
                'series': item.series,
                'year': item.year,
                'mint_mark': item.mint_mark,
                'variety': item.variety,
                'qty_remaining': item.qty_remaining,
                'unit_cost_usd': item.unit_cost_usd,
                'melt_unit_value': item.melt_unit_value,
                'chosen_unit_value': item.chosen_unit_value,
                'lot_est_value': item.lot_est_value,
                'is_proof': item.is_proof,
                'cert_number': item.cert_number
                # Add other fields as needed
            })
        return pd.DataFrame(data)
    
    def _display_formatted_inventory_dataframe(self, df: pd.DataFrame, filename: str, button_label: str):
        """Format and display inventory DataFrame with download button."""
        # Hide the lot_id column for display
        if "lot_id" in df.columns:
            csv_df = df.copy()  # Keep lot_id in CSV
            df = df.drop(columns=["lot_id"])
        else:
            csv_df = df.copy()

        # Format year columns
        display_df = format_year_columns_for_display(df)

        # Format money columns with proper precision
        money_columns = ["Unit Cost (USD)", "Melt Unit Value", "Chosen Unit Value", "Lot Est. Value"]
        display_df, _ = format_money_columns(display_df, money_columns, keep_melt_precision=True)

        st.dataframe(display_df, width='stretch', hide_index=True)
        create_download_button(f"Download CSV ({button_label})", csv_df, filename)
