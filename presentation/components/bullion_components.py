# presentation/components/bullion_components.py
"""Bullion UI components - Single Responsibility: Bullion rendering logic"""
import streamlit as st
import pandas as pd
from typing import List, Optional
from infrastructure.database.repositories.bullion_repository import (
    BullionDataRepository,
    SpotPrice,
    BullionSummary,
    BullionDetail,
    BullionTotals
)


class BullionRenderer:
    """Handles all bullion UI rendering - Single Responsibility"""

    def __init__(self, repo: BullionDataRepository):
        """Inject bullion repository dependency"""
        self.repo = repo

    def render_spot_prices(self):
        """Render the latest spot prices section for context."""
        spots = self.repo.get_latest_spot_prices()

        if not spots:
            st.info("No spot prices found. Update them in Admin → Metal Prices.")
            return

        st.caption("Latest Precious Metal spot prices.")

        # Convert to DataFrame for display
        spot_data = [{'metal': s.metal, 'price_per_oz_usd': s.price_per_oz_usd} for s in spots]
        spot_df = pd.DataFrame(spot_data).rename(columns={
            "metal": "Metal",
            "price_per_oz_usd": "Price per oz (USD)"
        })

        st.dataframe(spot_df, hide_index=True, width='stretch', column_config={
            "Metal": st.column_config.TextColumn(),
            "Price per oz (USD)": st.column_config.NumberColumn(format="$%.2f"),
        })

    def render_totals_summary(self):
        """Render the bullion totals summary metrics."""
        totals = self.repo.get_bullion_totals()

        if not totals or not totals.total_units:
            return  # No totals to display

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Units", f"{totals.total_units:,}")
        col2.metric("Total Fine Oz", f"{totals.total_fine_oz:,.2f}")
        col3.metric("Total Melt Value", f"${totals.total_value:,.2f}")
        st.divider()

    def render_category_tab(self):
        """Render the 'By Category' tab with combined bullion and constitutional data."""
        combined_data = self.repo.get_combined_category_data()

        if not combined_data:
            st.info(
                "No bullion (ROUND/BAR/BULLION COIN) or Junk Silver (MELT_ONLY COINS) detected yet. "
                "Set 'asset_category' on your Coin Master records."
            )
            return

        # Convert to DataFrame
        df = self._convert_category_data_to_dataframe(combined_data)

        # Apply safe formatting
        format_spec = {
            "Units": "{:,.0f}",
            "Gross oz": "{:.4f}",
            "Fine oz": "{:.4f}",
            "Melt Value (USD)": "${:,.2f}"
        }

        styled_df = self._safe_format_dataframe(df.copy(), format_spec)
        st.dataframe(styled_df, hide_index=True, width='stretch')

        # Download button
        self._create_download_button(
            "Download CSV (By Category)",
            df,
            "bullion_by_category.csv"
        )

    def render_series_tab(self):
        """Render the 'By Series' tab with detailed series breakdown."""
        combined_data = self.repo.get_combined_series_data()

        if not combined_data:
            st.info(
                "No bullion (ROUND/BAR/BULLION COIN) or Junk Silver (MELT ONLY COINS) detected yet. "
                "Set 'asset_category' on your Coin Master records."
            )
            return

        # Convert to DataFrame
        df = self._convert_series_data_to_dataframe(combined_data)

        # Apply safe formatting
        format_spec = {
            "Units": "{:,.0f}",
            "Unit troy oz": "{:.4f}",
            "Unit fine oz": "{:.4f}",
            "Gross oz": "{:.4f}",
            "Fine oz": "{:.4f}",
            "Melt Value (USD)": "${:,.2f}"
        }

        styled_df = self._safe_format_dataframe(df.copy(), format_spec)
        st.dataframe(styled_df, hide_index=True, width='stretch')

        # Download button
        self._create_download_button(
            "Download CSV (By Series)",
            df,
            "bullion_by_series.csv"
        )

    def render_footer_sections(self):
        """Render the footer tip and help sections."""
        st.markdown("---")
        st.caption(
            "💡 **Tip:** Use your Coin Master editor to set **asset_category = ROUND, BAR, or BULLION COIN** "
            "on products like generic Buffalo rounds, APMEX bars, 10 oz bars, etc. "
            "Valuation uses your melt setup via weight × fineness × spot price."
        )

        # Show which asset categories are included
        with st.expander("ℹ️ What counts as bullion?"):
            st.markdown("""
            This page shows items with the following asset_category values:
            - **ROUND** - Generic rounds, non-government issue
            - **BAR** - Bars of any size
            - **BULLION COIN** - Government-issued bullion coins (ASE, Maple Leaf, etc.)

            Regular **COIN** category items are not shown here - they appear in the main Inventory pages.
            """)

        # Add diagnostic info
        with st.expander("⚠️ Seeing $0 values?"):
            st.markdown("""
            If you're seeing $0 melt values, check that your coin_master records have:
            1. **metal** set (Ag, Au, Pt, Pd)
            2. **weight_grams** set (e.g., 31.103 for 1 troy oz)
            3. **fineness** set (e.g., 0.999 for .999 fine silver)
            4. **Metal prices** updated in Admin → Metal Prices

            You can update these in Admin → Coin Master Editor.
            """)

    def _convert_category_data_to_dataframe(self,
                                            category_data: List[BullionSummary]) -> pd.DataFrame:
        """Convert category data to DataFrame with appropriate column names."""
        data = []
        for item in category_data:
            data.append({
                'Category': item.category,
                'Metal': item.metal,
                'Units': item.units_on_hand,
                'Gross oz': item.gross_oz,
                'Fine oz': item.fine_oz,
                'Melt Value (USD)': item.melt_value_usd
            })

        df = pd.DataFrame(data)

        # Handle NULL values before returning
        numeric_cols = ['Units', 'Gross oz', 'Fine oz', 'Melt Value (USD)']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        return df

    def _convert_series_data_to_dataframe(self, series_data: List[BullionDetail]) -> pd.DataFrame:
        """Convert series data to DataFrame with appropriate column names."""
        data = []
        for item in series_data:
            data.append({
                'Category': item.category,
                'Metal': item.metal,
                'Series': item.series,
                'Unit troy oz': item.unit_troy_oz,
                'Unit fine oz': item.unit_fine_oz,
                'Units': item.units_on_hand,
                'Gross oz': item.gross_oz,
                'Fine oz': item.fine_oz,
                'Melt Value (USD)': item.melt_value_usd
            })

        df = pd.DataFrame(data)

        # Handle NULL values before returning
        numeric_cols = ['Unit troy oz', 'Unit fine oz', 'Units', 'Gross oz', 'Fine oz',
                        'Melt Value (USD)']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        return df

    def _safe_format_dataframe(self, df: pd.DataFrame, format_spec: dict) -> pd.DataFrame:
        """Apply formatting to dataframe, handling None/NULL values safely."""
        if df.empty:
            return df

        # Replace None values with 0 for numeric columns before formatting
        for col in format_spec.keys():
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        try:
            return df.style.format(format_spec)
        except Exception as e:
            st.warning(f"Could not apply formatting: {e}")
            return df

    def _create_download_button(self, label: str, df: pd.DataFrame, filename: str):
        """Create a CSV download button."""
        st.download_button(
            label,
            data=df.to_csv(index=False).encode("utf-8"),
            file_name=filename,
            mime="text/csv",
        )
