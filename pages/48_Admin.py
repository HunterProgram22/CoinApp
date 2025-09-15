# pages/48_Admin.py
import streamlit as st
from infrastructure.auth.auth_utils import require_auth

# Check authentication first
require_auth()
import os
from datetime import datetime, UTC
import pandas as pd
import streamlit as st

from infrastructure.database.db import init_db, create_backup_data, get_backup_filename, DB_PATH
from infrastructure.database.db_operations import execute_query_all, execute_insert, execute_delete
from presentation.components.helpers.admin_helpers import (
    get_coin_masters,
    get_all_coin_types,
    update_coin_master,
    update_coin_type,
    normalize_text,
    format_master_label,
    format_type_label,
    render_weight_helper,
    WEIGHT_PRESETS
)
from core.queries import create_or_update_coin_master, create_or_update_coin_type
from core.constants import ASSET_CATEGORIES

st.set_page_config(page_title="Admin", page_icon="🛠️", layout="wide")
st.title("🛠️ Admin")

# Create tabs
tabs = st.tabs([
    "Coin Master Editor",
    "Coin Type Editor",
    "Metal Prices",
    "Maintenance Tools",
    "Database"
])

# =====================================================
# Tab 1: Coin Master Editor
# =====================================================
# =====================================================
# Tab 1: Coin Master Editor
# =====================================================
with tabs[0]:
    st.subheader("Coin Master Editor")

    # Add weight conversion helper at the top
    render_weight_helper()

    masters = get_coin_masters()

    # Add new master - expandable section at the top
    with st.expander("➕ Add a Coin Master", expanded=False):
        with st.form("add_master_form"):
            # Basic required fields
            col1, col2, col3 = st.columns(3)
            new_country = col1.text_input("Country*")
            new_denomination = col2.text_input("Denomination*")
            new_series = col3.text_input("Series*")

            # Metal specs
            col1, col2, col3 = st.columns(3)
            new_metal = col1.text_input("Metal (Ag/Au/Pt/Pd)")
            new_fineness = col2.number_input("Fineness", 0.0, 1.0, 0.999, step=0.001, format="%.4f")
            new_weight = col3.number_input("Weight (grams)", 0.0, step=0.000001, format="%.6f")

            # Weight preset helper
            weight_preset = st.selectbox("Or select weight preset",
                                         ["Custom"] + list(WEIGHT_PRESETS.keys()))
            if weight_preset != "Custom":
                st.info(f"Will use: {WEIGHT_PRESETS[weight_preset]} grams")

            # Physical dimensions
            col1, col2, col3 = st.columns(3)
            new_diameter = col1.number_input("Diameter (mm)", 0.0, step=0.1)
            new_thickness = col2.number_input("Thickness (mm)", 0.0, step=0.01)
            new_edge = col3.text_input("Edge")

            # Years and category
            col1, col2, col3 = st.columns(3)
            new_years_start = col1.number_input("Years start", 0, step=1)
            new_years_end = col2.number_input("Years end", 0, step=1)
            new_asset_category = col3.selectbox("Asset Category", ASSET_CATEGORIES)

            # Reference URLs
            new_numista = st.text_input("Numista URL (optional)")
            new_ngc = st.text_input("NGC URL (optional)")
            new_pcgs = st.text_input("PCGS URL (optional)")

            # Notes
            new_notes = st.text_area("Notes", height=80)

            if st.form_submit_button("Create Master", type="primary"):
                if not all([new_country, new_denomination, new_series]):
                    st.error("Country, Denomination, and Series are required.")
                else:
                    try:
                        # Use preset weight if selected
                        final_weight = WEIGHT_PRESETS[
                            weight_preset] if weight_preset != "Custom" else new_weight

                        result_id = create_or_update_coin_master(
                            new_country, new_denomination, new_series,
                            metal=new_metal or None,
                            fineness=new_fineness if new_fineness else None,
                            weight_grams=final_weight if final_weight else None,
                            diameter_mm=new_diameter if new_diameter else None,
                            thickness_mm=new_thickness if new_thickness else None,
                            edge=new_edge or None,
                            years_start=new_years_start or None,
                            years_end=new_years_end or None,
                            asset_category=new_asset_category,
                            numista_url=new_numista or None,
                            ngc_url=new_ngc or None,
                            pcgs_url=new_pcgs or None,
                            notes=new_notes or None
                        )
                        st.success(f"Created master with ID: {result_id}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Creation failed: {e}")

    # Edit existing master
    st.markdown("### Edit Existing Master")

    if not masters:
        st.info("No masters yet. Add one above.")
    else:
        # Master selection
        labels = [format_master_label(m) for m in masters]
        selected = st.selectbox("Select a coin master", labels, key="cm_select")
        master = masters[labels.index(selected)]
        mid = master["id"]

        # Basic info
        col1, col2, col3 = st.columns(3)
        country = col1.text_input("Country", master.get("country") or "", key=f"cm_country_{mid}")
        denomination = col2.text_input("Denomination", master.get("denomination") or "",
                                       key=f"cm_denom_{mid}")
        series = col3.text_input("Series", master.get("series") or "", key=f"cm_series_{mid}")

        # Metal specifications
        col1, col2, col3 = st.columns(3)
        metal = col1.text_input("Metal (Ag/Au/Pt/Pd)", master.get("metal") or "",
                                key=f"cm_metal_{mid}")
        fineness = col2.number_input("Fineness (0-1)", 0.0, 1.0,
                                     float(master.get("fineness") or 0.0),
                                     step=0.001, format="%.4f", key=f"cm_fineness_{mid}")
        weight_grams = col3.number_input("Weight (grams)", 0.0, step=0.000001,
                                         value=float(master.get("weight_grams") or 0.0),
                                         format="%.6f", key=f"cm_weight_{mid}")

        # Physical dimensions
        col1, col2, col3 = st.columns(3)
        diameter_mm = col1.number_input("Diameter (mm)", 0.0, step=0.1,
                                        value=float(master.get("diameter_mm") or 0.0),
                                        key=f"cm_diameter_{mid}")
        thickness_mm = col2.number_input("Thickness (mm)", 0.0, step=0.01,
                                         value=float(master.get("thickness_mm") or 0.0),
                                         key=f"cm_thickness_{mid}")
        edge = col3.text_input("Edge", master.get("edge") or "", key=f"cm_edge_{mid}")

        # Years and category
        col1, col2, col3 = st.columns(3)
        years_start = col1.number_input("Years start", 0, step=1,
                                        value=int(master.get("years_start") or 0),
                                        key=f"cm_ystart_{mid}")
        years_end = col2.number_input("Years end", 0, step=1,
                                      value=int(master.get("years_end") or 0), key=f"cm_yend_{mid}")
        asset_category = col3.selectbox("Asset Category", ASSET_CATEGORIES,
                                        index=ASSET_CATEGORIES.index(
                                            master.get("asset_category") or "COIN"),
                                        key=f"cm_assetcat_{mid}")

        # Reference URLs
        st.markdown("#### Reference URLs")
        numista_url = st.text_input("Numista URL", master.get("numista_url") or "",
                                    key=f"cm_numista_{mid}")
        ngc_url = st.text_input("NGC URL", master.get("ngc_url") or "", key=f"cm_ngc_{mid}")
        pcgs_url = st.text_input("PCGS URL", master.get("pcgs_url") or "", key=f"cm_pcgs_{mid}")

        # Link buttons
        col1, col2, col3 = st.columns(3)
        if numista_url:
            col1.link_button("Open Numista", numista_url)
        if ngc_url:
            col2.link_button("Open NGC", ngc_url)
        if pcgs_url:
            col3.link_button("Open PCGS", pcgs_url)

        # Notes
        notes = st.text_area("Notes", master.get("notes") or "", height=80, key=f"cm_notes_{mid}")

        # Save button
        if st.button("Save Changes", type="primary", key=f"cm_save_{mid}"):
            try:
                rows = update_coin_master(
                    mid,
                    country=country,
                    denomination=denomination,
                    series=series,
                    metal=metal or None,
                    fineness=fineness,
                    weight_grams=weight_grams,
                    diameter_mm=diameter_mm,
                    thickness_mm=thickness_mm,
                    edge=edge or None,
                    years_start=years_start or None,
                    years_end=years_end or None,
                    asset_category=asset_category,
                    numista_url=numista_url or None,
                    ngc_url=ngc_url or None,
                    pcgs_url=pcgs_url or None,
                    notes=notes or None
                )
                st.success(f"Updated successfully! Rows affected: {rows}")
                st.rerun()
            except Exception as e:
                st.error(f"Update failed: {e}")

