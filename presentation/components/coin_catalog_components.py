# presentation/components/coin_catalog_components.py
"""Coin catalog UI components - Single Responsibility: UI rendering and user interaction"""
import streamlit as st
import pandas as pd
from typing import List, Dict, Any, Tuple, Optional

from infrastructure.database.repositories.coin_catalog_repository import CoinCatalogDataRepository
from presentation.components.helpers.coin_catalog_helpers import (
    prepare_master_display_dataframe,
    prepare_types_display_dataframe
)


class CoinCatalogRenderer:
    """Handles rendering of coin catalog UI components."""

    def __init__(self, repository: CoinCatalogDataRepository):
        self.repository = repository

    def create_download_button(self, df: pd.DataFrame, filename: str = "coin_catalog.csv"):
        """Create CSV download button."""
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download CSV",
            data=csv,
            file_name=filename,
            mime="text/csv"
        )

    def render_master_filters(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Render filter controls for coin masters and return selected values."""
        col1, col2, col3 = st.columns([2, 2, 3])

        # Country filter with empty default
        countries = self.repository.get_distinct_values("country")
        selected_country = col1.selectbox(
            "Country",
            [""] + countries,  # Empty string as default instead of "All"
            index=0,
            key="cat_country",
            help="Select a country to filter results"
        )

        # Denomination filter (only active if country is selected)
        if selected_country:
            denominations = self.repository.get_distinct_values(
                "denomination", "coin_master", "country", selected_country
            )
            selected_denomination = col2.selectbox(
                "Denomination",
                ["All"] + denominations,  # Keep "All" here to see all denominations for a country
                index=0,
                key="cat_denom"
            )
        else:
            col2.selectbox(
                "Denomination",
                ["Select a country first"],
                index=0,
                key="cat_denom",
                disabled=True
            )
            selected_denomination = None

        # Series search (always available but won't return results without country)
        series_search = col3.text_input(
            "Search Series",
            placeholder="e.g., Morgan, Peace, Eagle",
            key="cat_search",
            disabled=not selected_country,
            help="Search within series names"
        )

        return selected_country, selected_denomination, series_search

    def render_master_results(self, results: List[Dict[str, Any]]):
        """Render the coin master results table."""
        if not results:
            st.info("No Master Coins found. Try relaxing the filters or import some masters first.")
            return

        df = pd.DataFrame(results)
        display_df = prepare_master_display_dataframe(df)

        # Configure column display with link columns for all three references
        column_config = {}

        # Add link columns for reference sites
        if "Numista" in display_df.columns:
            column_config["Numista"] = st.column_config.LinkColumn(
                "Numista",
                display_text="Open"
            )

        if "NGC" in display_df.columns:
            column_config["NGC"] = st.column_config.LinkColumn(
                "NGC",
                display_text="Open"
            )

        if "PCGS" in display_df.columns:
            column_config["PCGS"] = st.column_config.LinkColumn(
                "PCGS",
                display_text="Open"
            )

        # Add formatting for numeric columns
        if "Fineness" in display_df.columns:
            column_config["Fineness"] = st.column_config.NumberColumn(
                "Fineness",
                format="%.4f"
            )

        if "Wt (g)" in display_df.columns:
            column_config["Wt (g)"] = st.column_config.NumberColumn(
                "Wt (g)",
                format="%.3f"
            )

        # Display the dataframe
        st.dataframe(
            display_df,
            width='stretch',
            hide_index=True,
            column_config=column_config
        )

        # Add download button
        self.create_download_button(display_df, "coin_masters.csv")

    def render_types_filters(self) -> Tuple[Optional[str], Optional[str]]:
        """Render filter controls for coin types and return selected values."""
        col1, col2 = st.columns(2)

        # Country filter with empty default
        countries = self.repository.get_countries_for_coin_types()
        if not countries:
            st.info("No coin types found in the database.")
            return None, None

        selected_country = col1.selectbox(
            "Country",
            [""] + countries,  # Empty string as default
            index=0,
            key="types_country",
            help="Select a country to view coin types"
        )

        # Series filter (only show if country is selected)
        if selected_country:
            series_list = self.repository.get_series_for_country(selected_country)
            # Removed "All" option - must select a specific series
            selected_series = col2.selectbox(
                "Series",
                [""] + series_list,  # Empty as default, no "All" option
                index=0,
                key="types_series",
                help="Select a series to view coin types"
            )
        else:
            # Show disabled/empty dropdown when no country selected
            col2.selectbox(
                "Series",
                ["Select a country first"],
                index=0,
                key="types_series",
                disabled=True
            )
            selected_series = None

        return selected_country, selected_series

    def render_types_results(self, results: List[Dict[str, Any]]):
        """Render the coin types results table."""
        if not results:
            st.info("No coin types found. Try adjusting the filters.")
            return

        df = pd.DataFrame(results)
        display_df = prepare_types_display_dataframe(df)

        # Configure column display
        column_config = {
            "Year": st.column_config.NumberColumn(format="%d"),
            "Mintage": st.column_config.TextColumn(),
        }

        # Display the dataframe
        st.dataframe(
            display_df,
            width='stretch',
            hide_index=True,
            column_config=column_config
        )

        # Add download button
        self.create_download_button(display_df, "coin_types.csv")

    def render_masters_tab(self):
        """Render the complete coin masters tab."""
        st.caption("Filter your Master Coins and jump to Numista, NGC, and PCGS references.")

        # Render filters
        selected_country, selected_denomination, series_search = self.render_master_filters()

        # Only search and display if a country is selected
        if selected_country:
            # Execute search
            results = self.repository.search_coin_masters(
                selected_country, selected_denomination, series_search
            )

            # Display result count
            st.markdown(f"**Results:** {len(results):,} master coins")

            # Render results
            self.render_master_results(results)
        else:
            # Show instruction message when no country is selected
            st.info("👆 Select a country above to view coin masters")

        # Add help information
        with st.expander("ℹ️ About Reference Links"):
            st.markdown("""
            **Reference Links:**
            - **Numista** - Community-driven world coin catalog with detailed information
            - **NGC** - Numismatic Guaranty Company price guides and population reports
            - **PCGS** - Professional Coin Grading Service price guides and population reports

            Links will only appear if they've been added to the coin master records.
            You can add these URLs in Admin → Coin Master Editor.
            """)

    def render_types_tab(self):
        """Render the complete coin types tab."""
        st.caption("Browse individual coin types with year, mint mark, and variety details.")

        # Render filters
        filter_result = self.render_types_filters()

        if filter_result:
            selected_country, selected_series = filter_result

            # Only search and display if both country AND series are selected
            if selected_country and selected_series:
                # Execute search
                type_results = self.repository.search_coin_types(selected_country, selected_series)

                # Display result count
                st.markdown(f"**Results:** {len(type_results):,} coin types")

                # Render results
                self.render_types_results(type_results)
            elif selected_country:
                # Country selected but no series
                st.info("👆 Select a series above to view coin types")
            else:
                # No country selected
                st.info("👆 Select a country above to begin")

            # Add help information
            with st.expander("ℹ️ About Coin Types"):
                st.markdown("""
                **Coin Types represent individual coins with specific:**
                - Year of minting
                - Mint mark (if applicable)
                - Variety (special characteristics or errors)
                - Mintage (number produced)

                Each coin type belongs to a coin master which defines the series, denomination, and specifications.
                """)
