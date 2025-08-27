# pages/45_Admin.py
import io
import os
from datetime import datetime, UTC

import pandas as pd
import streamlit as st

from db import init_db, create_backup_data, get_backup_filename, DB_PATH
from db_operations import execute_query_all, execute_query_single, execute_insert, execute_update, execute_delete
from queries import create_or_update_coin_master, create_or_update_coin_type
from constants import ASSET_CATEGORIES

st.set_page_config(page_title="Admin", page_icon="🛠️", layout="wide")
st.title("🛠️ Admin")

TAB_LABELS = [
    "Coin Master Editor",
    "Coin Type Editor", 
    "Metal Prices",
    "Void / Delete Tools",
    "Reset DB",
]
tab_master, tab_types, tab_prices, tab_maint, tab_reset = st.tabs(TAB_LABELS)


# --------------------------
# Helper Functions (refactored to use query functions)
# --------------------------
def clean_str(val):
    """Clean string input, handling NaN-like values."""
    if val is None:
        return None
    s = str(val).strip()
    if s.lower() in {"nan", "none", "-", "—"}:
        return ""
    return s


def get_coin_masters():
    """Get all coin masters."""
    return execute_query_all("""
        SELECT id, country, denomination, series, metal, fineness, weight_grams,
            diameter_mm, thickness_mm, edge, 
            years_start, years_end, asset_category,
            numista_url, ngc_url, pcgs_url, notes
        FROM coin_master
        ORDER BY country, denomination, series
    """)


def get_coin_types_for_master(master_id: int):
    """Get coin types for a specific master."""
    return execute_query_all("""
        SELECT id, year, COALESCE(mint_mark,'') AS mint_mark, COALESCE(variety,'') AS variety,
               mintage, is_proof, designer, obv_desc, rev_desc
        FROM coin_type
        WHERE master_id=?
        ORDER BY year, mint_mark, variety
    """, (master_id,))


def get_all_coin_types():
    """Get all coin types with master information."""
    return execute_query_all("""
        SELECT ct.id, cm.country, cm.denomination, cm.series, ct.year,
               COALESCE(ct.mint_mark,'') AS mint_mark, COALESCE(ct.variety,'') AS variety,
               ct.mintage, ct.is_proof, ct.master_id
        FROM coin_type ct
        JOIN coin_master cm ON cm.id = ct.master_id
        ORDER BY cm.country, cm.denomination, cm.series, ct.year, ct.mint_mark, ct.variety
    """)


def get_recent_transactions(limit: int = 50):
    """Get recent transactions."""
    return execute_query_all("""
        SELECT t.id, t.tx_date, t.tx_type, p.name AS party, t.shipping, t.tax, t.fees, t.currency
        FROM tx t
        LEFT JOIN party p ON p.id = t.party_id
        ORDER BY t.tx_date DESC, t.id DESC
        LIMIT ?
    """, (limit,))


def get_open_lots():
    """Get open lots."""
    return execute_query_all("""
        SELECT l.id, l.acquired_date, l.qty_acquired, l.qty_remaining, l.unit_cost,
               cm.country, cm.denomination, cm.series, ct.year, ct.mint_mark, COALESCE(ct.variety,'') AS variety
        FROM lot l
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        ORDER BY l.acquired_date DESC, l.id DESC
    """)


def get_latest_metal_prices():
    """Get latest metal prices."""
    return execute_query_all("""
        SELECT metal, price_per_oz_usd, quoted_at_utc
        FROM metal_price
        WHERE (metal, quoted_at_utc) IN (
            SELECT metal, MAX(quoted_at_utc) FROM metal_price GROUP BY metal
        )
        ORDER BY metal
    """)


def create_metal_price(metal: str, price: float, quoted_at: str) -> int:
    """Create a metal price record."""
    return execute_insert(
        "INSERT INTO metal_price (metal, price_per_oz_usd, quoted_at_utc) VALUES (?,?,?)",
        (metal, price, quoted_at)
    )


def delete_transaction(tx_id: int) -> int:
    """Delete a transaction."""
    return execute_delete("DELETE FROM tx WHERE id=?", (tx_id,))


