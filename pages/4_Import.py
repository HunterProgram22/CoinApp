
# pages/4_Import.py
import streamlit as st
import pandas as pd
from queries import (
    upsert_coin_master, upsert_coin_type, upsert_storage,
    create_buy_transaction, create_sell_transaction,
    list_storage_locations,
)

st.header("Import from Excel/CSV")
st.caption("Upload a workbook or CSV, map your columns, preview, then import.")

NAN_LIKE = {"nan","NaN","none","None","-","—"}
def norm_text(x):
    if x is None: return ""
    s = str(x).strip()
    return "" if s in NAN_LIKE or s.lower() in NAN_LIKE else s


uploaded = st.file_uploader("Upload file", type=["xlsx", "csv"])  # requires openpyxl for .xlsx

if uploaded is not None:
    # Read file
    if uploaded.name.lower().endswith(".xlsx"):
        try:
            xls = pd.ExcelFile(uploaded)
            sheet_name = st.selectbox("Choose sheet", xls.sheet_names)
            df = xls.parse(sheet_name)
        except Exception as e:
            st.error(f"Couldn't read Excel: {e}. Try installing 'openpyxl' or upload as CSV.")
            st.stop()
    else:
        df = pd.read_csv(uploaded)

    if df.empty:
        st.warning("The selected sheet/file appears empty.")
        st.stop()

    st.subheader("Preview")
    st.dataframe(df.head(20))

    cols = ["— none —"] + list(df.columns)

    def guess_column(target_label: str):
        """Return a best-guess index for a label based on fuzzy contains, or 0 for none."""
        tl = target_label.lower().replace(" ", "")
        for c in df.columns:
            if tl in c.lower().replace(" ", ""):
                return cols.index(c)
        return 0

    st.markdown("### Required fields")
    c1, c2, c3 = st.columns(3)
    f_tx_date = c1.selectbox("Transaction Date (YYYY-MM-DD)", cols, index=guess_column("date"))
    f_tx_type = c2.selectbox("Transaction Type (BUY/SELL)", cols, index=guess_column("type"))
    f_quantity = c3.selectbox("Quantity", cols, index=guess_column("quantity"))
    f_unit_price = c1.selectbox("Unit Price (per coin)", cols, index=guess_column("unit price"))

    st.markdown("### Coin identification — choose **one** path")
    f_coin_type_id = st.selectbox("coin_type_id (if you already have IDs)", cols, index=guess_column("coin_type_id"))
    st.caption("OR provide catalog fields below (we'll create masters/types as needed).")
    c4, c5, c6 = st.columns(3)
    f_country = c4.selectbox("Country", cols, index=guess_column("country"))
    f_denom = c5.selectbox("Denomination", cols, index=guess_column("denomination"))
    f_series = c6.selectbox("Series", cols, index=guess_column("series"))
    c7, c8, c9 = st.columns(3)
    f_year = c7.selectbox("Year", cols, index=guess_column("year"))
    f_mint = c8.selectbox("Mint Mark", cols, index=guess_column("mint"))
    f_variety = c9.selectbox("Variety", cols, index=guess_column("variety"))

    st.markdown("### Optional fields")
    c10, c11, c12 = st.columns(3)
    f_party = c10.selectbox("Counterparty / Dealer", cols, index=guess_column("party"))
    f_currency = c11.selectbox("Currency", cols, index=guess_column("currency"))
    f_notes = c12.selectbox("Line Notes", cols, index=guess_column("notes"))

    c13, c14, c15 = st.columns(3)
    f_shipping = c13.selectbox("Shipping (per transaction)", cols, index=guess_column("shipping"))
    f_tax = c14.selectbox("Tax (per transaction)", cols, index=guess_column("tax"))
    f_fees = c15.selectbox("Fees (per transaction)", cols, index=guess_column("fees"))

    c16, c17, c18 = st.columns(3)
    f_purchase_grade_company = c16.selectbox("Purchase Grade Company", cols, index=guess_column("grade company"))
    f_purchase_grade_text = c17.selectbox("Purchase Grade Text", cols, index=guess_column("grade text"))
    f_purchase_numeric = c18.selectbox("Purchase Numeric Grade", cols, index=guess_column("numeric grade"))

    c19, c20, c21 = st.columns(3)
    f_est_grade_text = c19.selectbox("Estimated Grade Text", cols, index=guess_column("estimated grade"))
    f_est_numeric = c20.selectbox("Estimated Numeric Grade", cols, index=guess_column("estimated numeric"))
    f_valuation = c21.selectbox("Valuation Method (AUTO/MELT_ONLY/GUIDE_ONLY/MANUAL)", cols, index=guess_column("valuation"))

    c22, c23 = st.columns(2)
    f_manual_value = c22.selectbox("Manual Unit Value (if MANUAL)", cols, index=guess_column("manual"))
    f_storage_name = c23.selectbox("Storage Location Name", cols, index=guess_column("storage"))

    st.markdown("### Defaults & grouping")
    d_currency = st.text_input("Default currency if blank", "USD")
    storage_opts = list_storage_locations()
    names = {"— none —": None}
    names.update({s['name']: s['id'] for s in storage_opts})
    default_storage = st.selectbox("Default Storage (if blank)", list(names.keys()))

    group_mode = st.selectbox(
        "Group rows into transactions by",
        ["Auto: (tx_date, tx_type, party)", "Each row is its own transaction", "Custom: use a column"],
        index=0,
    )
    f_group_col = None
    if group_mode == "Custom: use a column":
        f_group_col = st.selectbox("Select group column (rows with same value form one transaction)", cols)

    dry_run = st.checkbox("Dry run (validate only—don’t write)", value=True)

    st.markdown("---")
    if st.button("Validate & Import"):
        # Helper to fetch a value or default None
        def val(row, field):
            if field and field != "— none —":
                return row[field]
            return None

        # Normalize tx groups
        df2 = df.copy()
        # Basic sanity
        required = [f_tx_date, f_tx_type, f_quantity, f_unit_price]
        missing = [x for x in required if x == "— none —"]
        if missing:
            st.error("Please map all required fields.")
            st.stop()

        # Clean types
        def norm_tx_type(x):
            if pd.isna(x):
                return None
            s = str(x).strip().upper()
            return 'BUY' if s.startswith('B') else ('SELL' if s.startswith('S') else s)

        df2["__tx_date"] = pd.to_datetime(df2[f_tx_date], errors='coerce').dt.date
        df2["__tx_type"] = df2[f_tx_type].apply(norm_tx_type)
        df2["__qty"] = pd.to_numeric(df2[f_quantity], errors='coerce').fillna(0).astype(int)
        df2["__unit_price"] = pd.to_numeric(df2[f_unit_price], errors='coerce')

        if df2["__tx_date"].isna().any() or df2["__tx_type"].isna().any():
            st.error("Some rows have invalid dates or tx types. Fix the source or map correctly.")
            st.stop()

        # Determine grouping key
        if group_mode.startswith("Auto"):
            party_series = df2[f_party] if f_party != "— none —" else ""
            df2["__group"] = df2["__tx_date"].astype(str) + "|" + df2["__tx_type"].astype(str) + "|" + party_series.astype(str)
        elif group_mode.startswith("Each row"):
            df2["__group"] = df2.index.astype(str)
        else:
            if f_group_col == "— none —":
                st.error("Choose a group column or change grouping mode.")
                st.stop()
            df2["__group"] = df2[f_group_col].astype(str)

        # Aggregators for fees
        if f_shipping != "— none —":
            df2["__ship"] = pd.to_numeric(df2[f_shipping], errors='coerce').fillna(0.0)
        else:
            df2["__ship"] = 0.0
        if f_tax != "— none —":
            df2["__tax"] = pd.to_numeric(df2[f_tax], errors='coerce').fillna(0.0)
        else:
            df2["__tax"] = 0.0
        if f_fees != "— none —":
            df2["__fees"] = pd.to_numeric(df2[f_fees], errors='coerce').fillna(0.0)
        else:
            df2["__fees"] = 0.0

        problems = []
        created_tx = 0
        created_lines = 0

        # Iterate groups
        for gval, gdf in df2.groupby("__group"):
            tx_type = gdf["__tx_type"].iloc[0]
            tx_date_val = gdf["__tx_date"].iloc[0].isoformat()
            party_name = None if f_party == "— none —" else str(gdf[f_party].iloc[0]) if pd.notna(gdf[f_party].iloc[0]) else None
            currency = None if f_currency == "— none —" else str(gdf[f_currency].iloc[0]) if pd.notna(gdf[f_currency].iloc[0]) else d_currency

            ship = float(gdf["__ship"].sum())
            tax = float(gdf["__tax"].sum())
            fees = float(gdf["__fees"].sum())
            notes = None

            items = []
            for _, row in gdf.iterrows():
                # Resolve coin_type_id or create from catalog fields
                coin_type_id = None
                if f_coin_type_id != "— none —" and pd.notna(row[f_coin_type_id]):
                    try:
                        coin_type_id = int(row[f_coin_type_id])
                    except Exception:
                        problems.append(f"Bad coin_type_id '{row[f_coin_type_id]}'")
                        continue
                else:
                    # Need catalog
                    country = val(row, f_country) or "USA"
                    denom = val(row, f_denom) or "Unknown"
                    series = val(row, f_series) or "Unknown Series"
                    year = val(row, f_year)
                    try:
                        year = int(year)
                    except Exception:
                        problems.append(f"Invalid year for row: {year}")
                        continue
                    mint = str(val(row, f_mint) or '').strip()
                    variety = str(val(row, f_variety) or '').strip()
                    master_id = upsert_coin_master(str(country), str(denom), str(series))
                    coin_type_id = upsert_coin_type(master_id, year, mint, variety)

                quantity = int(row["__qty"]) if pd.notna(row["__qty"]) else 0
                unit_price = float(row["__unit_price"]) if pd.notna(row["__unit_price"]) else 0.0

                # Grades & valuation
                def as_float(v):
                    try:
                        return float(v) if v is not None and str(v) != '' else None
                    except Exception:
                        return None

                purchase_grade_company = val(row, f_purchase_grade_company)
                purchase_grade_text = val(row, f_purchase_grade_text)
                purchase_numeric = as_float(val(row, f_purchase_numeric))
                est_grade_text = val(row, f_est_grade_text)
                est_numeric = as_float(val(row, f_est_numeric))
                valuation = str(val(row, f_valuation) or 'AUTO').upper()
                if valuation not in ('AUTO','MELT_ONLY','GUIDE_ONLY','MANUAL'):
                    valuation = 'AUTO'
                manual_val = as_float(val(row, f_manual_value))

                # Storage
                storage_name = val(row, f_storage_name)
                if storage_name and str(storage_name).strip():
                    storage_id = upsert_storage(str(storage_name).strip())
                else:
                    storage_id = names.get(default_storage)

                items.append({
                    "coin_type_id": coin_type_id,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "purchase_grade_company": purchase_grade_company,
                    "purchase_grade_text": purchase_grade_text,
                    "purchase_numeric_grade": purchase_numeric,
                    "slab_cert": None,
                    "estimated_grade_text": est_grade_text,
                    "estimated_numeric_grade": est_numeric,
                    "valuation_method": valuation,
                    "manual_est_unit_value": manual_val,
                    "storage_location_id": storage_id,
                    "lot_notes": val(row, f_notes),
                })

            if dry_run:
                created_tx += 1
                created_lines += len(items)
                continue

            try:
                if tx_type == 'BUY':
                    create_buy_transaction(tx_date_val, party_name, currency, ship, tax, fees, notes, items)
                elif tx_type == 'SELL':
                    sell_items = [{"coin_type_id": it["coin_type_id"], "quantity": it["quantity"], "unit_price": it["unit_price"]} for it in items]
                    create_sell_transaction(tx_date_val, party_name, currency, ship, tax, fees, notes, sell_items, method='FIFO')
                else:
                    problems.append(f"Unknown tx_type '{tx_type}' for group {gval}")
                    continue
                created_tx += 1
                created_lines += len(items)
            except Exception as e:
                problems.append(f"Group {gval}: {e}")

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
    st.info("Upload an Excel (.xlsx) or CSV file to begin.")
