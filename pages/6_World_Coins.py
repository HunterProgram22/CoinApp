
# pages/6_World_Coins.py
import streamlit as st
import pandas as pd
from db import get_conn

st.header("World Coins")

# ---------------------------------
# Helpers
# ---------------------------------
def table_exists(cx, name: str) -> bool:
    return cx.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name=?",
        (name,)
    ).fetchone() is not None

def column_exists(cx, table: str, column: str) -> bool:
    if not table:
        return False
    rows = cx.execute(f"PRAGMA table_info({table})").fetchall()
    cols = {r[1] for r in rows}  # r[1] is the column name
    return column in cols

def list_countries_on_hand() -> list[str]:
    with get_conn() as cx:
        rows = cx.execute(
            '''
            SELECT DISTINCT COALESCE(cm.country,'') AS country
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE l.qty_remaining > 0 AND COALESCE(cm.country,'') <> ''
            ORDER BY country
            '''
        ).fetchall()
    return [r["country"] for r in rows]

def _fmt_year_cols_for_display(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    yearish = [c for c in out.columns if c.lower() in {"year","years_start","years_end"}]
    for col in yearish:
        out[col] = pd.to_numeric(out[col], errors="coerce").map(lambda x: "" if pd.isna(x) else f"{int(x)}")
    return out

def _money_cols(df: pd.DataFrame, cols, keep=None):
    """Return (display_df, csv_df). Display has $2-decimals; csv keeps raw numeric.
       'keep' can list columns to leave as-is (e.g., melt per-unit to 4 dp)."""
    if df is None or df.empty:
        return df, df
    disp = df.copy()
    keep = set(keep or [])
    for c in cols:
        if c in disp.columns and c not in keep:
            disp[c] = pd.to_numeric(disp[c], errors="coerce").fillna(0.0).map(lambda x: f"${x:,.2f}")
    return disp, df

def download_csv_button(label: str, df: pd.DataFrame, filename: str):
    st.download_button(
        label,
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
    )

# ---------------------------------
# UI: country + filters
# ---------------------------------
countries = list_countries_on_hand()
if not countries:
    st.info("You currently have no on-hand world coins (country column empty).")
    st.stop()

c1, c2, c3, c4 = st.columns([2,1,1,1])
country = c1.selectbox("Country", options=countries, index=0, key="wc_country")

want_proofs = c2.checkbox("Proofs only", value=False, key="wc_proofs")
want_slabbed = c3.checkbox("Slabbed only", value=False, key="wc_slabbed")

# Optional asset_category filter if your schema has it
with get_conn() as cx:
    has_asset_cat = column_exists(cx, "coin_master", "asset_category")
if has_asset_cat:
    cat = c4.selectbox("Asset", options=["All","COIN","ROUND","BAR"], index=0, key="wc_asset")
else:
    cat = "All"

tab_sum, tab_detail = st.tabs(["Summary", "Detail"])

# Common WHERE parts
where = ["cm.country = ?","l.qty_remaining > 0"]
params = [country]
if want_proofs:
    where.append("ct.is_proof = 1")
if want_slabbed:
    where.append("(COALESCE(l.slab_cert,'') <> '' OR UPPER(COALESCE(l.purchase_grade_company,'')) IN ('PCGS','NGC','ANACS','ICG'))")
if has_asset_cat and cat != "All":
    where.append("cm.asset_category = ?")
    params.append(cat)

# ===== Summary =====
with tab_sum:
    with get_conn() as cx:
        if table_exists(cx, "v_lot_value_details"):
            sql = f"""
            SELECT
              cm.series AS Series,
              SUM(v.qty_remaining) AS Coins,
              ROUND(SUM(v.qty_remaining * COALESCE(v.melt_unit_value,0)), 2)  AS "Melt Value (USD)",
              ROUND(SUM(v.qty_remaining * COALESCE(v.chosen_unit_value,0)), 2) AS "Est. Value (USD)"
            FROM v_lot_value_details v
            JOIN lot l       ON l.id = v.lot_id
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE {" AND ".join(where)}
            GROUP BY cm.series
            ORDER BY "Est. Value (USD)" DESC, cm.series
            """
        else:
            # Fallback: counts only (no valuation view)
            sql = f"""
            SELECT
              cm.series AS Series,
              SUM(l.qty_remaining) AS Coins,
              NULL AS "Melt Value (USD)",
              NULL AS "Est. Value (USD)"
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE {" AND ".join(where)}
            GROUP BY cm.series
            ORDER BY Coins DESC, cm.series
            """
        rows = cx.execute(sql, params).fetchall()

    df = pd.DataFrame([dict(r) for r in rows])
    if df.empty:
        st.info("No on-hand inventory matched those filters.")
    else:
        disp, csv_df = _money_cols(df, ["Melt Value (USD)","Est. Value (USD)"])
        st.dataframe(disp, use_container_width=True, hide_index=True)
        download_csv_button(f"Download CSV (Summary — {country})", csv_df, f"world_summary_{country}.csv".replace(" ","_"))

# ===== Detail =====
with tab_detail:
    with get_conn() as cx:
        has_specimen = table_exists(cx, "specimen")
        has_specimen_code = column_exists(cx, "specimen", "specimen_code") if has_specimen else False
        has_sold_line_id = column_exists(cx, "specimen", "sold_line_id") if has_specimen else False

        cte = ""
        join_flip = ""
        if has_specimen and has_specimen_code:
            where_unsold = " WHERE sold_line_id IS NULL" if has_sold_line_id else ""
            cte = f"""
WITH flip AS (
  SELECT lot_id, GROUP_CONCAT(specimen_code, ', ') AS flip_ids
  FROM specimen{where_unsold}
  GROUP BY lot_id
)
"""
            join_flip = "LEFT JOIN flip f ON f.lot_id = l.id"

        if table_exists(cx, "v_lot_value_details"):
            sel_value_cols = """
              ROUND(v.melt_unit_value, 4) AS "Melt Unit Value",
              ROUND(v.chosen_unit_value, 2) AS "Chosen Unit Value",
              ROUND(l.qty_remaining * COALESCE(v.chosen_unit_value,0), 2) AS "Lot Est. Value",
            """
            join_val = "LEFT JOIN v_lot_value_details v ON v.lot_id = l.id"
        else:
            sel_value_cols = """
              NULL AS "Melt Unit Value",
              NULL AS "Chosen Unit Value",
              NULL AS "Lot Est. Value",
            """
            join_val = ""

        sql = f"""
{cte}SELECT
  cm.series AS Series,
  ct.year   AS Year,
  ct.mint_mark AS "Mint Mark",
  COALESCE(ct.variety,'') AS Variety,
  l.id AS lot_id,
  t.tx_date AS Acquired,
  COALESCE(p.name,'') AS Party,
  l.qty_remaining AS Qty,
  ROUND(l.unit_cost, 2) AS "Unit Cost (USD)",
  {sel_value_cols}
  COALESCE(l.estimated_grade_text, l.purchase_grade_text) AS Grade,
  { "COALESCE(f.flip_ids, '') AS \"Flip IDs\"," if join_flip else "'' AS \"Flip IDs\"," }
  COALESCE(l.slab_cert,'') AS "Cert #"
FROM lot l
JOIN tx_line tl   ON tl.id = l.acquisition_line_id
JOIN tx t         ON t.id = tl.tx_id
LEFT JOIN party p ON p.id = t.party_id
JOIN coin_type ct ON ct.id = l.coin_type_id
JOIN coin_master cm ON cm.id = ct.master_id
{join_val}
{join_flip}
WHERE {" AND ".join(where)}
ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety, l.id
"""
        rows = cx.execute(sql, params).fetchall()

    df = pd.DataFrame([dict(r) for r in rows])
    if df.empty:
        st.info("No lots matched those filters.")
    else:
        disp = _fmt_year_cols_for_display(df)
        # Money: format 2dp for totals; keep 4dp for Melt Unit Value
        disp, csv_df = _money_cols(disp, ["Unit Cost (USD)","Chosen Unit Value","Lot Est. Value"])
        if "Melt Unit Value" in disp.columns:
            disp["Melt Unit Value"] = pd.to_numeric(disp["Melt Unit Value"], errors="coerce").map(lambda x: "" if pd.isna(x) else f"{x:,.4f}")
        st.dataframe(disp, use_container_width=True, hide_index=True)
        download_csv_button(f"Download CSV (Detail — {country})", csv_df, f"world_detail_{country}.csv".replace(" ","_"))