def delete_lot(lot_id: int) -> int:
    """Delete a lot (only if no relief records exist)."""
    # Check for existing relief records
    relief_count = execute_query_single("SELECT COUNT(1) AS c FROM lot_relief WHERE lot_id=?", (lot_id,))
    if relief_count and relief_count['c'] > 0:
        raise ValueError("This lot has relief (sales) linked. Cannot delete.")
    
    return execute_delete("DELETE FROM lot WHERE id=?", (lot_id,))


# =====================================================
# Coin Master Editor
# =====================================================
with tab_master:
    st.subheader("Coin Master Editor")

    masters = get_coin_masters()
    left, right = st.columns([2, 1])

    with left:
        if not masters:
            st.info("No masters yet. Use **Add New** on the right.")
        else:
            labels = [f"{m['country']} • {m['denomination']} • {m['series']}" for m in masters]
            lbl_to_row = {lab: m for lab, m in zip(labels, masters)}
            pick = st.selectbox("Select a coin master", labels, key="cm_pick_label")
            m = lbl_to_row[pick]
            mid = m["id"]

            ca, cb, cc = st.columns(3)
            country = ca.text_input("Country", m.get("country") or "", key=f"cm_country_{mid}")
            denomination = cb.text_input("Denomination", m.get("denomination") or "", key=f"cm_denom_{mid}")
            series = cc.text_input("Series", m.get("series") or "", key=f"cm_series_{mid}")

            c1, c2, c3 = st.columns(3)
            metal = c1.text_input("Metal (Ag/Au/Pt/Pd/...)", m.get("metal") or "", key=f"cm_metal_{mid}")
            fineness = c2.number_input("Fineness (0-1)", min_value=0.0, max_value=1.0, step=0.001,
                                       value=float(m.get("fineness") or 0.0), key=f"cm_fineness_{mid}")
            weight_grams = c3.number_input("Weight (g)", min_value=0.0, step=0.001,
                                           value=float(m.get("weight_grams") or 0.0), key=f"cm_weight_{mid}")

            d1, d2, d3 = st.columns(3)
            diameter_mm = d1.number_input("Diameter (mm)", min_value=0.0, step=0.1,
                                          value=float(m.get("diameter_mm") or 0.0),
                                          key=f"cm_diameter_{mid}")
            thickness_mm = d2.number_input("Thickness (mm)", min_value=0.0, step=0.01,
                                           value=float(m.get("thickness_mm") or 0.0),
                                           key=f"cm_thickness_{mid}")
            edge = d3.text_input("Edge", m.get("edge") or "", key=f"cm_edge_{mid}")

            y1, y2 = st.columns(2)
            years_start = y1.number_input("Years start", min_value=0, step=1,
                                          value=int(m.get("years_start") or 0), key=f"cm_ystart_{mid}")
            years_end = y2.number_input("Years end", min_value=0, step=1,
                                        value=int(m.get("years_end") or 0), key=f"cm_yend_{mid}")

            asset_category = st.selectbox("Asset Category", ASSET_CATEGORIES,
                                          index=ASSET_CATEGORIES.index((m.get("asset_category") or "COIN")),
                                          key=f"cm_assetcat_{mid}")

            numista_url = st.text_input("Numista URL (optional)", m.get("numista_url") or "",
                                        placeholder="https://en.numista.com/catalogue/...",
                                        key=f"cm_numista_{mid}")
            if numista_url:
                st.link_button("Open Numista", numista_url, type="secondary")

            ngc_url = st.text_input("NGC URL (optional)", m.get("ngc_url") or "",
                                    placeholder="https://www.ngccoin.com/price-guide/...",
                                    key=f"cm_ngc_{mid}")
            if ngc_url:
                st.link_button("Open NGC", ngc_url, type="secondary")

            pcgs_url = st.text_input("PCGS URL (optional)", m.get("pcgs_url") or "",
                                     placeholder="https://www.pcgs.com/prices/...",
                                     key=f"cm_pcgs_{mid}")
            if pcgs_url:
                st.link_button("Open PCGS", pcgs_url, type="secondary")

            notes = st.text_area("Notes", m.get("notes") or "", height=80, key=f"cm_notes_{mid}")

            if st.button("Save changes", type="primary", use_container_width=False,
                         key=f"cm_save_{mid}"):
                try:
                    rows_affected = execute_update(
                        """
                        UPDATE coin_master
                        SET country=?, denomination=?, series=?, metal=?, fineness=?, 
                            weight_grams=?, diameter_mm=?, thickness_mm=?, edge=?,
                            years_start=?, years_end=?, asset_category=?, 
                            numista_url=?, ngc_url=?, pcgs_url=?, notes=?
                        WHERE id=?
                        """,
                        (
                            country, denomination, series,
                            metal if metal else None,
                            fineness,
                            weight_grams,
                            diameter_mm,
                            thickness_mm,
                            edge if edge else None,
                            years_start,
                            years_end,
                            asset_category,
                            numista_url if numista_url else None,
                            ngc_url if ngc_url else None,
                            pcgs_url if pcgs_url else None,
                            notes if notes else None,
                            mid
                        )
                    )
                    st.success(f"Saved. Rows affected: {rows_affected}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to save changes: {e}")

            st.divider()
            st.caption("All masters (read-only)")
            st.dataframe(pd.DataFrame(masters), use_container_width=True)

    with right:
        st.subheader("Add New")
        with st.form("cm_add_form"):
            ac, ad = st.columns(2)
            new_country = ac.text_input("Country*", key="cm_add_country")
            new_denom = ad.text_input("Denomination*", key="cm_add_denom")
            new_series = st.text_input("Series*", key="cm_add_series")
            row1, row2, row3 = st.columns(3)
            new_metal = row1.text_input("Metal", key="cm_add_metal")
            new_fineness = row2.number_input("Fineness", min_value=0.0, max_value=1.0, step=0.001, value=0.0, key="cm_add_fineness")
            new_weight = row3.number_input("Weight (g)", min_value=0.0, step=0.001, value=0.0, key="cm_add_weight")
            dim1, dim2, dim3 = st.columns(3)
            new_diameter = dim1.number_input("Diameter (mm)", min_value=0.0, step=0.1, value=0.0, key="cm_add_diameter")
            new_thickness = dim2.number_input("Thickness (mm)", min_value=0.0, step=0.01, value=0.0, key="cm_add_thickness")
            new_edge = dim3.text_input("Edge", key="cm_add_edge")
            y1, y2 = st.columns(2)
            new_start = y1.number_input("Years start", min_value=0, step=1, value=0, key="cm_add_ystart")
            new_end = y2.number_input("Years end", min_value=0, step=1, value=0, key="cm_add_yend")
            new_asset_cat = st.selectbox("Asset Category", ASSET_CATEGORIES, index=0, key="cm_add_asset_cat")
            new_numista = st.text_input("Numista URL (optional)", placeholder="https://en.numista.com/catalogue/...", key="cm_add_numista")
            new_ngc = st.text_input("NGC URL (optional)",
                                    placeholder="https://www.ngccoin.com/price-guide/...",
                                    key="cm_add_ngc")
            new_pcgs = st.text_input("PCGS URL (optional)",
                                     placeholder="https://www.pcgs.com/prices/...",
                                     key="cm_add_pcgs")
            new_notes = st.text_area("Notes", height=80, key="cm_add_notes")

            submitted = st.form_submit_button("Create master")
            if submitted:
                if not (new_country and new_denom and new_series):
                    st.error("Country, Denomination, and Series are required.")
                else:
                    try:
                        result_id = create_or_update_coin_master(
                            new_country, new_denom, new_series,
                            metal=new_metal if new_metal else None,
                            fineness=float(new_fineness) if new_fineness else None,
                            weight_grams=float(new_weight) if new_weight else None,
                            diameter_mm=float(new_diameter) if new_diameter else None,
                            thickness_mm=float(new_thickness) if new_thickness else None,
                            edge=new_edge if new_edge else None,
                            years_start=int(new_start) if new_start else None,
                            years_end=int(new_end) if new_end else None,
                            asset_category=new_asset_cat,
                            numista_url=new_numista if new_numista else None,
                            ngc_url=new_ngc if new_ngc else None,
                            pcgs_url=new_pcgs if new_pcgs else None,
                            notes=new_notes if new_notes else None
                        )
                        st.success(f"New coin master created with ID: {result_id}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to create coin master: {e}")


