# pages/9_Data_Import.py
import streamlit as st
import pandas as pd
from typing import Optional
from queries import (
    upsert_coin_master, upsert_coin_type, upsert_storage,
    create_buy_transaction, create_sell_transaction,
)
from db import get_conn
from constants import ASSET_CATEGORIES

st.header("📥 Data Import")
tabs = st.tabs(["Quick Templates", "Flexible Import (Column Mapper)", "Catalog Import (Masters & Types)"])

# -------------------------------
# Shared helpers
# -------------------------------
_BAD_EMPTY = {"", "-", "—", "None", "none", "null", "nan", "NaN"}

def _norm_text(v):
    if v is None:
        return None
    s = str(v).strip()
    return None if s in _BAD_EMPTY else s

def _norm_asset_category(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip().upper()
    return s if s in ASSET_CATEGORIES else None

def _read_any(uploaded_file) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    if name.endswith(".xlsx") or name.endswith(".xls"):
        try:
            return pd.read_excel(uploaded_file)
        except Exception as e:
            st.error(f"Unable to read Excel: {e}. Ensure 'openpyxl' is installed.")
            st.stop()
    return pd.read_csv(uploaded_file)

def _fnum(v):
    """Convert to float, defaulting to 0.0 for Turso compatibility"""
    if v is None or v == "" or str(v).strip().lower() in {"nan", "none", "null", "-", "—"}:
        return 0.0
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0

def _fint(v):
    """Convert to int, defaulting to 0 for Turso compatibility"""
    if v is None or v == "" or str(v).strip().lower() in {"nan", "none", "null", "-", "—"}:
        return 0
    try:
        return int(float(v))  # Handle "1.0" -> 1
    except (ValueError, TypeError):
        return 0

# -------------------------------
# Core import routine for transactions (used by tabs 0 & 1)
# -------------------------------
def _import_transactions(df: pd.DataFrame, dry_run: bool):
    problems = []
    created_tx = 0
    created_lines = 0

    # Group-level numeric cleanups
    for col in ['shipping', 'tax', 'fees']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)  # Add fillna(0.0)
        else:
            df[col] = 0.0

    grp_cols = ['tx_date','tx_type','party']
    for (tx_date, tx_type, party), part in df.groupby(grp_cols, dropna=False):
        # Normalize header fields
        try:
            tx_date_iso = tx_date.isoformat() if hasattr(tx_date, 'isoformat') else str(pd.to_datetime(tx_date).date())
        except Exception:
            problems.append(f"Invalid tx_date: {tx_date}")
            continue

        tx_type_u = str(tx_type).strip().upper()
        if tx_type_u not in ("BUY","SELL"):
            problems.append(f"Invalid tx_type: {tx_type}")
            continue

        # Pull first non-null currency or default USD
        if 'currency' in part.columns and not part['currency'].dropna().empty:
            currency = str(part['currency'].dropna().astype(str).str.strip().iloc[0] or "USD")
        else:
            currency = "USD"

        ship = float(part['shipping'].sum())
        tax  = float(part['tax'].sum())
        fees = float(part['fees'].sum())
        notes = None  # row-level notes go to lot

        items = []
        for _, row in part.iterrows():
            # Master + optional category
            master_id = upsert_coin_master(str(row['country']), str(row['denomination']), str(row['series']))
            cat = _norm_asset_category(row.get('asset_category')) if 'asset_category' in row else None
            if cat:
                try:
                    with get_conn() as cx:
                        cx.execute("UPDATE coin_master SET asset_category=? WHERE id=?", (cat, master_id))
                except Exception as e:
                    problems.append(f"Could not set asset_category for {row.get('series')}: {e}")

            # Type
            try:
                year = int(row['year'])
            except Exception:
                problems.append(f"Invalid year: {row.get('year')}")
                continue
            mint_mark = (_norm_text(row.get('mint_mark')) or "")
            variety   = (_norm_text(row.get('variety')) or "")
            coin_type_id = upsert_coin_type(master_id, year, mint_mark, variety)

            # Valuation + storage
            valuation = str(row.get('valuation_method') or 'AUTO').upper()
            if valuation not in ('AUTO','MELT_ONLY','GUIDE_ONLY','MANUAL'):
                valuation = 'AUTO'
            storage_name = _norm_text(row.get('storage_location'))
            storage_id = upsert_storage(storage_name) if storage_name else None

            items.append({
                'coin_type_id': coin_type_id,
                'quantity': _fint(row.get('quantity')),  # Use _fint instead of int()
                'unit_price': _fnum(row.get('unit_price')),  # Use _fnum instead of float()
                'purchase_grade_company': _norm_text(row.get('purchase_grade_company')),
                'purchase_grade_text': _norm_text(row.get('purchase_grade_text')),
                'purchase_numeric_grade': _fnum(row.get('purchase_numeric_grade')),
                'slab_cert': _norm_text(row.get('slab_cert')),
                'estimated_grade_text': _norm_text(row.get('estimated_grade_text')),
                'estimated_numeric_grade': _fnum(row.get('estimated_numeric_grade')),
                'valuation_method': valuation,
                'manual_est_unit_value': _fnum(row.get('manual_est_unit_value')),
                'storage_location_id': storage_id,
                'lot_notes': _norm_text(row.get('notes'))
            })

        if dry_run:
            created_tx += 1
            created_lines += len(items)
            continue

        try:
            if tx_type_u == "BUY":
                create_buy_transaction(tx_date_iso, party, currency, ship, tax, fees, notes, items)
            else:
                sell_items = [{"coin_type_id": it["coin_type_id"], "quantity": it["quantity"], "unit_price": it["unit_price"]} for it in items]
                create_sell_transaction(tx_date_iso, party, currency, ship, tax, fees, notes, sell_items, method='FIFO')
            created_tx += 1
            created_lines += len(items)
        except Exception as e:
            problems.append(str(e))

    if dry_run:
        st.success(f"Dry run OK. Would create ~{created_tx} transactions and {created_lines} line items.")
    else:
        if problems:
            st.warning("Import finished with some issues:")
            for p in problems[:75]:
                st.write("• ", p)
            if len(problems) > 75:
                st.caption(f"...and {len(problems)-75} more")
        st.success(f"Imported {created_tx} transactions and {created_lines} line items.")