# =====================================================
# Tab 2: Coin Type Editor
# =====================================================
with tabs[1]:
    st.subheader("Coin Type Editor")

    masters = get_coin_masters()
    if not masters:
        st.info("Add a Coin Master first.")
    else:
        # Add new type
        with st.expander("➕ Add a Coin Type", expanded=False):
            with st.form("add_type_form"):
                labels = [format_master_label(m) for m in masters]
                master_index = st.selectbox("Master", range(len(labels)),
                                            format_func=lambda x: labels[x])
                selected_master = masters[master_index]

                col1, col2, col3 = st.columns(3)
                year = col1.number_input("Year*", min_value=0, step=1)
                mint_mark = col2.text_input("Mint Mark")
                variety = col3.text_input("Variety")

                col1, col2 = st.columns(2)
                mintage = col1.number_input("Mintage", min_value=0, step=1)
                is_proof = col2.checkbox("Is Proof?")

                if st.form_submit_button("Create Type", type="primary"):
                    try:
                        result_id = create_or_update_coin_type(
                            selected_master['id'],
                            year,
                            normalize_text(mint_mark),
                            normalize_text(variety),
                            mintage=mintage or None,
                            is_proof=1 if is_proof else 0
                        )
                        st.success(f"Created type with ID: {result_id}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Creation failed: {e}")

        # Edit existing types
        st.markdown("### Edit Existing Type")
        types = get_all_coin_types()

        if not types:
            st.info("No coin types yet.")
        else:
            type_labels = [format_type_label(t) for t in types]
            selected_type = st.selectbox("Select coin type", type_labels)
            type_data = types[type_labels.index(selected_type)]
            tid = type_data["id"]

            col1, col2, col3 = st.columns(3)
            edit_year = col1.number_input("Year", value=type_data["year"], key=f"type_year_{tid}")
            edit_mint = col2.text_input("Mint Mark", value=type_data["mint_mark"],
                                        key=f"type_mint_{tid}")
            edit_variety = col3.text_input("Variety", value=type_data["variety"],
                                           key=f"type_variety_{tid}")

            col1, col2 = st.columns(2)
            edit_mintage = col1.number_input("Mintage", value=type_data.get("mintage", 0),
                                             key=f"type_mintage_{tid}")
            edit_proof = col2.checkbox("Is Proof?", value=bool(type_data.get("is_proof")),
                                       key=f"type_proof_{tid}")

            if st.button("Save Type Changes", key=f"save_type_{tid}"):
                try:
                    rows = update_coin_type(
                        tid,
                        year=edit_year,
                        mint_mark=edit_mint,
                        variety=edit_variety,
                        mintage=edit_mintage,
                        is_proof=edit_proof
                    )
                    st.success(f"Updated successfully! Rows affected: {rows}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Update failed: {e}")