# =====================================================
# Coin Type Editor
# =====================================================
with tab_types:
    st.subheader("Coin Type Editor")

    masters = get_coin_masters()
    if not masters:
        st.info("Add a Coin Master first.")
    else:
        # Create Type
        with st.expander("➕ Add a Coin Type", expanded=True):
            with st.form("coin_type_create_form"):  # Add this form wrapper
                labels = [f"{m['country']} • {m['denomination']} • {m['series']}" for m in masters]
                lbl_to_id = {lab: m['id'] for lab, m in zip(labels, masters)}
                pick_m_label = st.selectbox("Master", labels, key="ct_add_master")
                master_id = lbl_to_id[pick_m_label]

                c1, c2, c3 = st.columns(3)
                year = c1.number_input("Year*", min_value=0, step=1, value=0, key="ct_add_year")
                mint_mark = c2.text_input("Mint Mark ('', P, D, S, W ...)", value="",
                                          key="ct_add_mint")
                variety = c3.text_input("Variety", value="", key="ct_add_variety")
                c4, c5 = st.columns(2)
                mintage = c4.number_input("Mintage", min_value=0, step=1, value=0,
                                          key="ct_add_mintage")
                is_proof = c5.checkbox("Is Proof?", key="ct_add_proof")

                # Change to form submit button
                submitted = st.form_submit_button("Create Type", type="primary")

                if submitted:  # Change from st.button to form submission
                    try:
                        result_id = create_or_update_coin_type(
                            master_id,
                            int(year or 0),
                            clean_str(mint_mark),
                            clean_str(variety),
                            mintage=int(mintage or 0),
                            is_proof=1 if is_proof else 0
                        )
                        st.success(
                            f"Coin Type created with ID: {result_id}. Refresh the page to see it in the edit list below.")
                    except Exception as e:
                        st.error(f"Failed to create coin type: {e}")

        st.subheader("Edit Existing Type")
        type_rows = get_all_coin_types()
        
        if not type_rows:
            st.info("No coin types yet.")
        else:
            options = [
                f"{r['country']} • {r['denomination']} • {r['series']} — {r['year']}{(' ' + r['mint_mark']) if r['mint_mark'] else ''}{(' • ' + r['variety']) if r['variety'] else ''}"
                for r in type_rows
            ]
            lbl_to_row = {lab: r for lab, r in zip(options, type_rows)}
            pick_t = st.selectbox("Select coin type", options, key="ct_edit_pick")
            row = lbl_to_row[pick_t]
            tid = row["id"]

            c1, c2, c3 = st.columns(3)
            e_year = c1.number_input("Year", min_value=0, step=1, value=int(row["year"] or 0), key=f"ct_year_{tid}")
            e_mint = c2.text_input("Mint Mark", value=row["mint_mark"] or "", key=f"ct_mint_{tid}")
            e_var = c3.text_input("Variety", value=row["variety"] or "", key=f"ct_var_{tid}")
            c4, c5 = st.columns(2)
            e_mintage = c4.number_input("Mintage", min_value=0, step=1, value=int(row.get("mintage") or 0), key=f"ct_mintage_{tid}")
            e_proof = c5.checkbox("Is Proof?", value=bool(row.get("is_proof")), key=f"ct_proof_{tid}")

            if st.button("Save Type Changes", key=f"ct_save_{tid}"):
                try:
                    rows_affected = execute_update(
                        """
                        UPDATE coin_type
                        SET year=?, mint_mark=?, variety=?, mintage=?, is_proof=?
                        WHERE id=?
                        """,
                        (int(e_year or 0), clean_str(e_mint), clean_str(e_var), 
                         int(e_mintage or 0), 1 if e_proof else 0, tid)
                    )
                    st.success(f"Type updated. Rows affected: {rows_affected}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to update coin type: {e}")


