# pages/50_Data_Import.py
import streamlit as st
import pandas as pd
from import_helpers import (
    TransactionImporter,
    read_uploaded_file,
    normalize_text,
    normalize_asset_category,
    safe_float,
    safe_int
)
from queries import upsert_coin_master, upsert_coin_type
from db import get_conn

st.header("📥 Data Import")
tabs = st.tabs(
    ["Quick Templates", "Flexible Import (Column Mapper)", "Catalog Import (Masters & Types)"])

# ---------------------------------
# Tab 1: Quick Templates
# ---------------------------------
with tabs[0]:
    st.subheader("⚡ Quick Templates (Transactions)")
    st.caption("Upload the exact **coin_lines_template.csv** or **.xlsx** (headers must match).")

    uploaded = st.file_uploader("Upload template file", type=["csv", "xlsx", "xls"], key="qi_file")

    if uploaded is not None:
        df = read_uploaded_file(uploaded)

        st.write("**Preview**")
        st.dataframe(df.head(20), width='stretch')

        importer = TransactionImporter(df)

        if importer.validate_columns():
            dry_run = st.checkbox("Dry run (validate only—don't write)", value=True,
                                  key="qi_dryrun")

            if st.button("Validate & Import from Template", type="primary", key="qi_run"):
                importer.import_transactions(dry_run)

    with st.expander("Template Columns", expanded=False):
        st.markdown("""
        **Required**: `tx_date`, `tx_type`, `country`, `denomination`, `series`, `year`, `mint_mark`, `variety`, `quantity`, `unit_price`  
        **Optional**: `party`, `currency`, `shipping`, `tax`, `fees`, `notes`, `purchase_grade_company`, `purchase_grade_text`, 
        `purchase_numeric_grade`, `estimated_grade_text`, `estimated_numeric_grade`, `valuation_method`, 
        `manual_est_unit_value`, `storage_location`, `slab_cert`, `asset_category`  
        **asset_category** values: **COIN**, **ROUND**, **BAR**, **BULLION COIN**
        """)

# ---------------------------------
# Tab 2: Flexible Import
# ---------------------------------
with tabs[1]:
    st.subheader("🧭 Flexible Import (Column Mapper)")
    st.caption("Upload any CSV/XLSX and map its columns to CoinApp **transaction** fields.")

    uploaded2 = st.file_uploader("Upload CSV/XLSX to map", type=["csv", "xlsx", "xls"],
                                 key="map_file")

    if uploaded2 is not None:
        src_df = read_uploaded_file(uploaded2)

        st.write("**Preview**")
        st.dataframe(src_df.head(20), width='stretch')

        src_cols = ["(none)"] + list(src_df.columns)

        st.markdown("### Map Columns")
        maps = {}

        # Required fields
        cols = st.columns(2)
        for i, tgt in enumerate(TransactionImporter.REQUIRED_COLUMNS):
            maps[tgt] = cols[i % 2].selectbox(f"Required → {tgt}", src_cols, key=f"map_req_{tgt}")

        # Optional fields
        cols2 = st.columns(3)
        for i, tgt in enumerate(TransactionImporter.OPTIONAL_COLUMNS):
            maps[tgt] = cols2[i % 3].selectbox(f"Optional → {tgt}", src_cols, index=0,
                                               key=f"map_opt_{tgt}")

        # Check for missing required mappings
        missing_req = [t for t in TransactionImporter.REQUIRED_COLUMNS if
                       maps.get(t) in (None, "(none)")]

        if missing_req:
            st.error("Please map all required fields: " + ", ".join(missing_req))
        else:
            dry_run2 = st.checkbox("Dry run (validate only—don't write)", value=True,
                                   key="map_dryrun")

            if st.button("Validate & Import Mapped File", type="primary", key="map_run"):
                # Build mapped dataframe
                mapped_df = pd.DataFrame()
                for tgt in TransactionImporter.REQUIRED_COLUMNS + TransactionImporter.OPTIONAL_COLUMNS:
                    src = maps.get(tgt)
                    if not src or src == "(none)":
                        mapped_df[tgt] = None
                    else:
                        mapped_df[tgt] = src_df[src]

                # Import using the mapped dataframe
                importer = TransactionImporter(mapped_df)
                importer.import_transactions(dry_run2)