# =====================================================
# Tab 3: Metal Prices
# =====================================================
with tabs[2]:
    from queries import get_latest_metal_prices, create_metal_price

    st.subheader("Metal Prices")

    # Display current prices
    prices = get_latest_metal_prices()
    if prices:
        df = pd.DataFrame(prices)
        df = df.rename(columns={
            "metal": "Metal",
            "price_per_oz_usd": "Price Per Oz (USD)",
            "quoted_at_utc": "Last Updated (UTC)"
        })
        st.dataframe(df, width='stretch', hide_index=True)
    else:
        st.info("No prices yet. Add some below.")

    # Manual price entry
    st.markdown("### Add/Update Price")
    col1, col2 = st.columns(2)
    metal = col1.selectbox("Metal", ["Ag", "Au", "Pt", "Pd"])
    price = col2.text_input("Price per oz (USD)", value="0.00")

    if st.button("Save Price", type="primary"):
        try:
            price_val = float(price)
            if price_val <= 0:
                st.error("Price must be greater than 0")
            else:
                now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
                create_metal_price(metal, price_val, now)
                st.success(f"Saved {metal} = ${price_val:,.2f}")
                st.rerun()
        except ValueError:
            st.error("Invalid price format")
        except Exception as e:
            st.error(f"Save failed: {e}")

    # Yahoo Finance update
    st.markdown("### Auto-Update from Yahoo Finance")
    if st.button("Fetch Current Prices from Yahoo", type="secondary"):
        try:
            import yfinance as yf

            symbols = {"Ag": "SI=F", "Au": "GC=F", "Pt": "PL=F", "Pd": "PA=F"}
            timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
            updated = []

            for metal, symbol in symbols.items():
                try:
                    ticker = yf.Ticker(symbol)
                    data = ticker.history(period="3d")
                    if not data.empty:
                        last_price = float(data["Close"].iloc[-1])
                        create_metal_price(metal, last_price, timestamp)
                        updated.append(f"{metal}: ${last_price:,.2f}")
                except Exception as e:
                    st.warning(f"Failed to update {metal}: {e}")

            if updated:
                st.success("Updated: " + ", ".join(updated))
                st.rerun()
        except ImportError:
            st.error("yfinance not installed. Add it to requirements.txt")

