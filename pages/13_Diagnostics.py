
# pages/13_Diagnostics.py
import streamlit as st
import os, hashlib
from pathlib import Path
from db import get_conn

st.set_page_config(page_title="Diagnostics", page_icon="🧪", layout="wide")
st.title("🧪 Diagnostics")

# --- Version stamp (ENV or VERSION file) ---
build_sha = os.getenv("BUILD_SHA") or os.getenv("GIT_SHA")
if not build_sha and Path("VERSION").exists():
    try:
        build_sha = Path("VERSION").read_text(encoding="utf-8").strip()
    except Exception:
        build_sha = None

st.subheader("Build / Commit")
st.write("Commit/Build:", build_sha or "unknown")
st.caption("Set BUILD_SHA or add a VERSION file to stamp builds.")

# --- DB info ---
st.subheader("Database")
db_url = os.getenv("TURSO_DATABASE_URL", "")
redacted = ""
if db_url:
    # redact token-like parts
    if "@" in db_url:
        redacted = db_url.split("@")[-1]
    else:
        redacted = db_url[-40:]
st.write("Driver:", "libSQL / SQLite compatible")
st.write("URL (redacted host):", redacted or "(not set)")

try:
    with get_conn() as cx:
        v = cx.execute("select sqlite_version() as v").fetchone()
        st.write("sqlite_version():", v["v"] if isinstance(v, dict) or hasattr(v,'keys') else v[0])
except Exception as e:
    st.warning(f"Could not query sqlite_version(): {e}")

# --- File hashes for sync confidence ---
st.subheader("Key file hashes (SHA-1)")
files = [
    "app.py","db.py","queries.py",
    "pages/1_Dashboard.py","pages/2_Add_Transaction.py","pages/3_Inventory.py",
    "pages/4_Import.py","pages/5_Transactions.py","pages/6_Settings.py",
    "pages/8_Admin.py","pages/9_Data_Import.py","pages/10_Type_Sets.py",
    "pages/10_Bullion.py","pages/11_Coin_Catalog.py","pages/12_DB_Patches.py"
]
rows = []
for f in files:
    p = Path(f)
    if p.exists() and p.is_file():
        try:
            b = p.read_bytes()
            h = hashlib.sha1(b).hexdigest()
            rows.append((f, h[:12], p.stat().st_size))
        except Exception as e:
            rows.append((f, f"error: {e}", 0))
    else:
        rows.append((f, "(missing)", 0))

st.dataframe(
    {"file": [r[0] for r in rows], "sha1_12": [r[1] for r in rows], "bytes": [r[2] for r in rows]},
    use_container_width=True
)

st.caption("Share the sha1_12 values with me so I can target patches exactly to your current files.")
