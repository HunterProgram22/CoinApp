
# pages/25_Coin_Catalog.py
import streamlit as st
import pandas as pd
from db import get_conn

st.title("📚 Coin Catalog")
st.caption("Filter your Master Coins and jump to Numista references.")

# --- helpers ---
def _distinct(col: str, where: str = "", params: tuple = ()):
    sql = f"SELECT DISTINCT {col} AS v FROM coin_master"
    if where:
        sql += f" WHERE {where}"
    sql += " ORDER BY 1"
    with get_conn() as cx:
        rows = cx.execute(sql, params).fetchall()
    return [r["v"] for r in rows]

def _query(country: str | None, denom: str | None, q: str | None):
    parts = []
    args = []
    if country and country != "All":
        parts.append("country = ?")
        args.append(country)
    if denom and denom != "All":
        parts.append("denomination = ?")
        args.append(denom)
    if q and q.strip():
        parts.append("LOWER(series) LIKE ?")
        args.append(f"%{q.strip().lower()}%")
    where = (" WHERE " + " AND ".join(parts)) if parts else ""
    sql = f'''
        SELECT id, country, denomination, series,
               years_start, years_end, metal, fineness, weight_grams,
               COALESCE(numista_url, '') AS numista_url
        FROM coin_master
        {where}
        ORDER BY country, denomination, series
    '''
    with get_conn() as cx:
        rows = cx.execute(sql, tuple(args)).fetchall()
    return [dict(r) for r in rows]

# --- filters ---
countries = ["All"] + _distinct("country")
c1, c2, c3 = st.columns([2,2,3])
pick_country = c1.selectbox("Country", countries, index=0)

if pick_country != "All":
    denoms = ["All"] + _distinct("denomination", "country = ?", (pick_country,))
else:
    denoms = ["All"] + _distinct("denomination")
pick_denom = c2.selectbox("Denomination", denoms, index=0)
search = c3.text_input("Search Series", placeholder="e.g., Morgan, Peace, Cent")

rows = _query(pick_country, pick_denom, search)
st.markdown(f"**Results:** {len(rows):,} master coins")

if not rows:
    st.info("No Master Coins found. Try relaxing the filters or import some masters first.")
    st.stop()

df = pd.DataFrame(rows)

# Pretty years
def _years(r):
    a, b = r.get("years_start"), r.get("years_end")
    if pd.isna(a) and pd.isna(b):
        return ""
    try:
        ai = int(a) if not pd.isna(a) else None
    except Exception:
        ai = None
    try:
        bi = int(b) if not pd.isna(b) else None
    except Exception:
        bi = None
    if ai is None and bi is None:
        return ""
    if ai is None:
        return f"–{bi}"
    if bi is None:
        return f"{ai}–"
    return f"{ai}–{bi}"

df["Years"] = df.apply(_years, axis=1)

# Reorder & rename
cols = ["country","denomination","series","Years","metal","fineness","weight_grams","numista_url"]
present = [c for c in cols if c in df.columns]
df = df[present]
df = df.rename(columns={
    "country": "Country",
    "denomination": "Denomination",
    "series": "Series",
    "metal": "Metal",
    "fineness": "Fineness",
    "weight_grams": "Wt (g)",
    "numista_url": "Numista"
})

# Display with LinkColumn if available (Streamlit ≥ 1.31)
try:
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Numista": st.column_config.LinkColumn("Numista", display_text="Open")
        },
    )
except Exception:
    st.dataframe(df, use_container_width=True, hide_index=True)

# CSV export
csv = df.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Download CSV", data=csv, file_name="coin_catalog.csv", mime="text/csv")