# ---------------------------------
# Tab 3: Catalog Import
# ---------------------------------
with tabs[2]:
    st.subheader("📚 Catalog Import (Coin Masters & Coin Types)")
    st.caption("Add or update **catalog** without recording transactions.")

    # Coin Masters Import
    st.markdown("### Import Coin Masters")
    cm_file = st.file_uploader("Upload coin_master CSV/XLSX", type=["csv", "xlsx", "xls"],
                               key="cm_up")
    cm_update = st.checkbox("Update fields if master already exists", value=True, key="cm_upd_ck")

    if cm_file is not None:
        df = read_uploaded_file(cm_file)
        st.dataframe(df.head(20), width='stretch')

        required = ["country", "denomination", "series"]
        missing = [c for c in required if c not in df.columns]

        if missing:
            st.error("Missing required columns: " + ", ".join(missing))
        else:
            # Add missing optional columns including URLs
            optional_cols = [
                "metal", "fineness", "weight_grams", "diameter_mm", "thickness_mm",
                "edge", "years_start", "years_end", "notes", "asset_category",
                "numista_url", "ngc_url", "pcgs_url"
            ]
            for c in optional_cols:
                if c not in df.columns:
                    df[c] = None

            # Normalize data types
            for c in ["fineness", "weight_grams", "diameter_mm", "thickness_mm"]:
                df[c] = pd.to_numeric(df[c], errors='coerce')
            for c in ["years_start", "years_end"]:
                df[c] = pd.to_numeric(df[c], errors='coerce').astype('Int64')

            df["asset_category"] = df["asset_category"].apply(normalize_asset_category)

            dry_run_cm = st.checkbox("Dry run (don't write)", value=True, key="cm_dry")

            if st.button("Import Masters", type="primary", key="cm_run"):
                problems = []
                created = 0
                updated = 0

                for _, r in df.iterrows():
                    if not dry_run_cm:
                        try:
                            mid = upsert_coin_master(
                                str(r["country"]), str(r["denomination"]), str(r["series"]),
                                normalize_text(r.get("metal")),
                                safe_float(r.get("fineness")),
                                safe_float(r.get("weight_grams")),
                                safe_float(r.get("diameter_mm")),
                                safe_float(r.get("thickness_mm")),
                                normalize_text(r.get("edge")),
                                int(r["years_start"]) if pd.notna(r["years_start"]) else None,
                                int(r["years_end"]) if pd.notna(r["years_end"]) else None,
                                normalize_text(r.get("notes")),
                                asset_category=normalize_text(r.get("asset_category")),
                                numista_url=normalize_text(r.get("numista_url")),
                                ngc_url=normalize_text(r.get("ngc_url")),
                                pcgs_url=normalize_text(r.get("pcgs_url"))
                            )
                            updated += 1
                        except Exception as e:
                            problems.append(str(e))
                    else:
                        created += 1

                if dry_run_cm:
                    st.success(f"Dry run OK. Would upsert ~{created} masters.")
                else:
                    if problems:
                        st.warning("Finished with issues:")
                        for p in problems[:50]:
                            st.write("• ", p)
                    st.success(f"Imported/updated {updated} masters.")

    st.markdown("---")

    # Coin Types Import
    st.markdown("### Import Coin Types")
    ct_file = st.file_uploader("Upload coin_type CSV/XLSX", type=["csv", "xlsx", "xls"],
                               key="ct_up")

    if ct_file is not None:
        df = read_uploaded_file(ct_file)
        st.dataframe(df.head(20), width='stretch')

        required = ["country", "denomination", "series", "year"]
        missing = [c for c in required if c not in df.columns]

        if missing:
            st.error("Missing required columns: " + ", ".join(missing))
        else:
            # Add missing optional columns
            for c in ["mint_mark", "variety", "mintage", "is_proof", "designer", "obv_desc",
                      "rev_desc"]:
                if c not in df.columns:
                    df[c] = None

            # Normalize data types
            df["year"] = pd.to_numeric(df["year"], errors='coerce')
            df["mintage"] = pd.to_numeric(df["mintage"], errors='coerce').astype('Int64')


            # Handle boolean is_proof
            def to_bool(x):
                s = str(x).strip().lower()
                if s in {"1", "true", "yes", "y"}:
                    return 1
                if s in {"0", "false", "no", "n"}:
                    return 0
                return 0


            df["is_proof"] = df["is_proof"].apply(to_bool)

            dry_run_ct = st.checkbox("Dry run (don't write)", value=True, key="ct_dry")

            if st.button("Import Types", type="primary", key="ct_run"):
                problems = []
                created = 0

                for _, r in df.iterrows():
                    try:
                        if not dry_run_ct:
                            mid = upsert_coin_master(
                                str(r["country"]),
                                str(r["denomination"]),
                                str(r["series"])
                            )
                            _ = upsert_coin_type(
                                mid, int(r["year"]),
                                normalize_text(r.get("mint_mark")) or "",
                                normalize_text(r.get("variety")) or "",
                                mintage=int(r["mintage"]) if pd.notna(r["mintage"]) else None,
                                is_proof=int(r["is_proof"]) if pd.notna(r["is_proof"]) else 0,
                                designer=normalize_text(r.get("designer")),
                                obv_desc=normalize_text(r.get("obv_desc")),
                                rev_desc=normalize_text(r.get("rev_desc"))
                            )
                        created += 1
                    except Exception as e:
                        problems.append(str(e))
                        continue

                if dry_run_ct:
                    st.success(f"Dry run OK. Would upsert ~{created} coin types.")
                else:
                    if problems:
                        st.warning("Finished with issues:")
                        for p in problems[:50]:
                            st.write("• ", p)
                    st.success(f"Imported/updated {created} coin types.")
