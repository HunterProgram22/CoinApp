
# pages/5_Quick_Import_Templates.py
import streamlit as st
import pandas as pd
from queries import (
    upsert_coin_master, upsert_coin_type, upsert_storage,
    create_buy_transaction, create_sell_transaction,
)

st.header("⚡ Quick Import (Templates)")
st.caption("Use the provided coin_lines_template.csv or .xlsx with exact headers. This importer now normalizes 'nan/None/—/-' in Mint Mark & Variety to blanks.")

uploaded = st.file_uploader("Upload template file", type=["csv", "xlsx"])  # .xlsx needs openpyxl

NAN_LIKE = {"nan","NaN","none","None","-","—"}

def norm_text(x: object) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    return "" if s in NAN_LIKE or s.lower() in NAN_LIKE else s

def read_any(f):
    name = f.name.lower()
    if name.endswith(".xlsx"):
        try:
            return pd.read_excel(f)
        except Exception as e:
            st.error(f"Unable to read Excel: {e}. Make sure 'openpyxl' is installed.")
            st.stop()
    # For CSV, avoid default NA -> NaN for strings; we want to keep literal 'NA' if present
    return pd.read_csv(f, keep_default_na=False)

TEMPLATE_REQUIRED = [
    # Minimal required to import
    'tx_date','tx_type','country','denomination','series','year','mint_mark','variety','quantity','unit_price'
]
# Optional columns we will use if present
OPTIONAL = [
    'party','currency','shipping','tax','fees','notes',
    'purchase_grade_company','purchase_grade_text','purchase_numeric_grade',
    'estimated_grade_text','estimated_numeric_grade','valuation_method','manual_est_unit_value','storage_location'
]

if uploaded is not None:
    df = read_any(uploaded)
    # normalize column names: strip spaces
    df.columns = [c.strip() for c in df.columns]
    st.subheader("Preview")
    st.dataframe(df.head(20))

    missing = [c for c in TEMPLATE_REQUIRED if c not in df.columns]
    if missing:
        st.error("Missing required columns in your file: " + ", ".join(missing))
        st.stop()

    # Ensure optional columns exist
    for c in OPTIONAL:
        if c not in df.columns:
            df[c] = None

    # Clean types
    df['tx_date'] = pd.to_datetime(df['tx_date'], errors='coerce').dt.date
    df['tx_type'] = df['tx_type'].astype(str).str.strip().str.upper()
    # IMPORTANT: normalize mint_mark & variety BEFORE grouping / inserting
    df['mint_mark'] = df['mint_mark'].apply(norm_text)
    df['variety']   = df['variety'].apply(norm_text)

    # numeric conversions
    df['quantity']  = pd.to_numeric(df['quantity'], errors='coerce').fillna(0).astype(int)
    df['unit_price']= pd.to_numeric(df['unit_price'], errors='coerce').fillna(0.0)

    if df['tx_date'].isna().any() or (~df['tx_type'].isin(['BUY','SELL'])).any():
        st.error("Some rows have invalid dates or tx types (must be BUY/SELL). Fix the template and re-upload.")
        st.stop()

    dry_run = st.checkbox("Dry run (validate only—don’t write)", value=True)

    if st.button("Validate & Import from Template"):
        problems = []
        created_tx = 0
        created_lines = 0

        # Group by tx header tuple (similar to template guidance)
        grp_cols = ['tx_date','tx_type','party']
        gdf = df.copy()

        # Sum per-transaction charges across rows in the group
        for col in ['shipping','tax','fees']:
            if col in gdf.columns:
                gdf[col] = pd.to_numeric(gdf[col], errors='coerce').fillna(0.0)
            else:
                gdf[col] = 0.0

        for (tx_date, tx_type, party), part in gdf.groupby(grp_cols, dropna=False):
            tx_date_iso = tx_date.isoformat() if hasattr(tx_date,'isoformat') else str(tx_date)
            currency = (part['currency'].dropna().astype(str).str.strip().replace({'':''}).iloc[0]
                        if 'currency' in part.columns and not part['currency'].dropna().empty else 'USD')
            currency = currency or 'USD'
            ship = float(part['shipping'].sum())
            tax = float(part['tax'].sum())
            fees = float(part['fees'].sum())
            notes = None  # leave empty; row-level notes go to lot

            items = []
            for _, row in part.iterrows():
                # Resolve coin type via catalog fields (template guarantees presence)
                try:
                    year = int(row['year'])
                except Exception:
                    problems.append(f"Invalid year: {row['year']}")
                    continue

                country      = str(row['country']).strip()
                denomination = str(row['denomination']).strip()
                series       = str(row['series']).strip()
                mint_mark    = norm_text(row['mint_mark'])
                variety      = norm_text(row['variety'])

                master_id = upsert_coin_master(country, denomination, series)
                coin_type_id = upsert_coin_type(master_id, year, mint_mark, variety)

                # Grades & valuation
                def fnum(v):
                    try:
                        return float(v) if v is not None and str(v) != '' else None
                    except Exception:
                        return None
                valuation = str(row.get('valuation_method') or 'AUTO').upper().strip()
                if valuation not in ('AUTO','MELT_ONLY','GUIDE_ONLY','MANUAL'):
                    valuation = 'AUTO'

                # Storage (create on the fly)
                storage_name = row.get('storage_location')
                if storage_name and str(storage_name).strip():
                    storage_id = upsert_storage(str(storage_name).strip())
                else:
                    storage_id = None

                items.append({
                    'coin_type_id': coin_type_id,
                    'quantity': int(row['quantity'] or 0),
                    'unit_price': float(row['unit_price'] or 0.0),
                    'purchase_grade_company': row.get('purchase_grade_company'),
                    'purchase_grade_text': row.get('purchase_grade_text'),
                    'purchase_numeric_grade': fnum(row.get('purchase_numeric_grade')),
                    'slab_cert': None,
                    'estimated_grade_text': row.get('estimated_grade_text'),
                    'estimated_numeric_grade': fnum(row.get('estimated_numeric_grade')),
                    'valuation_method': valuation,
                    'manual_est_unit_value': fnum(row.get('manual_est_unit_value')),
                    'storage_location_id': storage_id,
                    'lot_notes': row.get('notes'),
                })

            if dry_run:
                created_tx += 1
                created_lines += len(items)
                continue

            try:
                if tx_type == 'BUY':
                    create_buy_transaction(tx_date_iso, party, currency, ship, tax, fees, notes, items)
                elif tx_type == 'SELL':
                    sell_items = [{"coin_type_id": it["coin_type_id"], "quantity": it["quantity"], "unit_price": it["unit_price"]} for it in items]
                    create_sell_transaction(tx_date_iso, party, currency, ship, tax, fees, notes, sell_items, method='FIFO')
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
