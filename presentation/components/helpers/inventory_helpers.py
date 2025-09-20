# inventory_helpers.py
"""Helper functions for inventory operations."""
import pandas as pd
import streamlit as st
from infrastructure.database.db_operations import execute_query_all, execute_query_single


def get_inventory_by_series_detail(series_name):
    """Get detailed inventory for a specific series."""
    # Check for specimen table and columns
    specimen_check = execute_query_single(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='specimen'"
    )

    flip_cte = ""
    flip_join = ""
    flip_select = ""

    if specimen_check:
        # Check if code column exists (NOT specimen_code)
        code_check = execute_query_single(
            "SELECT 1 FROM pragma_table_info('specimen') WHERE name='code'"
        )

        if code_check:
            # Check if sold_line_id column exists
            sold_check = execute_query_single(
                "SELECT 1 FROM pragma_table_info('specimen') WHERE name='sold_line_id'"
            )

            where_unsold = " WHERE sold_line_id IS NULL" if sold_check else ""
            flip_cte = f"""
                WITH flip AS (
                    SELECT lot_id, GROUP_CONCAT(code, ', ') AS flip_ids
                    FROM specimen{where_unsold}
                    GROUP BY lot_id
                )
            """
            flip_join = "LEFT JOIN flip f ON f.lot_id = l.id"
            flip_select = "COALESCE(f.flip_ids, '') AS 'Flip IDs',"

    query = f"""
        {flip_cte}
        SELECT
            cm.series AS Series,
            ct.year AS Year,
            ct.mint_mark AS 'Mint Mark',
            COALESCE(ct.variety, '') AS Variety,
            l.id AS lot_id,
            t.tx_date AS Acquired,
            COALESCE(p.name, '') AS Party,
            l.qty_remaining AS Qty,
            ROUND(l.unit_cost, 2) AS 'Unit Cost (USD)',
            ROUND(v.melt_unit_value, 4) AS 'Melt Unit Value',
            ROUND(v.chosen_unit_value, 2) AS 'Chosen Unit Value',
            ROUND(l.qty_remaining * COALESCE(v.chosen_unit_value, 0), 2) AS 'Lot Est. Value',
            COALESCE(l.estimated_grade_text, l.purchase_grade_text, '') AS Grade,
            {flip_select if flip_select else "'' AS 'Flip IDs',"}
            COALESCE(l.slab_cert, '') AS 'Cert #'
        FROM lot l
        JOIN tx_line tl ON tl.id = l.acquisition_line_id
        JOIN tx t ON t.id = tl.tx_id
        LEFT JOIN party p ON p.id = t.party_id
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
        {flip_join}
        WHERE l.qty_remaining > 0 AND cm.series = ?
        ORDER BY ct.year, ct.mint_mark, ct.variety, l.id
    """

    return execute_query_all(query, (series_name,))


def get_inventory_by_flags(want_proofs=False, want_slabbed=False):
    """Get inventory filtered by flags (proofs, slabbed)."""
    where_conditions = ["l.qty_remaining > 0"]
    params = []

    if want_proofs:
        where_conditions.append("ct.is_proof = 1")

    if want_slabbed:
        where_conditions.append(
            "(COALESCE(l.slab_cert, '') <> '' OR "
            "UPPER(COALESCE(l.purchase_grade_company, '')) IN ('PCGS','NGC','ANACS','ICG'))"
        )

    # Check for specimen table and columns
    specimen_check = execute_query_single(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='specimen'"
    )

    flip_cte = ""
    flip_join = ""
    flip_select = ""

    if specimen_check:
        # Check if code column exists (NOT specimen_code)
        code_check = execute_query_single(
            "SELECT 1 FROM pragma_table_info('specimen') WHERE name='code'"
        )

        if code_check:
            # Check if sold_line_id column exists
            sold_check = execute_query_single(
                "SELECT 1 FROM pragma_table_info('specimen') WHERE name='sold_line_id'"
            )

            where_unsold = " WHERE sold_line_id IS NULL" if sold_check else ""
            flip_cte = f"""
                WITH flip AS (
                    SELECT lot_id, GROUP_CONCAT(code, ', ') AS flip_ids
                    FROM specimen{where_unsold}
                    GROUP BY lot_id
                )
            """
            flip_join = "LEFT JOIN flip f ON f.lot_id = l.id"
            flip_select = "COALESCE(f.flip_ids, '') AS \"Flip IDs\","

    query = f"""
        {flip_cte}
        SELECT
            cm.series AS Series,
            ct.year AS Year,
            ct.mint_mark AS "Mint Mark",
            COALESCE(ct.variety, '') AS Variety,
            l.id AS lot_id,
            l.qty_remaining AS Qty,
            ROUND(l.unit_cost, 2) AS "Unit Cost (USD)",
            ROUND(v.melt_unit_value, 4) AS "Melt Unit Value",
            ROUND(v.chosen_unit_value, 2) AS "Chosen Unit Value",
            ROUND(l.qty_remaining * COALESCE(v.chosen_unit_value, 0), 2) AS "Lot Est. Value",
            CASE WHEN ct.is_proof = 1 THEN 'Yes' ELSE 'No' END AS Proof,
            CASE WHEN (COALESCE(l.slab_cert, '') <> '' OR 
                      UPPER(COALESCE(l.purchase_grade_company, '')) IN ('PCGS','NGC','ANACS','ICG'))
                 THEN 'Yes' ELSE 'No' END AS Slabbed,
            {flip_select}
            COALESCE(l.estimated_grade_text, l.purchase_grade_text, '') AS Grade
        FROM lot l
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
        {flip_join}
        WHERE {" AND ".join(where_conditions)}
        ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety, l.id
    """

    return execute_query_all(query, params)


def format_year_columns_for_display(df: pd.DataFrame) -> pd.DataFrame:
    """Format year columns for display (handle NaN values)."""
    if df is None or df.empty:
        return df

    out = df.copy()
    year_columns = [c for c in out.columns if c.lower() in {"year", "years_start", "years_end"}]

    for col in year_columns:
        out[col] = pd.to_numeric(out[col], errors="coerce").map(
            lambda x: "" if pd.isna(x) else f"{int(x)}"
        )

    return out


def format_money_columns(df: pd.DataFrame, columns, keep_melt_precision=False):
    """
    Return display copy with currency formatting; original df stays numeric for CSV.

    Args:
        df: DataFrame to format
        columns: List of column names to format as currency
        keep_melt_precision: If True, keeps 4 decimal places for "Melt Unit Value"
    """
    if df is None or df.empty:
        return df, df

    display_df = df.copy()

    for col in columns:
        if col in display_df.columns:
            # Special handling for Melt Unit Value - keep 4 decimal places
            if keep_melt_precision and col == "Melt Unit Value":
                display_df[col] = pd.to_numeric(display_df[col], errors="coerce").fillna(0.0).map(
                    lambda x: f"${x:,.4f}"
                )
            else:
                # Standard 2 decimal place formatting for other money columns
                display_df[col] = pd.to_numeric(display_df[col], errors="coerce").fillna(0.0).map(
                    lambda x: f"${x:,.2f}"
                )

    return display_df, df


def create_download_button(label: str, df: pd.DataFrame, filename: str):
    """Create a CSV download button."""
    st.download_button(
        label,
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
    )
