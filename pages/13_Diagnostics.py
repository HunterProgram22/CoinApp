
# pages/13_Diagnostics.py
import streamlit as st
import os, hashlib
from pathlib import Path
from db import get_conn

st.set_page_config(page_title="Diagnostics", page_icon="🧪", layout="wide")
st.title("🧪 Diagnostics")

# ---- Build / Commit stamp ----
build_sha = os.getenv("BUILD_SHA") or os.getenv("GIT_SHA")
if not build_sha and Path("VERSION").exists():
    try:
        build_sha = Path("VERSION").read_text(encoding="utf-8").strip()
    except Exception:
        build_sha = None

st.subheader("Build / Commit")
st.write("Commit/Build:", build_sha or "unknown")
st.caption("Set BUILD_SHA (or GIT_SHA) or add a VERSION file to stamp builds.")

# ---- Database info ----
st.subheader("Database")
db_url = os.getenv("TURSO_DATABASE_URL", "")
driver = "Turso (libSQL)" if db_url else "SQLite (local file)"
st.write("Driver:", driver)

redacted = ""
if db_url:
    # redact token/creds; show only host/db
    try:
        redacted = db_url.split("@", 1)[-1]
    except Exception:
        redacted = "(set)"
st.write("URL (redacted):", redacted or "(not set)")

try:
    with get_conn() as cx:
        row = cx.execute("select sqlite_version() as v").fetchone()
        v = row["v"] if hasattr(row, "keys") else row[0]
        st.write("sqlite_version():", v)
except Exception as e:
    st.warning(f"Could not query sqlite_version(): {e}")

st.divider()

# ---- File hashes (sha1_12) in requested sidebar/page order ----
st.subheader("Key file hashes (sha1_12)")

def sha1_12(path: Path) -> str:
    try:
        b = path.read_bytes()
        return hashlib.sha1(b).hexdigest()[:12]
    except Exception as e:
        return f"(missing)"

files_in_order = [
    # Root app files (include both in case your repo uses either)
    "Home.py",
    "app.py",
    "db.py",
    "queries.py",

    # Pages in exact order requested
    "pages/1_Dashboard.py",
    "pages/2_Inventory.py",
    "pages/3_Type_Sets.py",
    "pages/4_Specimens.py",
    "pages/5_Transactions.py",
    "pages/6_World_Coins.py",
    "pages/7_Coin_Type_Editor.py",
    "pages/8_Admin.py",
    "pages/9_Data_Import.py",
    "pages/10_Bullion.py",
    "pages/11_Coin_Catalog.py",
    "pages/12_DB_Patches.py",
    "pages/13_Diagnostics.py",
]

rows = []
for f in files_in_order:
    p = Path(f)
    rows.append({
        "file": f,
        "sha1_12": sha1_12(p),
        "bytes": (p.stat().st_size if p.exists() else 0),
    })

st.dataframe(rows, use_container_width=True, hide_index=True)

st.caption("Copy the sha1_12 values for any files we edit so I can target patches exactly to your current code.")