# -------------------------------
# Tab 1 — Quick Templates (transactions)
# -------------------------------
with tabs[0]:
    st.subheader("⚡ Quick Templates (Transactions)")
    st.caption("Upload the exact **coin_lines_template.csv** or **.xlsx** (headers must match). Also supports optional **asset_category** for the coin master.")
    uploaded = st.file_uploader("Upload template file", type=["csv","xlsx","xls"], key="qi_file")

    TEMPLATE_REQUIRED = [
        'tx_date','tx_type','country','denomination','series','year','mint_mark','variety','quantity','unit_price'
    ]
    OPTIONAL = [
        'party','currency','shipping','tax','fees','notes',
        'purchase_grade_company','purchase_grade_text','purchase_numeric_grade',
        'estimated_grade_text','estimated_numeric_grade','valuation_method','manual_est_unit_value','storage_location',
        'slab_cert','asset_category'
    ]

    if uploaded is not None:
        df = _read_any(uploaded)
        st.write("**Preview**")
        st.dataframe(df.head(20), use_container_width=True)

        missing = [c for c in TEMPLATE_REQUIRED if c not in df.columns]
        if missing:
            st.error("Missing required columns in your file: " + ", ".join(missing))
            st.stop()

        # Ensure optional columns exist
        for c in OPTIONAL:
            if c not in df.columns:
                df[c] = None

        # Normalize core fields
        df['tx_date'] = pd.to_datetime(df['tx_date'], errors='coerce').dt.date
        df['tx_type'] = df['tx_type'].astype(str).str.strip().str.upper()
        df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0).astype(int)
        df['unit_price'] = pd.to_numeric(df['unit_price'], errors='coerce').fillna(0.0)

        # Normalize asset_category
        if 'asset_category' in df.columns:
            df['asset_category'] = df['asset_category'].apply(_norm_asset_category)

        # Validate
        if df['tx_date'].isna().any():
            st.error("Some rows have invalid tx_date.")
            st.stop()
        if (~df['tx_type'].isin(['BUY','SELL'])).any():
            st.error("Some rows have invalid tx_type (must be BUY/SELL).")
            st.stop()

        dry_run = st.checkbox("Dry run (validate only—don’t write)", value=True, key="qi_dryrun")
        if st.button("Validate & Import from Template", type="primary", key="qi_run"):
            _import_transactions(df, dry_run)

    with st.expander("Template Columns", expanded=False):
        st.markdown("""
        **Required**: `tx_date`, `tx_type`, `country`, `denomination`, `series`, `year`, `mint_mark`, `variety`, `quantity`, `unit_price`  
        **Optional**: `party`, `currency`, `shipping`, `tax`, `fees`, `notes`, `purchase_grade_company`, `purchase_grade_text`, `purchase_numeric_grade`, `estimated_grade_text`, `estimated_numeric_grade`, `valuation_method`, `manual_est_unit_value`, `storage_location`, `slab_cert`, `asset_category`  
        **asset_category** values: **COIN**, **ROUND**, **BAR**
        """)

