
# pages/5_Quick_Import_Templates.py (patched)
import streamlit as st
import pandas as pd
from queries import (
    upsert_coin_master, upsert_coin_type, upsert_storage,
    create_buy_transaction, create_sell_transaction,
)

st.header("⚡ Quick Import (Templates)")
st.caption("Upload coin_lines_template.csv or .xlsx with the exact headers to skip mapping.")

uploaded = st.file_uploader("Upload template file", type=["csv", "xlsx"])  # .xlsx needs openpyxl

def read_any(f):
    name = (f.name if hasattr(f, "name") else "upload").lower()
    if name.endswith(".xlsx"):
        try:
            return pd.read_excel(f)
        except Exception as e:
            st.error(f"Unable to read Excel: {e}. Make sure 'openpyxl' is installed, or upload CSV instead.")
            st.stop()
    return pd.read_csv(f)

def clean_money(series):
    # Strip $, commas, spaces, and any non-numeric (keeps minus and dot)
    return pd.to_numeric(series.astype(str).str.replace(r"[^0-9.\-]", "", regex=True), errors="coerce").fillna(0.0)

# Required headers for coin_lines_template
TEMPLATE_REQUIRED = [
    "tx_date","tx_type","country","denomination","series","year","mint_mark","variety","quantity","unit_price"
]

# Optional headers that will be used if present
OPTIONAL = [
    "party","currency","shipping","tax","fees","notes",
    "purchase_grade_company","purchase_grade_text","purchase_numeric_grade",
    "estimated_grade_text","estimated_numeric_grade","valuation_method","manual_est_unit_value","storage_location"
]

if uploaded is not None:
    df = read_any(uploaded)
    st.subheader("Preview")
    st.dataframe(df.head(20))

    # Validate required columns
    missing = [c for c in TEMPLATE_REQUIRED if c not in df.columns]
    if missing:
        st.error("Missing required columns in your file: " + ", ".join(missing))
        st.stop()

    # Ensure optional columns exist
    for c in OPTIONAL:
        if c not in df.columns:
            df[c] = None

    # Clean and normalize types
    df["tx_date"] = pd.to_datetime(df["tx_date"], errors="coerce").dt.date
    df["tx_type"] = df["tx_type"].astype(str).str.strip().str.upper()
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
    df["unit_price"] = clean_money(df["unit_price"])

    # Money-like optional fields
    for col in ["shipping","tax","fees","manual_est_unit_value","purchase_numeric_grade","estimated_numeric_grade"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if df["tx_date"].isna().any() or (~df["tx_type"].isin(["BUY","SELL"])).any():
        st.error("Some rows have invalid dates or tx types (must be BUY/SELL). Fix the template and re-upload.")
        st.stop()

    dry_run = st.checkbox("Dry run (validate only—don’t write)", value=True)

    if st.button("Validate & Import from Template"):
        problems = []
        created_tx = 0
        created_lines = 0

        # Pre-normalize per-transaction charges (strip $ etc.)
        gdf = df.copy()
        for col in ["shipping","tax","fees"]:
            gdf[col] = clean_money(gdf[col]) if col in gdf.columns else 0.0

        # Group rows into transactions by (date, type, party)
        grp_cols = ["tx_date","tx_type","party"]
        for (tx_date, tx_type, party), part in gdf.groupby(grp_cols, dropna=False):
            tx_date_iso = tx_date.isoformat() if hasattr(tx_date, "isoformat") else str(tx_date)
            # Currency: first non-empty else USD
            if "currency" in part.columns and not part["currency"].dropna().empty:
                currency = str(part["currency"].dropna().astype(str).str.strip().replace({"": "USD"}).iloc[0])
            else:
                currency = "USD"

            ship = float(part["shipping"].sum()) if "shipping" in part.columns else 0.0
            tax = float(part["tax"].sum()) if "tax" in part.columns else 0.0
            fees = float(part["fees"].sum()) if "fees" in part.columns else 0.0
            notes = None

            items = []

            def fnum(v):
                try:
                    return float(v) if v is not None and str(v) != "" else None
                except Exception:
                    return None

            for _, row in part.iterrows():
                # Create/attach to catalog entries
                try:
                    year = int(row["year"])
                except Exception:
                    problems.append(f"Invalid year: {row['year']}")
                    continue

                master_id = upsert_coin_master(str(row["country"]), str(row["denomination"]), str(row["series"]))
                mmark = str(row.get("mint_mark") or "").strip()
                if mmark in ("-", "—", "None", "nan"):
                    mmark = ""
                variety = str(row.get("variety") or "").strip()
                coin_type_id = upsert_coin_type(master_id, year, mmark, variety)

                valuation = str(row.get("valuation_method") or "AUTO").upper()
                if valuation not in ("AUTO","MELT_ONLY","GUIDE_ONLY","MANUAL"):
                    valuation = "AUTO"

                # Storage (auto-create if not existing)
                storage_name = row.get("storage_location")
                if storage_name and str(storage_name).strip():
                    storage_id = upsert_storage(str(storage_name).strip())
                else:
                    storage_id = None

                items.append({
                    "coin_type_id": coin_type_id,
                    "quantity": int(row["quantity"] or 0),
                    "unit_price": float(row["unit_price"] or 0.0),
                    "purchase_grade_company": row.get("purchase_grade_company"),
                    "purchase_grade_text": row.get("purchase_grade_text"),
                    "purchase_numeric_grade": fnum(row.get("purchase_numeric_grade")),
                    "slab_cert": None,
                    "estimated_grade_text": row.get("estimated_grade_text"),
                    "estimated_numeric_grade": fnum(row.get("estimated_numeric_grade")),
                    "valuation_method": valuation,
                    "manual_est_unit_value": fnum(row.get("manual_est_unit_value")),
                    "storage_location_id": storage_id,
                    "lot_notes": row.get("notes"),
                })

            if dry_run:
                created_tx += 1
                created_lines += len(items)
                continue

            try:
                if tx_type == "BUY":
                    create_buy_transaction(tx_date_iso, None if pd.isna(party) else party, currency, ship, tax, fees, notes, items)
                elif tx_type == "SELL":
                    sell_items = [{"coin_type_id": it["coin_type_id"], "quantity": it["quantity"], "unit_price": it["unit_price"]} for it in items]
                    create_sell_transaction(tx_date_iso, None if pd.isna(party) else party, currency, ship, tax, fees, notes, sell_items, method="FIFO")
                else:
                    problems.append(f"Unknown tx_type '{tx_type}'")
                    continue
                created_tx += 1
                created_lines += len(items)
            except Exception as e:
                problems.append(str(e))

        if dry_run:
            st.success(f"Dry run OK. Would create ~{created_tx} transactions and {created_lines} line items.")
        else:
            if problems:
                st.warning("Import finished with some issues:")
                for p in problems[:50]:
                    st.write("• ", p)
                if len(problems) > 50:
                    st.caption(f"...and {len(problems)-50} more")
            st.success(f"Imported {created_tx} transactions and {created_lines} line items.")
else:
    st.info("Upload coin_lines_template.csv or .xlsx with the exact header names.")