# =====================================================
# Metal Prices
# =====================================================
with tab_prices:
    st.subheader("Metal Prices")

    # Show latest prices
    prices = get_latest_metal_prices()
    if prices:
        df = pd.DataFrame(prices)
        df = df.rename(columns={"metal": "Metal", "price_per_oz_usd": "Price Per Oz. (USD)", "quoted_at_utc": "Quoted (UTC)"})
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No prices yet. Add some below.")

    st.markdown("**Add/Update a Price**")
    c1, c2, c3 = st.columns(3)
    metal = c1.selectbox("Metal", ["Ag","Au","Pt","Pd"], index=0, key="mp_metal")
    price = c2.number_input("Price per oz (USD)", min_value=0.0, step=0.01, value=0.0, key="mp_price")
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")

    if st.button("Save Price", key="mp_save"):
        try:
            create_metal_price(metal, float(price), now)
            st.success(f"Saved {metal} = ${price:,.2f} @ {now} UTC")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to save price: {e}")

    st.divider()
    st.markdown("**Fetch from Yahoo Finance (Futures)**")

    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("Update Ag/Au/Pt/Pd from Yahoo", key="mp_yahoo_btn"):
            try:
                import yfinance as yf
            except Exception as e:
                st.error(f"yfinance not available: {e}. Install it (requirements.txt) and redeploy.")
            else:
                sym_map = {"Ag": "SI=F", "Au": "GC=F", "Pt": "PL=F", "Pd": "PA=F"}
                updated = []
                timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
                
                for m, sym in sym_map.items():
                    try:
                        t = yf.Ticker(sym)
                        data = t.history(period="1d")
                        last = float(data["Close"].iloc[-1])
                        create_metal_price(m, last, timestamp)
                        updated.append((m, last))
                    except Exception as ex:
                        st.warning(f"{m} ({sym}) update failed: {ex}")
                
                if updated:
                    st.success("Updated: " + ", ".join([f"{m} ${v:,.2f}" for m, v in updated]))
                    st.rerun()
    with c2:
        st.caption("Uses Yahoo futures symbols: Ag=SI=F, Au=GC=F, Pt=PL=F, Pd=PA=F")


