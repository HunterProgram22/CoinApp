# presentation/components/world_coins_components.py
"""World Coins UI components - Single Responsibility: World Coins rendering logic"""
import streamlit as st
import pandas as pd
from typing import List, Tuple
from presentation.components.helpers.inventory_helpers import (
    format_year_columns_for_display,
    format_money_columns,
    create_download_button
)
from infrastructure.database.repositories.world_coins_repository import (
    WorldCoinsDataRepository,
    WorldCoinFilters,
    WorldCoinSummary,
    WorldCoinDetail
)


class WorldCoinsRenderer:
    """Handles all world coins UI rendering - Single Responsibility"""

    def __init__(self, repo: WorldCoinsDataRepository):
        """Inject world coins repository dependency"""
        self.repo = repo

    def render_filters_and_get_selection(self) -> Tuple[str, WorldCoinFilters]:
        """Render filter controls and return selected country and filters."""
        countries = self.repo.get_countries_with_world_coins()

        if not countries:
            st.info("You currently have no on-hand world coins (country field empty).")
            st.stop()

        # Create filter columns
        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

        # Country selection (required)
        country = col1.selectbox(
            "Country",
            options=countries,
            index=0,
            key="world_coins_country"
        )

        # Basic filters
        want_proofs = col2.checkbox(
            "Proofs only",
            value=False,
            key="world_coins_proofs"
        )
        want_slabbed = col3.checkbox(
            "Slabbed only",
            value=False,
            key="world_coins_slabbed"
        )

        # Optional asset category filter
        has_asset_category = self.repo.check_asset_category_support()
        if has_asset_category:
            asset_category = col4.selectbox(
                "Asset",
                options=["All", "COIN", "ROUND", "BAR"],
                index=0,
                key="world_coins_asset"
            )
        else:
            asset_category = "All"

        # Create filters object
        filters = WorldCoinFilters(
            want_proofs=want_proofs,
            want_slabbed=want_slabbed,
            asset_category=asset_category
        )

        return country, filters

    def render_summary_tab(self, country: str, filters: WorldCoinFilters):
        """Render the summary tab with series rollup data."""
        summary_data = self.repo.get_world_coins_summary(country, filters)

        if not summary_data:
            st.info("No on-hand inventory matched those filters.")
            return

        # Convert to DataFrame for display
        df = self._convert_summary_data_to_dataframe(summary_data)

        # Format money columns and display
        money_columns = ["Melt Value (USD)", "Est. Value (USD)"]
        display_df, csv_df = format_money_columns(df, money_columns)
        st.dataframe(display_df, width='stretch', hide_index=True)

        # Download button
        filename = f"world_summary_{country}.csv".replace(" ", "_")
        create_download_button(
            f"Download CSV (Summary — {country})",
            csv_df,
            filename
        )

    def render_detail_tab(self, country: str, filters: WorldCoinFilters):
        """Render the detail tab with individual lot data."""
        detail_data = self.repo.get_world_coins_detail(country, filters)

        if not detail_data:
            st.info("No lots matched those filters.")
            return

        # Convert to DataFrame
        df = self._convert_detail_data_to_dataframe(detail_data)

        # Format year columns
        display_df = format_year_columns_for_display(df)

        # Format money columns (most with 2 decimals)
        money_columns = ["Unit Cost (USD)", "Chosen Unit Value", "Lot Est. Value"]
        display_df, csv_df = format_money_columns(display_df, money_columns)

        # Special formatting for Melt Unit Value (4 decimal places)
        if "Melt Unit Value" in display_df.columns:
            display_df["Melt Unit Value"] = pd.to_numeric(
                display_df["Melt Unit Value"], errors="coerce"
            ).map(
                lambda x: "" if pd.isna(x) else f"{x:,.4f}"
            )

        st.dataframe(display_df, width='stretch', hide_index=True)

        # Download button
        filename = f"world_detail_{country}.csv".replace(" ", "_")
        create_download_button(
            f"Download CSV (Detail — {country})",
            csv_df,
            filename
        )

    def render_footer_link(self):
        """Render the footer link to World Coins Gallery."""
        st.markdown(
            "For additional information on world coins including pictures and lists with KM numbers, see: "
            "[World Coins Gallery](https://worldcoingallery.com)"
        )

    def _convert_summary_data_to_dataframe(self,
                                           summary_data: List[WorldCoinSummary]) -> pd.DataFrame:
        """Convert summary data to DataFrame with appropriate columns."""
        data = []
        for item in summary_data:
            data.append({
                'Series': item.series,
                'Coins': item.coins,
                'Melt Value (USD)': item.melt_value_usd,
                'Est. Value (USD)': item.est_value_usd
            })

        return pd.DataFrame(data)

    def _convert_detail_data_to_dataframe(self, detail_data: List[WorldCoinDetail]) -> pd.DataFrame:
        """Convert detail data to DataFrame with original column names."""
        data = []
        for item in detail_data:
            data.append({
                'lot_id': item.lot_id,  # Keep for CSV, will be hidden in display
                'Series': item.series,
                'Year': item.year,
                'Mint Mark': item.mint_mark,
                'Variety': item.variety,
                'Acquired': item.acquired,
                'Party': item.party,
                'Qty': item.qty,
                'Unit Cost (USD)': item.unit_cost_usd,
                'Melt Unit Value': item.melt_unit_value,
                'Chosen Unit Value': item.chosen_unit_value,
                'Lot Est. Value': item.lot_est_value,
                'Grade': item.grade,
                'Flip IDs': item.flip_ids,
                'Cert #': item.cert_number
            })

        df = pd.DataFrame(data)

        # Hide lot_id column for display (but keep in CSV)
        return df
