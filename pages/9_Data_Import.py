
# pages/4_Data_Import.py
import streamlit as st
import pandas as pd
from queries import (
    upsert_coin_master, upsert_coin_type, upsert_storage,
    create_buy_transaction, create_sell_transaction,
)

st.header("📥 Data Import")
st.caption("Combined: **Quick Templates** and a **Flexible Column Mapper**. Always start with a dry run.")

tab_quick, tab_mapper = st.tabs(["⚡ Quick Templates", "🧭 Flexible Import (Column Mapper)"])

# -----------------------------
# Helpers
# -----------------------------
def _read_any(upload):
    name = upload.name.lower()
    if name.endswith(".xlsx"):
        try:
            return pd.read_excel(upload)
        except Exception as e:
            st.error(f"Unable to read Excel: {e}. Make sure 'openpyxl' is installed.")
            st.stop()
    return pd.read_csv(upload)

def _fnum(v):
    try:
        if v is None or str(v).strip() == "":
            return None
        return float(v)
    except Exception:
        return None

# ==========================================================
# TAB 1: QUICK TEMPLATES
# ==========================================================
with tab_quick:
    st.subheader("Quick Templates")
    st.caption("Upload **coin_lines_template.csv** or **.xlsx** with the exact headers we provided to skip mapping.")

    T_REQUIRED = ['tx_date','tx_type','country','denomination','series','year','mint_mark','variety','quantity','unit_price']
    T_OPTIONAL = [
        'party','currency','shipping','tax','fees','notes',
        'purchase_grade_company','purchase_grade_text','purchase_numeric_grade',
        'estimated_grade_text','estimated_numeric_grade','valuation_method','manual_est_unit_value',
        'storage_location'
    ]

    up_q = st.file_uploader("Upload template file", type=["csv","xlsx"], key="quick")
    if up_q is not None:
        df = _read_any(up_q)
        st.dataframe(df.head(20), use_container_width=True)

        missing = [c for c in T_REQUIRED if c not in df.columns]
        if missing:
            st.error("Missing required columns: " + ", ".join(missing))
            st.stop()

        for c in T_OPTIONAL:
            if c not in df.columns:
                df[c] = None

        # Clean
        df['tx_date'] = pd.to_datetime(df['tx_date'], errors='coerce').dt.date
        df['tx_type'] = df['tx_type'].astype(str).str.strip().str.upper()
        df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0).astype(int)
        df['unit_price'] = pd.to_numeric(df['unit_price'], errors='coerce').fillna(0.0)

        if df['tx_date'].isna().any() or (~df['tx_type'].isin(['BUY','SELL'])).any():
            st.error("Some rows have invalid dates or tx types (must be BUY/SELL). Fix and re-upload.")
            st.stop()

        dry_run = st.checkbox("Dry run (validate only — no writes)", value=True, key="quick_dry")

        if st.button("Validate & Import (Quick Template)"):
            problems = []
            created_tx = 0
            created_lines = 0

            g = df.copy()
            for col in ['shipping','tax','fees']:
                if col in g.columns:
                    g[col] = pd.to_numeric(g[col], errors='coerce').fillna(0.0)
                else:
                    g[col] = 0.0

            for (tx_date, tx_type, party), part in g.groupby(['tx_date','tx_type','party'], dropna=False):
                tx_date_iso = tx_date.isoformat() if hasattr(tx_date,"isoformat") else str(tx_date)
                currency = (part['currency'].dropna().astype(str).str.strip().replace({'':''}).iloc[0]
                            if 'currency' in part.columns and not part['currency'].dropna().empty else 'USD') or 'USD'
                ship = float(part['shipping'].sum())
                tax = float(part['tax'].sum())
                fees = float(part['fees'].sum())
                notes = None

                items = []
                for _, row in part.iterrows():
                    try:
                        year = int(row['year'])
                    except Exception:
                        problems.append(f"Invalid year: {row['year']}")
                        continue
                    master_id = upsert_coin_master(str(row['country']), str(row['denomination']), str(row['series']))
                    coin_type_id = upsert_coin_type(master_id, year, str(row.get('mint_mark') or ''), str(row.get('variety') or ''))

                    valuation = str(row.get('valuation_method') or 'AUTO').upper()
                    if valuation not in ('AUTO','MELT_ONLY','GUIDE_ONLY','MANUAL'):
                        valuation = 'AUTO'

                    storage_name = row.get('storage_location')
                    storage_id = upsert_storage(str(storage_name).strip()) if storage_name and str(storage_name).strip() else None

                    items.append({
                        'coin_type_id': coin_type_id,
                        'quantity': int(row['quantity'] or 0),
                        'unit_price': float(row['unit_price'] or 0.0),
                        'purchase_grade_company': row.get('purchase_grade_company'),
                        'purchase_grade_text': row.get('purchase_grade_text'),
                        'purchase_numeric_grade': _fnum(row.get('purchase_numeric_grade')),
                        'slab_cert': None,
                        'estimated_grade_text': row.get('estimated_grade_text'),
                        'estimated_numeric_grade': _fnum(row.get('estimated_numeric_grade')),
                        'valuation_method': valuation,
                        'manual_est_unit_value': _fnum(row.get('manual_est_unit_value')),
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
                        problems.append(f"Unknown tx_type '{tx_type}'"); continue
                    created_tx += 1; created_lines += len(items)
                except Exception as e:
                    problems.append(str(e))

            if dry_run:
                st.success(f"Dry run OK. Would create ~{created_tx} transaction(s) and {created_lines} line item(s).")
            else:
                if problems:
                    st.warning("Import finished with some issues:")
                    for p in problems[:50]: st.write("•", p)
                    if len(problems) > 50: st.caption(f"...and {len(problems)-50} more")
                st.success(f"Imported {created_tx} transaction(s) and {created_lines} line item(s).")

# ==========================================================
# TAB 2: FLEXIBLE MAPPER
# ==========================================================
with tab_mapper:
    st.subheader("Flexible Import (Column Mapper)")
    st.caption("Bring any CSV/Excel and map your columns to the required fields.")

    up_m = st.file_uploader("Upload CSV/XLSX", type=["csv","xlsx"], key="mapper")
    if up_m is not None:
        df = _read_any(up_m)
        st.dataframe(df.head(15), use_container_width=True)

        cols = ["(none)"] + list(df.columns)

        st.markdown("**Required fields**")
        col1, col2, col3 = st.columns(3)
        m_tx_date   = col1.selectbox("Date → tx_date", cols)
        m_tx_type   = col2.selectbox("Type (BUY/SELL) → tx_type", cols)
        m_country   = col3.selectbox("Country → country", cols)

        col4, col5, col6 = st.columns(3)
        m_denom     = col4.selectbox("Denomination → denomination", cols)
        m_series    = col5.selectbox("Series → series", cols)
        m_year      = col6.selectbox("Year → year", cols)

        col7, col8, col9 = st.columns(3)
        m_qty       = col7.selectbox("Quantity → quantity", cols)
        m_price     = col8.selectbox("Unit Price → unit_price", cols)
        m_mint      = col9.selectbox("Mint Mark → mint_mark", cols)

        m_variety   = st.selectbox("Variety → variety", cols)

        st.markdown("**Optional fields**")
        o1, o2, o3 = st.columns(3)
        m_party     = o1.selectbox("Party → party", cols)
        m_currency  = o2.selectbox("Currency → currency", cols)
        m_ship      = o3.selectbox("Shipping → shipping", cols)

        o4, o5, o6 = st.columns(3)
        m_tax       = o4.selectbox("Tax → tax", cols)
        m_fees      = o5.selectbox("Fees → fees", cols)
        m_notes     = o6.selectbox("Notes → notes", cols)

        g1, g2, g3 = st.columns(3)
        m_p_comp   = g1.selectbox("Purchase Grade Company → purchase_grade_company", cols)
        m_p_text   = g2.selectbox("Purchase Grade Text → purchase_grade_text", cols)
        m_p_num    = g3.selectbox("Purchase Numeric Grade → purchase_numeric_grade", cols)

        g4, g5, g6 = st.columns(3)
        m_e_text   = g4.selectbox("Estimated Grade Text → estimated_grade_text", cols)
        m_e_num    = g5.selectbox("Estimated Numeric Grade → estimated_numeric_grade", cols)
        m_val_meth = g6.selectbox("Valuation Method → valuation_method", cols)

        g7, g8 = st.columns(2)
        m_manual   = g7.selectbox("Manual Unit Value → manual_est_unit_value", cols)
        m_storage  = g8.selectbox("Storage Location → storage_location", cols)

        dry_map = st.checkbox("Dry run (validate only — no writes)", value=True, key="map_dry")

        # Validate required mappings
        req_map = [m_tx_date, m_tx_type, m_country, m_denom, m_series, m_year, m_qty, m_price]
        missing_map = [lbl for lbl in req_map if lbl == "(none)"]
        if missing_map:
            st.error("Please map all **required** fields before importing.")
        else:
            if st.button("Validate & Import (Mapper)"):
                problems = []
                created_tx = 0
                created_lines = 0

                # Build a normalized frame with unified column names
                nx = pd.DataFrame({
                    'tx_date':   pd.to_datetime(df[m_tx_date], errors='coerce').dt.date,
                    'tx_type':   df[m_tx_type].astype(str).str.strip().str.upper(),
                    'country':   df[m_country].astype(str).str.strip(),
                    'denomination': df[m_denom].astype(str).str.strip(),
                    'series':    df[m_series].astype(str).str.strip(),
                    'year':      pd.to_numeric(df[m_year], errors='coerce'),
                    'quantity':  pd.to_numeric(df[m_qty], errors='coerce'),
                    'unit_price':pd.to_numeric(df[m_price], errors='coerce'),
                    'mint_mark': (df[m_mint] if m_mint != "(none)" else ""),
                    'variety':   (df[m_variety] if m_variety != "(none)" else ""),
                })

                # Optional columns
                def optcol(m): return df[m] if m != "(none)" else None
                nx['party']             = optcol(m_party)
                nx['currency']          = optcol(m_currency)
                nx['shipping']          = pd.to_numeric(optcol(m_ship), errors='coerce') if m_ship != "(none)" else 0.0
                nx['tax']               = pd.to_numeric(optcol(m_tax), errors='coerce') if m_tax != "(none)" else 0.0
                nx['fees']              = pd.to_numeric(optcol(m_fees), errors='coerce') if m_fees != "(none)" else 0.0
                nx['notes']             = optcol(m_notes)

                nx['purchase_grade_company'] = optcol(m_p_comp)
                nx['purchase_grade_text']    = optcol(m_p_text)
                nx['purchase_numeric_grade'] = pd.to_numeric(optcol(m_p_num), errors='coerce') if m_p_num != "(none)" else None

                nx['estimated_grade_text']   = optcol(m_e_text)
                nx['estimated_numeric_grade']= pd.to_numeric(optcol(m_e_num), errors='coerce') if m_e_num != "(none)" else None
                nx['valuation_method']       = optcol(m_val_meth)
                nx['manual_est_unit_value']  = pd.to_numeric(optcol(m_manual), errors='coerce') if m_manual != "(none)" else None
                nx['storage_location']       = optcol(m_storage)

                # Basic sanity
                bad = nx['tx_date'].isna() | ~nx['tx_type'].isin(['BUY','SELL']) | nx['year'].isna() | nx['quantity'].isna() | nx['unit_price'].isna()
                if bad.any():
                    st.error("Some rows are missing required values or have invalid date/type/year/quantity/price.")
                    st.dataframe(nx[bad].head(20))
                    st.stop()

                # Sum per-tx charges by header keys
                nx['shipping'] = nx['shipping'].fillna(0.0).astype(float)
                nx['tax']      = nx['tax'].fillna(0.0).astype(float)
                nx['fees']     = nx['fees'].fillna(0.0).astype(float)

                # Group and import
                for (tx_date, tx_type, party), part in nx.groupby(['tx_date','tx_type','party'], dropna=False):
                    tx_date_iso = tx_date.isoformat() if hasattr(tx_date,"isoformat") else str(tx_date)
                    currency = str(part['currency'].dropna().iloc[0]) if 'currency' in part.columns and not part['currency'].dropna().empty else 'USD'
                    ship = float(part['shipping'].sum())
                    tax = float(part['tax'].sum())
                    fees = float(part['fees'].sum())
                    notes = None

                    items = []
                    for _, row in part.iterrows():
                        master_id = upsert_coin_master(str(row['country']), str(row['denomination']), str(row['series']))
                        coin_type_id = upsert_coin_type(master_id, int(row['year']), str(row.get('mint_mark') or ''), str(row.get('variety') or ''))

                        valuation = str(row.get('valuation_method') or 'AUTO').upper()
                        if valuation not in ('AUTO','MELT_ONLY','GUIDE_ONLY','MANUAL'):
                            valuation = 'AUTO'

                        storage_name = row.get('storage_location')
                        storage_id = upsert_storage(str(storage_name).strip()) if storage_name is not None and str(storage_name).strip() else None

                        items.append({
                            'coin_type_id': coin_type_id,
                            'quantity': int(row['quantity'] or 0),
                            'unit_price': float(row['unit_price'] or 0.0),
                            'purchase_grade_company': row.get('purchase_grade_company'),
                            'purchase_grade_text': row.get('purchase_grade_text'),
                            'purchase_numeric_grade': _fnum(row.get('purchase_numeric_grade')),
                            'slab_cert': None,
                            'estimated_grade_text': row.get('estimated_grade_text'),
                            'estimated_numeric_grade': _fnum(row.get('estimated_numeric_grade')),
                            'valuation_method': valuation,
                            'manual_est_unit_value': _fnum(row.get('manual_est_unit_value')),
                            'storage_location_id': storage_id,
                            'lot_notes': row.get('notes'),
                        })

                    if dry_map:
                        created_tx += 1; created_lines += len(items); continue

                    try:
                        if tx_type == 'BUY':
                            create_buy_transaction(tx_date_iso, party, currency, ship, tax, fees, notes, items)
                        elif tx_type == 'SELL':
                            sell_items = [{"coin_type_id": it["coin_type_id"], "quantity": it["quantity"], "unit_price": it["unit_price"]} for it in items]
                            create_sell_transaction(tx_date_iso, party, currency, ship, tax, fees, notes, sell_items, method='FIFO')
                        else:
                            problems.append(f"Unknown tx_type '{tx_type}'"); continue
                        created_tx += 1; created_lines += len(items)
                    except Exception as e:
                        problems.append(str(e))

                if dry_map:
                    st.success(f"Dry run OK. Would create ~{created_tx} transaction(s) and {created_lines} line item(s).")
                else:
                    if problems:
                        st.warning("Import finished with some issues:")
                        for p in problems[:50]: st.write("•", p)
                        if len(problems) > 50: st.caption(f"...and {len(problems)-50} more")
                    st.success(f"Imported {created_tx} transaction(s) and {created_lines} line item(s).")
