
# pages/10_Inventory.py
import streamlit as st
import pandas as pd
from db import get_conn

st.header("Inventory")

# ---------------------------
# Helpers
# ---------------------------
def table_exists(cx, name: str) -> bool:
    return cx.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name=?",
        (name,)
    ).fetchone() is not None

def column_exists(cx, table: str, column: str) -> bool:
    # PRAGMA can't be parameterized, so we interpolate a vetted table name
    if not table:
        return False
    rows = cx.execute(f"PRAGMA table_info({table})").fetchall()
    cols = {r[1] for r in rows}  # r[1] is the column name
    return column in cols

def list_series():
    with get_conn() as cx:
        rows = cx.execute("SELECT DISTINCT series FROM coin_master ORDER BY series").fetchall()
        return [r[0] for r in rows]

def _fmt_year_cols_for_display(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    yearish = [c for c in out.columns if c.lower() in {"year","years_start","years_end"}]
    for col in yearish:
        out[col] = pd.to_numeric(out[col], errors="coerce").map(lambda x: "" if pd.isna(x) else f"{int(x)}")
    return out

def _money_cols(df: pd.DataFrame, cols):
    """Return a display copy with currency formatting; original df stays numeric for CSV."""
    if df is None or df.empty:
        return df, df
    disp = df.copy()
    for c in cols:
        if c in disp.columns:
            disp[c] = pd.to_numeric(disp[c], errors="coerce").fillna(0.0).map(lambda x: f"${x:,.2f}")
    return disp, df

def download_csv_button(label: str, df: pd.DataFrame, filename: str):
    st.download_button(
        label,
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
    )

# ---------------------------
# Views
# ---------------------------
tab_type, tab_series, tab_series_detail, tab_flags = st.tabs(
    ["By Type", "By Series (summary)", "Filter by Series (detail)", "Filter by Flags"]
)

# ===== By Type =====
with tab_type:
    with get_conn() as cx:
        sql = """        SELECT
          ct.id AS coin_type_id,
          cm.series,
          ct.year,
          ct.mint_mark,
          COALESCE(ct.variety,'') AS variety,
          SUM(l.qty_remaining) AS coins_on_hand
        FROM lot l
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        WHERE l.qty_remaining > 0
        GROUP BY ct.id, cm.series, ct.year, ct.mint_mark, ct.variety
        ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety
        """
        rows = cx.execute(sql).fetchall()
    df = pd.DataFrame([dict(r) for r in rows])
    if df.empty:
        st.info("No inventory yet.")
    else:
        # Hide internal ID and put Series first
        if "coin_type_id" in df.columns:
            df = df.drop(columns=["coin_type_id"])
        first = [c for c in ["series","year","mint_mark","variety","coins_on_hand"] if c in df.columns]
        df = df[first + [c for c in df.columns if c not in first]]

        # Friendly labels
        df = df.rename(columns={
            "series": "Series",
            "year": "Year",
            "mint_mark": "Mint Mark",
            "variety": "Variety",
            "coins_on_hand": "Qty on Hand",
        })
        # Display formatting
        disp = _fmt_year_cols_for_display(df)
        st.dataframe(disp, use_container_width=True, hide_index=True)
        download_csv_button("Download CSV (By Type)", df, "inventory_by_type.csv")

# ===== By Series (summary) =====
with tab_series:
    with get_conn() as cx:
        if table_exists(cx, "v_lot_value_details"):
            sql = """            SELECT
              series,
              SUM(qty_remaining) AS coins,
              ROUND(SUM(qty_remaining * COALESCE(chosen_unit_value,0)), 2) AS est_value_usd
            FROM v_lot_value_details
            GROUP BY series
            ORDER BY est_value_usd DESC, series
            """
        else:
            sql = """            SELECT cm.series AS series, SUM(l.qty_remaining) AS coins, NULL AS est_value_usd
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE l.qty_remaining > 0
            GROUP BY cm.series
            ORDER BY coins DESC, cm.series
            """
        rows = cx.execute(sql).fetchall()
    df = pd.DataFrame([dict(r) for r in rows])
    if df.empty:
        st.info("No inventory yet.")
    else:
        df = df.rename(columns={"series":"Series","coins":"Coins","est_value_usd":"Est. Value (USD)"})
        disp, csv_df = _money_cols(df, ["Est. Value (USD)"])
        st.dataframe(disp, use_container_width=True, hide_index=True)
        download_csv_button("Download CSV (Series Summary)", csv_df, "inventory_by_series_summary.csv")

# ===== Filter by Series (detail) =====
with tab_series_detail:
    series_list = list_series()
    if not series_list:
        st.info("No series found in catalog (coin_master).")
    else:
        pick = st.selectbox("Series", options=series_list, key="inv_series_pick")
        with get_conn() as cx:
            has_specimen = table_exists(cx, "specimen")
            has_specimen_code = column_exists(cx, "specimen", "specimen_code") if has_specimen else False
            has_sold_line_id = column_exists(cx, "specimen", "sold_line_id") if has_specimen else False

            cte = ""
            join_flip = ""
            if has_specimen and has_specimen_code:
                where_unsold = " WHERE sold_line_id IS NULL" if has_sold_line_id else ""
                cte = f"""WITH flip AS (
  SELECT lot_id, GROUP_CONCAT(specimen_code, ', ') AS flip_ids
  FROM specimen{where_unsold}
  GROUP BY lot_id
)
"""
                join_flip = "LEFT JOIN flip f ON f.lot_id = l.id"

            sql = f"""{cte}SELECT
  cm.series AS Series,
  ct.year   AS Year,
  ct.mint_mark AS "Mint Mark",
  COALESCE(ct.variety,'') AS Variety,
  l.id AS lot_id,
  t.tx_date AS Acquired,
  COALESCE(p.name,'') AS Party,
  l.qty_remaining AS Qty,
  ROUND(l.unit_cost, 2) AS "Unit Cost (USD)",
  ROUND(v.melt_unit_value, 4) AS "Melt Unit Value",
  ROUND(v.chosen_unit_value, 2) AS "Chosen Unit Value",
  ROUND(l.qty_remaining * COALESCE(v.chosen_unit_value,0), 2) AS "Lot Est. Value",
  COALESCE(l.estimated_grade_text, l.purchase_grade_text) AS Grade,
  { "COALESCE(f.flip_ids, '') AS \"Flip IDs\"," if join_flip else "'' AS \"Flip IDs\"," }
  COALESCE(l.slab_cert,'') AS "Cert #"
FROM lot l
JOIN tx_line tl ON tl.id = l.acquisition_line_id
JOIN tx t ON t.id = tl.tx_id
LEFT JOIN party p ON p.id = t.party_id
JOIN coin_type ct ON ct.id = l.coin_type_id
JOIN coin_master cm ON cm.id = ct.master_id
LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
{join_flip}
WHERE l.qty_remaining > 0 AND cm.series = ?
ORDER BY ct.year, ct.mint_mark, ct.variety, l.id
"""
            rows = cx.execute(sql, (pick,)).fetchall()
        df = pd.DataFrame([dict(r) for r in rows])
        if df.empty:
            st.info("No on-hand lots for this series.")
        else:
            disp = _fmt_year_cols_for_display(df)
            st.dataframe(disp, use_container_width=True, hide_index=True)
            download_csv_button("Download CSV (Series Detail)", df, f"{pick}_detail.csv".replace(" ","_"))

# ===== Filter by Flags =====
with tab_flags:
    c1, c2 = st.columns(2)
    want_proofs = c1.checkbox("Proofs only", value=False, key="inv_flag_proofs")
    want_slabbed = c2.checkbox("Slabbed only (has cert or PCGS/NGC/ANACS/ICG)", value=False, key="inv_flag_slabbed")

    where = ["l.qty_remaining > 0"]
    if want_proofs:
        where.append("(ct.is_proof = 1)")
    if want_slabbed:
        where.append("(COALESCE(l.slab_cert,'') <> '' OR UPPER(COALESCE(l.purchase_grade_company,'')) IN ('PCGS','NGC','ANACS','ICG'))")

    with get_conn() as cx:
        sql = f"""        SELECT
          cm.series AS Series,
          ct.year   AS Year,
          ct.mint_mark AS "Mint Mark",
          COALESCE(ct.variety,'') AS Variety,
          l.id AS lot_id,
          l.qty_remaining AS Qty,
          ROUND(l.unit_cost, 2) AS "Unit Cost (USD)",
          ROUND(v.melt_unit_value, 4) AS "Melt Unit Value",
          ROUND(v.chosen_unit_value, 2) AS "Chosen Unit Value",
          ROUND(l.qty_remaining * COALESCE(v.chosen_unit_value,0), 2) AS "Lot Est. Value",
          CASE WHEN ct.is_proof = 1 THEN 'Yes' ELSE 'No' END AS Proof,
          CASE WHEN (COALESCE(l.slab_cert,'') <> '' OR UPPER(COALESCE(l.purchase_grade_company,'')) IN ('PCGS','NGC','ANACS','ICG')) THEN 'Yes' ELSE 'No' END AS Slabbed
        FROM lot l
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        LEFT JOIN v_lot_value_details v ON v.lot_id = l.id
        WHERE {" AND ".join(where)}
        ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety, l.id
        """
        rows = cx.execute(sql).fetchall()
    df = pd.DataFrame([dict(r) for r in rows])

    if df.empty:
        st.info("No lots matched those flags.")
    else:
        disp = _fmt_year_cols_for_display(df)
        disp, csv_df = _money_cols(disp, ["Unit Cost (USD)","Chosen Unit Value","Lot Est. Value"])
        st.dataframe(disp, use_container_width=True, hide_index=True)
        download_csv_button("Download CSV (Flags)", df, "inventory_filter_flags.csv")