# -------------------------------
# Tab 2 — Flexible Import (Column Mapper) — transactions
# -------------------------------
with tabs[1]:
    st.subheader("🧭 Flexible Import (Column Mapper)")
    st.caption("Upload any CSV/XLSX and map its columns to CoinApp **transaction** fields (BUY/SELL). Supports **asset_category** mapping (COIN/ROUND/BAR).")
    uploaded2 = st.file_uploader("Upload CSV/XLSX to map", type=["csv","xlsx","xls"], key="map_file")

    if uploaded2 is not None:
        src_df = _read_any(uploaded2)
        st.write("**Preview**")
        st.dataframe(src_df.head(20), use_container_width=True)

        src_cols = ["(none)"] + list(src_df.columns)

        required_targets = [
            'tx_date','tx_type','country','denomination','series','year','mint_mark','variety','quantity','unit_price'
        ]
        optional_targets = [
            'party','currency','shipping','tax','fees','notes',
            'purchase_grade_company','purchase_grade_text','purchase_numeric_grade',
            'estimated_grade_text','estimated_numeric_grade','valuation_method','manual_est_unit_value','storage_location',
            'slab_cert','asset_category'
        ]

        st.markdown("### Map Columns")
        maps = {}
        cols = st.columns(2)
        for i, tgt in enumerate(required_targets):
            maps[tgt] = cols[i % 2].selectbox(f"Required → {tgt}", src_cols, key=f"map_req_{tgt}")

        cols2 = st.columns(3)
        for i, tgt in enumerate(optional_targets):
            maps[tgt] = cols2[i % 3].selectbox(f"Optional → {tgt}", src_cols, index=0, key=f"map_opt_{tgt}")

        missing_req = [t for t in required_targets if maps.get(t) in (None, "(none)")]
        if missing_req:
            st.error("Please map all required fields: " + ", ".join(missing_req))
        else:
            dry_run2 = st.checkbox("Dry run (validate only—don’t write)", value=True, key="map_dryrun")
            if st.button("Validate & Import Mapped File", type="primary", key="map_run"):
                # Build normalized dataframe
                df = pd.DataFrame()
                for tgt in required_targets + optional_targets:
                    src = maps.get(tgt)
                    if not src or src == "(none)":
                        df[tgt] = None
                    else:
                        df[tgt] = src_df[src]

                # Core normalization
                df['tx_date'] = pd.to_datetime(df['tx_date'], errors='coerce').dt.date
                df['tx_type'] = df['tx_type'].astype(str).str.strip().str.upper()
                df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0).astype(int)
                df['unit_price'] = pd.to_numeric(df['unit_price'], errors='coerce').fillna(0.0)

                for c in ['shipping','tax','fees','purchase_numeric_grade','estimated_numeric_grade','manual_est_unit_value']:
                    if c in df.columns:
                        df[c] = pd.to_numeric(df[c], errors='coerce')

                for c in ['country','denomination','series','mint_mark','variety','party','currency','notes','purchase_grade_company','purchase_grade_text','estimated_grade_text','storage_location','slab_cert','valuation_method']:
                    if c in df.columns:
                        df[c] = df[c].astype(str)

                if 'asset_category' in df.columns:
                    df['asset_category'] = df['asset_category'].apply(_norm_asset_category)

                if df['tx_date'].isna().any():
                    st.error("Some rows have invalid tx_date.")
                    st.stop()
                if (~df['tx_type'].isin(['BUY','SELL'])).any():
                    st.error("Some rows have invalid tx_type (must be BUY/SELL).")
                    st.stop()

                _import_transactions(df, dry_run2)

    with st.expander("Target Fields Reference", expanded=False):
        st.markdown("""
        **Required**: `tx_date`, `tx_type`, `country`, `denomination`, `series`, `year`, `mint_mark`, `variety`, `quantity`, `unit_price`  
        **Optional**: `party`, `currency`, `shipping`, `tax`, `fees`, `notes`, `purchase_grade_company`, `purchase_grade_text`,
        `purchase_numeric_grade`, `estimated_grade_text`, `estimated_numeric_grade`, `valuation_method`, `manual_est_unit_value`,
        `storage_location`, `slab_cert`, `asset_category`
        """)