# =====================================================
# Void / Delete Tools
# =====================================================
with tab_maint:
    st.subheader("Void an entire transaction")
    tx_rows = get_recent_transactions(100)
    if not tx_rows:
        st.info("No transactions yet.")
    else:
        opts = [
            f"#{r['id']} — {r['tx_date']} — {r['tx_type']} — {r.get('party') or 'Unknown'}"
            for r in tx_rows
        ]
        lbl_to_id = {lab: r["id"] for lab, r in zip(opts, tx_rows)}
        pick = st.selectbox("Pick a transaction to void", opts, key="vd_tx_pick")
        tx_id = lbl_to_id[pick]

        if st.button("Void Transaction", type="primary", key="vd_tx_void"):
            try:
                rows_deleted = delete_transaction(tx_id)
                st.success(f"Transaction #{tx_id} voided. Rows deleted: {rows_deleted}")
                st.rerun()
            except Exception as e:
                st.error(f"Could not void transaction: {e}")

    st.divider()
    st.subheader("Delete a lot (no relief)")
    lots = get_open_lots()
    if not lots:
        st.info("No lots available.")
    else:
        labels = [
            f"Lot #{l['id']} — {l['acquired_date']} — {l['series']} {l['year']}{(' ' + l['mint_mark']) if l['mint_mark'] else ''}{(' • ' + l['variety']) if l['variety'] else ''} — Rem {l['qty_remaining']}/{l['qty_acquired']}"
            for l in lots
        ]
        lbl_to_row = {lab: l for lab, l in zip(labels, lots)}
        pick_lot = st.selectbox("Pick a lot", labels, key="vd_lot_pick")
        chosen = lbl_to_row[pick_lot]

        if st.button("Delete Lot", type="secondary", key="vd_lot_delete"):
            try:
                rows_deleted = delete_lot(chosen["id"])
                st.success(f"Lot #{chosen['id']} deleted. Rows deleted: {rows_deleted}")
                st.rerun()
            except Exception as e:
                st.error(f"Could not delete lot: {e}")


# =====================================================
# Reset DB
# =====================================================
with tab_reset:
    st.subheader("Backup & Reset Database")
    st.caption(f"DB path: {DB_PATH}")

    c1, c2 = st.columns(2)

    with c1:
        if st.button("Create Backup (.sqlite download)", key="reset_backup_btn"):
            try:
                backup_data = create_backup_data()
                st.download_button(
                    label="Download backup",
                    data=backup_data,
                    file_name=get_backup_filename(),
                    mime="application/octet-stream",
                    use_container_width=True,
                    key="reset_download_btn"
                )
            except Exception as e:
                st.error(str(e))

    with c2:
        st.warning("Reset will delete the database file and rebuild with the current schema. This cannot be undone.")
        if st.button("💥 Reset DB (drop & recreate)", type="primary", key="reset_drop_btn"):
            try:
                if os.path.exists(DB_PATH):
                    os.remove(DB_PATH)
                init_db()
                st.success("Database reset complete.")
                st.rerun()
            except Exception as e:
                st.error(f"Reset failed: {e}")
