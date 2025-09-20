# dashboard_helpers.py
"""Helper functions for dashboard operations and data processing."""

import numpy as np
import pandas as pd
import streamlit as st
from core.constants import METAL_DISPLAY_ORDER, SILVER_COIN_SPECS, DASHBOARD_COLUMN_RENAMES


def format_metal_prices_dataframe(spots_data):
    """Format metal prices data for display."""
    if not spots_data:
        return None
    
    df = pd.DataFrame(spots_data)
    
    # Apply friendly metal ordering
    if "metal" in df.columns:
        try:
            order = pd.Categorical(df["metal"], categories=METAL_DISPLAY_ORDER, ordered=True)
            df = df.assign(metal=order).sort_values("metal").assign(metal=df["metal"].astype(str))
        except Exception:
            pass
    
    # Apply friendly column names
    df = df.rename(columns=DASHBOARD_COLUMN_RENAMES)
    return df


def calculate_silver_melt_values(silver_spot_price):
    """Calculate melt values for common silver coins."""
    melt_data = []
    
    for coin_name, fine_oz in SILVER_COIN_SPECS.items():
        melt_value = round(silver_spot_price * fine_oz, 2)
        melt_data.append({
            "Item": coin_name,
            "Fine Oz": f"{fine_oz:.5f}",
            "Melt (USD)": f"${melt_value:,.2f}"
        })
    
    df = pd.DataFrame(melt_data).set_index("Item")
    return df


def calculate_series_unrealized_gl(df):
    """Add unrealized gain/loss calculations to series dataframe."""
    df = df.copy()
    
    # More robust null handling
    chosen_total = pd.to_numeric(df.get('chosen_total_usd', 0), errors='coerce').fillna(0)
    cost_total = pd.to_numeric(df.get('cost_total_usd', 0), errors='coerce').fillna(0)
    
    # Calculate unrealized G/L in dollars
    df['unreal_gl_usd'] = (chosen_total - cost_total).round(2)
    
    # Calculate unrealized G/L percentage - avoid division by zero
    df['unreal_gl_pct'] = np.where(
        cost_total > 0,
        (df['unreal_gl_usd'] / cost_total * 100).round(2),
        0.0
    )
    
    return df


def prepare_series_display_dataframe(df):
    """Prepare series dataframe for display with proper column ordering."""
    # Apply friendly column names
    df_display = df.rename(columns=DASHBOARD_COLUMN_RENAMES)
    
    # Define column order
    desired_columns = [
        'Series', 'Coins', 'Melt Value (USD)', 'Numismatic Value (USD)',
        'Total Cost (USD)', 'Est. Value (USD)', 'Unrealized G/L (USD)', 'Unrealized G/L (%)'
    ]
    
    # Only include columns that exist
    available_columns = [col for col in desired_columns if col in df_display.columns]
    return df_display[available_columns]


def get_series_column_config():
    """Get standardized column configuration for series data display."""
    return {
        'Coins': st.column_config.NumberColumn(format="%d"),
        'Melt Value (USD)': st.column_config.NumberColumn(format="$%.2f"),
        'Numismatic Value (USD)': st.column_config.NumberColumn(format="$%.2f"),
        'Total Cost (USD)': st.column_config.NumberColumn(format="$%.2f"),
        'Est. Value (USD)': st.column_config.NumberColumn(format="$%.2f"),
        'Unrealized G/L (USD)': st.column_config.NumberColumn(format="$%.2f"),
        'Unrealized G/L (%)': st.column_config.NumberColumn(format="%.2f"),
    }


def prepare_series_export_data(df):
    """Prepare series dataframe for CSV export."""
    export_columns = [
        'series', 'coins', 'melt_total_usd', 'numi_total_usd', 
        'cost_total_usd', 'chosen_total_usd', 'unreal_gl_usd', 'unreal_gl_pct'
    ]
    
    # Only include columns that exist
    available_columns = [col for col in export_columns if col in df.columns]
    df_export = df[available_columns].copy()
    
    # Round monetary columns to 2 decimals more efficiently
    monetary_columns = [
        'melt_total_usd', 'numi_total_usd', 'cost_total_usd', 
        'chosen_total_usd', 'unreal_gl_usd', 'unreal_gl_pct'
    ]
    
    for col in monetary_columns:
        if col in df_export.columns:
            df_export[col] = pd.to_numeric(df_export[col], errors='coerce').round(2)
    
    return df_export


def apply_gain_loss_styling(df):
    """Apply color styling to gain/loss columns."""
    def color_gl(val):
        """Color positive values green, negative red, zero/nan gray."""
        try:
            v = pd.to_numeric(val, errors='coerce')
            if pd.isna(v) or v == 0:
                return 'color: gray;'
            return 'color: green;' if v > 0 else 'color: red;'
        except Exception:
            return 'color: gray;'
    
    # Round monetary columns for display
    df_styled = df.copy()
    money_cols = ['Melt Value (USD)', 'Numismatic Value (USD)', 'Total Cost (USD)', 
                  'Est. Value (USD)', 'Unrealized G/L (USD)']
    pct_cols = ['Unrealized G/L (%)']
    
    # Round numeric columns more efficiently
    for col in money_cols + pct_cols:
        if col in df_styled.columns:
            df_styled[col] = pd.to_numeric(df_styled[col], errors='coerce').round(2)
    
    # Apply styling
    styled = df_styled.style
    
    if 'Unrealized G/L (USD)' in df_styled.columns:
        styled = styled.map(color_gl, subset=['Unrealized G/L (USD)'])
    
    if 'Unrealized G/L (%)' in df_styled.columns:
        styled = styled.map(color_gl, subset=['Unrealized G/L (%)'])
    
    # Format columns
    money_format = {col: "${:,.2f}" for col in money_cols if col in df_styled.columns}
    pct_format = {col: "{:,.2f}" for col in pct_cols if col in df_styled.columns}
    
    styled = styled.format({**money_format, **pct_format})
    
    return styled