# =====================================================
# Tab 4: Maintenance Tools
# =====================================================
with tabs[3]:
    from queries import get_recent_transactions, get_open_lots

    st.subheader("Maintenance Tools")

    # Transaction void
    with st.expander("Void Transaction", expanded=True):
        transactions = get_recent_transactions(100)
        if not transactions:
            st.info("No transactions found.")
        else:
            tx_options = [
                f"#{t['id']} - {t['tx_date']} - {t['tx_type']} - {t.get('party', 'Unknown')}"
                for t in transactions
            ]
            selected_tx = st.selectbox("Select transaction to void", tx_options)
            tx_id = transactions[tx_options.index(selected_tx)]['id']

            if st.button("Void Transaction", type="primary"):
                try:
                    rows = execute_delete("DELETE FROM tx WHERE id=?", (tx_id,))
                    st.success(f"Transaction #{tx_id} voided. Rows deleted: {rows}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Void failed: {e}")

    # Lot deletion
    with st.expander("Delete Lot"):
        lots = get_open_lots()
        if not lots:
            st.info("No lots available.")
        else:
            lot_options = [
                f"Lot #{l['id']} - {l['series']} {l['year']} - Remaining: {l['qty_remaining']}/{l['qty_acquired']}"
                for l in lots
            ]
            selected_lot = st.selectbox("Select lot to delete", lot_options)
            lot_id = lots[lot_options.index(selected_lot)]['id']

            if st.button("Delete Lot", type="secondary"):
                try:
                    # Check for relief records
                    relief_check = execute_query_single(
                        "SELECT COUNT(*) as count FROM lot_relief WHERE lot_id=?",
                        (lot_id,)
                    )
                    if relief_check and relief_check['count'] > 0:
                        st.error("Cannot delete lot with sales history.")
                    else:
                        rows = execute_delete("DELETE FROM lot WHERE id=?", (lot_id,))
                        st.success(f"Lot #{lot_id} deleted.")
                        st.rerun()
                except Exception as e:
                    st.error(f"Delete failed: {e}")

# =====================================================
# Tab 5: Database
# =====================================================
with tabs[4]:
    st.subheader("Database Management")
    st.caption(f"Database location: `{DB_PATH}`")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Backup")
        st.write("Download a complete backup of your database.")

        if st.button("Create Backup", type="primary"):
            try:
                backup_data = create_backup_data()
                st.download_button(
                    label="📥 Download Backup",
                    data=backup_data,
                    file_name=get_backup_filename(),
                    mime="application/octet-stream",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Backup failed: {e}")

    with col2:
        st.markdown("### Reset Database")
        st.warning("⚠️ This will delete ALL data and cannot be undone!")

        confirm = st.checkbox("I understand this will delete all data")

        if st.button("🔥 Reset Database", type="primary", disabled=not confirm):
            try:
                if os.path.exists(DB_PATH):
                    os.remove(DB_PATH)
                init_db()
                st.success("Database reset complete!")
                st.rerun()
            except Exception as e:
                st.error(f"Reset failed: {e}")