# -------------------------------
# Tab 3 — Catalog Import (Masters & Types)
# -------------------------------
with tabs[2]:
    st.subheader("📚 Catalog Import (Coin Masters & Coin Types)")
    st.caption("Add or update **catalog** without recording transactions. Useful when seeding your collection definitions.")
    st.markdown("- Download CSV templates: "
                "[coin_master_template.csv](sandbox:/mnt/data/templates/coin_master_template.csv) • "
                "[coin_type_template.csv](sandbox:/mnt/data/templates/coin_type_template.csv)")

    st.markdown("### Import Coin Masters")
    cm_file = st.file_uploader("Upload coin_master CSV/XLSX", type=["csv","xlsx","xls"], key="cm_up")
    cm_update = st.checkbox("Update fields if master already exists (by Country+Denomination+Series)", value=True, key="cm_upd_ck")
    if cm_file is not None:
        df = _read_any(cm_file)
        st.dataframe(df.head(20), use_container_width=True)

        required = ["country","denomination","series"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            st.error("Missing required columns: " + ", ".join(missing))
        else:
            # Optional fields
            for c in ["metal","fineness","weight_grams","diameter_mm","thickness_mm","edge","years_start","years_end","notes","asset_category"]:
                if c not in df.columns:
                    df[c] = None

            # Normalize numeric fields
            for c in ["fineness","weight_grams","diameter_mm","thickness_mm"]:
                df[c] = pd.to_numeric(df[c], errors='coerce')
            for c in ["years_start","years_end"]:
                df[c] = pd.to_numeric(df[c], errors='coerce').astype('Int64')

            # Normalize cat
            df["asset_category"] = df["asset_category"].apply(_norm_asset_category)

            dry_run_cm = st.checkbox("Dry run (don’t write)", value=True, key="cm_dry")
            if st.button("Import Masters", type="primary", key="cm_run"):
                problems = []
                created = 0
                updated = 0
                for _, r in df.iterrows():
                    mid = upsert_coin_master(
                        str(r["country"]), str(r["denomination"]), str(r["series"]),
                        _norm_text(r.get("metal")), _fnum(r.get("fineness")), _fnum(r.get("weight_grams")),
                        _fnum(r.get("diameter_mm")), _fnum(r.get("thickness_mm")), _norm_text(r.get("edge")),
                        int(r["years_start"]) if pd.notna(r["years_start"]) else None,
                        int(r["years_end"]) if pd.notna(r["years_end"]) else None,
                        _norm_text(r.get("notes")),
                        asset_category=_norm_text(r.get("asset_category")),
                        numista_url=_norm_text(r.get("numista_url"))
                    )
                    if dry_run_cm:
                        created += 1
                        continue
                    # If exists and checkbox set, push updates
                    try:
                        with get_conn() as cx:
                            if cm_update:
                                cx.execute("""
                                  UPDATE coin_master
                                  SET metal=COALESCE(?, metal),
                                      fineness=COALESCE(?, fineness),
                                      weight_grams=COALESCE(?, weight_grams),
                                      diameter_mm=COALESCE(?, diameter_mm),
                                      thickness_mm=COALESCE(?, thickness_mm),
                                      edge=COALESCE(?, edge),
                                      years_start=COALESCE(?, years_start),
                                      years_end=COALESCE(?, years_end),
                                      notes=COALESCE(?, notes)
                                  WHERE id=?
                                """, (_norm_text(r.get("metal")), _fnum(r.get("fineness")), _fnum(r.get("weight_grams")),
                                        _fnum(r.get("diameter_mm")), _fnum(r.get("thickness_mm")), _norm_text(r.get("edge")),
                                        int(r["years_start"]) if pd.notna(r["years_start"]) else None,
                                        int(r["years_end"]) if pd.notna(r["years_end"]) else None,
                                        _norm_text(r.get("notes")), mid))
                            # Always set asset_category if provided
                            cat = _norm_asset_category(r.get("asset_category"))
                            if cat:
                                cx.execute("UPDATE coin_master SET asset_category=? WHERE id=?", (cat, mid))
                        updated += 1
                    except Exception as e:
                        problems.append(str(e))
                if dry_run_cm:
                    st.success(f"Dry run OK. Would upsert ~{created} masters.")
                else:
                    if problems:
                        st.warning("Finished with issues:")
                        for p in problems[:50]:
                            st.write("• ", p)
                    st.success(f"Imported/updated {updated} masters.")

    st.markdown("---")
    st.markdown("### Import Coin Types")
    ct_file = st.file_uploader("Upload coin_type CSV/XLSX", type=["csv","xlsx","xls"], key="ct_up")
    if ct_file is not None:
        df = _read_any(ct_file)
        st.dataframe(df.head(20), use_container_width=True)

        required = ["country","denomination","series","year"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            st.error("Missing required columns: " + ", ".join(missing))
        else:
            for c in ["mint_mark","variety","mintage","is_proof","designer","obv_desc","rev_desc"]:
                if c not in df.columns:
                    df[c] = None
            # Normalize
            df["year"] = pd.to_numeric(df["year"], errors='coerce')
            df["mintage"] = pd.to_numeric(df["mintage"], errors='coerce').astype('Int64')
            # is_proof can be 0/1/yes/no/true/false
            def _to_boolish(x):
                s = str(x).strip().lower()
                if s in {"1","true","yes","y"}: return 1
                if s in {"0","false","no","n"}: return 0
                return 0
            df["is_proof"] = df["is_proof"].apply(_to_boolish)

            dry_run_ct = st.checkbox("Dry run (don’t write)", value=True, key="ct_dry")
            if st.button("Import Types", type="primary", key="ct_run"):
                problems = []
                created = 0
                for _, r in df.iterrows():
                    try:
                        mid = upsert_coin_master(str(r["country"]), str(r["denomination"]), str(r["series"]))
                        _ = upsert_coin_type(
                            mid, int(r["year"]),
                            (_norm_text(r.get("mint_mark")) or ""),
                            (_norm_text(r.get("variety")) or ""),
                            mintage=int(r["mintage"]) if pd.notna(r["mintage"]) else None,
                            is_proof=int(r["is_proof"]) if pd.notna(r["is_proof"]) else 0,
                            designer=_norm_text(r.get("designer")),
                            obv_desc=_norm_text(r.get("obv_desc")),
                            rev_desc=_norm_text(r.get("rev_desc"))
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
