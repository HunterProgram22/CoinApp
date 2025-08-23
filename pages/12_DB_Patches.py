
# pages/12_DB_Patches.py
import streamlit as st
from pathlib import Path
from db import get_conn

st.set_page_config(page_title="DB Patches", page_icon="🧩", layout="wide")
st.title("🧩 Database Patches")
st.caption("Run .sql patch files against your database directly from the app.")

choice = st.radio("Patch source", ["Repo file (patches/…)", "Upload .sql file"], horizontal=True)

sql_text = ""
patch_path = None

if choice == "Repo file (patches/…)":
    pdir = Path("patches")
    files = []
    if pdir.exists():
        files = sorted([p for p in pdir.glob("*.sql")])
    if not files:
        st.warning("No .sql files found under `patches/`. Commit your patch (e.g., `patches/add_bullion_coin_category.sql`).")
    else:
        pick = st.selectbox("Choose patch file", files, format_func=lambda p: p.name)
        patch_path = pick
        sql_text = patch_path.read_text(encoding="utf-8", errors="ignore")
else:
    up = st.file_uploader("Upload a .sql file", type=["sql"])
    if up is not None:
        sql_text = up.read().decode("utf-8", errors="ignore")

if sql_text:
    with st.expander("Preview SQL", expanded=False):
        st.code(sql_text, language="sql")

def apply_sql(sql: str):
    # Execute statements separated by semicolons; skip purely whitespace lines.
    # Works for typical CREATE/DROP VIEW/TABLE patches (avoid semicolons inside string literals).
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    applied = 0
    with get_conn() as cx:
        for stmt in statements:
            try:
                cx.execute(stmt)
                applied += 1
            except Exception as e:
                st.error(f"Error on statement #{applied+1}: {e}\nSQL: {stmt[:300]}...")
                raise
    return applied

col1, col2 = st.columns([1,3])
with col1:
    run_btn = st.button("⚙️ Apply Patch", type="primary", disabled=(not bool(sql_text)))
with col2:
    if run_btn:
        try:
            n = apply_sql(sql_text)
            st.success(f"Patch applied successfully. Executed {n} statements.")
        except Exception:
            st.stop()

st.divider()
st.caption("Tip: After modifying views, reload pages that depend on them.")
