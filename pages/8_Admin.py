# pages/8_Admin.py
import io
import os
import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st

from db import get_conn, init_db, DB_PATH
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
# Helpers
# --------------------------
def _clean_str(val):
    if val is None:
        return None
    s = str(val).strip()
    if s.lower() in {"nan", "none", "-", "—"}:
        return ""
    return s

def _list_coin_masters():
    with get_conn() as cx:
        rows = cx.execute(
            """
            SELECT id, country, denomination, series, metal, fineness, weight_grams,
                diameter_mm, thickness_mm, edge, 
                years_start, years_end, asset_category,
                numista_url, notes
            FROM coin_master
            ORDER BY country, denomination, series
            """
        ).fetchall()
    return [dict(r) for r in rows]

def _list_coin_types_for_master(master_id: int):
    with get_conn() as cx:
        rows = cx.execute(
            """
            SELECT id, year, COALESCE(mint_mark,'') AS mint_mark, COALESCE(variety,'') AS variety,
                   mintage, is_proof, designer, obv_desc, rev_desc
            FROM coin_type
            WHERE master_id=?
            ORDER BY year, mint_mark, variety
            """, (master_id,)
        ).fetchall()
    return [dict(r) for r in rows]

def _list_recent_transactions(n=50):
    with get_conn() as cx:
        rows = cx.execute(
            """
            SELECT t.id, t.tx_date, t.tx_type, p.name AS party, t.shipping, t.tax, t.fees, t.currency
            FROM tx t
            LEFT JOIN party p ON p.id = t.party_id
            ORDER BY t.tx_date DESC, t.id DESC
            LIMIT ?
            """, (n,)
        ).fetchall()
    return [dict(r) for r in rows]

def _list_open_lots():
    with get_conn() as cx:
        rows = cx.execute(
            """
            SELECT l.id, l.acquired_date, l.qty_acquired, l.qty_remaining, l.unit_cost,
                   cm.country, cm.denomination, cm.series, ct.year, ct.mint_mark, COALESCE(ct.variety,'') AS variety
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            ORDER BY l.acquired_date DESC, l.id DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]


# =====================================================
# Coin Master Editor (with Numista URL)
# =====================================================
with tab_master:
    st.subheader("Coin Master Editor")

    masters = _list_coin_masters()
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

            # Numista URL
            numista_url = st.text_input("Numista URL (optional)", m.get("numista_url") or "",
                                        placeholder="https://en.numista.com/catalogue/...",
                                        key=f"cm_numista_{mid}")
            if numista_url:
                # Older Streamlit builds don't accept `key=` here; omit it.
                st.link_button("Open Numista", numista_url, type="secondary")

            notes = st.text_area("Notes", m.get("notes") or "", height=80, key=f"cm_notes_{mid}")

            if st.button("Save changes", type="primary", use_container_width=False, key=f"cm_save_{mid}"):
                with get_conn() as cx:
                    cx.execute(
                        """
                        UPDATE coin_master
                           SET country=?,
                               denomination=?,
                               series=?,
                               metal=?,
                               fineness=?,
                               weight_grams=?,
                               diameter_mm=?,
                               thickness_mm=?,
                               edge=?,
                               years_start=?,
                               years_end=?,
                               asset_category=?,
                               numista_url=?,
                               notes=?
                         WHERE id=?
                        """
                        ,
                        (
                            _clean_str(country), _clean_str(denomination), _clean_str(series),
                            _clean_str(metal), fineness or None, weight_grams or None,
                            diameter_mm or None, thickness_mm or None, _clean_str(edge),
                            years_start or None, years_end or None,
                            asset_category, _clean_str(numista_url), _clean_str(notes), mid,
                        )
                    )
                st.success("Saved.")
                st.rerun()

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
            new_diameter = dim1.number_input("Diameter (mm)", min_value=0.0, step=0.1, value=0.0,
                                             key="cm_add_diameter")
            new_thickness = dim2.number_input("Thickness (mm)", min_value=0.0, step=0.01, value=0.0,
                                              key="cm_add_thickness")
            new_edge = dim3.text_input("Edge", key="cm_add_edge")
            y1, y2 = st.columns(2)
            new_start = y1.number_input("Years start", min_value=0, step=1, value=0, key="cm_add_ystart")
            new_end = y2.number_input("Years end", min_value=0, step=1, value=0, key="cm_add_yend")
            new_asset_cat = st.selectbox("Asset Category", ASSET_CATEGORIES, index=0, key="cm_add_asset_cat")
            new_numista = st.text_input("Numista URL (optional)", placeholder="https://en.numista.com/catalogue/...",
                                        key="cm_add_numista")
            new_notes = st.text_area("Notes", height=80, key="cm_add_notes")

            submitted = st.form_submit_button("Create master")
            if submitted:
                if not (new_country and new_denom and new_series):
                    st.error("Country, Denomination, and Series are required.")
                else:
                    with get_conn() as cx:
                        cx.execute(
                            """
                            INSERT INTO coin_master (country, denomination, series, metal, fineness, weight_grams,
                                                     diameter_mm, thickness_mm, edge,
                                                     years_start, years_end, asset_category, numista_url, notes)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                            """,
                            (
                                _clean_str(new_country), _clean_str(new_denom),
                                _clean_str(new_series),
                                _clean_str(new_metal), float(new_fineness or 0) or None,
                                float(new_weight or 0) or None,
                                float(new_diameter or 0) or None, float(new_thickness or 0) or None,
                                _clean_str(new_edge),
                                int(new_start or 0) or None, int(new_end or 0) or None,
                                new_asset_cat, _clean_str(new_numista), _clean_str(new_notes),
                            )
                        )
                    st.success("New coin master created.")
                    st.rerun()


# =====================================================
# Coin Type Editor (create + edit)
# =====================================================
with tab_types:
    st.subheader("Coin Type Editor")

    masters = _list_coin_masters()
    if not masters:
        st.info("Add a Coin Master first.")
    else:
        # Create Type
        with st.expander("➕ Add a Coin Type", expanded=True):
            labels = [f"{m['country']} • {m['denomination']} • {m['series']}" for m in masters]
            lbl_to_id = {lab: m['id'] for lab, m in zip(labels, masters)}
            pick_m_label = st.selectbox("Master", labels, key="ct_add_master")
            master_id = lbl_to_id[pick_m_label]

            c1, c2, c3 = st.columns(3)
            year = c1.number_input("Year*", min_value=0, step=1, value=0, key="ct_add_year")
            mint_mark = c2.text_input("Mint Mark ('', P, D, S, W ...)", value="", key="ct_add_mint")
            variety = c3.text_input("Variety", value="", key="ct_add_variety")
            c4, c5 = st.columns(2)
            mintage = c4.number_input("Mintage", min_value=0, step=1, value=0, key="ct_add_mintage")
            is_proof = c5.checkbox("Is Proof?", key="ct_add_proof")

            if st.button("Create Type", type="primary", key="ct_add_submit"):
                with get_conn() as cx:
                    try:
                        st.write(
                            f"DEBUG: Attempting to create coin type with master_id={master_id}, year={year}")

                        cursor = cx.execute(
                            """
                            INSERT INTO coin_type(master_id, year, mint_mark, variety, mintage, is_proof)
                            VALUES (?,?,?,?,?,?)
                            """,
                            (master_id, int(year or 0), _clean_str(mint_mark), _clean_str(variety),
                             int(mintage or 0), 1 if is_proof else 0)
                        )

                        row_id = cursor.lastrowid
                        print(f"DEBUG: Created coin type with ID {row_id}")
                        st.write(f"DEBUG: Created coin type with ID {row_id}")

                        # Immediately verify it exists
                        verify = cx.execute("SELECT COUNT(*) FROM coin_type WHERE id = ?",
                                            (row_id,)).fetchone()
                        st.write(f"DEBUG: Verification count in coin_type table: {verify[0]}")
                        print(f"DEBUG: Verification count in coin_type table: {verify[0]}")

                        # Also check what we can query back
                        created_record = cx.execute(
                            "SELECT ct.id, cm.series FROM coin_type ct JOIN coin_master cm ON cm.id = ct.master_id WHERE ct.id = ?",
                            (row_id,)
                        ).fetchone()
                        if created_record:
                            st.write(
                                f"DEBUG: Found created record - ID: {created_record[0]}, Series: {created_record[1]}")
                        else:
                            st.write("DEBUG: Could not find the created record in joined query")

                        st.success("Coin Type created.")
                        st.rerun()

                    except sqlite3.IntegrityError as e:
                        st.error(f"Could not create coin type (maybe it already exists): {e}")
                    except Exception as e:
                        st.error(f"Database error: {e}")

            # if st.button("Create Type", type="primary", key="ct_add_submit"):
            #     with get_conn() as cx:
            #         try:
            #             cx.execute(
            #                 """
            #                 INSERT INTO coin_type(master_id, year, mint_mark, variety, mintage, is_proof)
            #                 VALUES (?,?,?,?,?,?)
            #                 """
            #                 , (master_id, int(year or 0), _clean_str(mint_mark), _clean_str(variety), int(mintage or 0), 1 if is_proof else 0)
            #             )
            #             st.success("Coin Type created.")
            #             st.rerun()
            #         except sqlite3.IntegrityError as e:
            #             st.error(f"Could not create coin type (maybe it already exists): {e}")

        st.divider()

        # Edit Type
        st.subheader("Edit Existing Type")
        type_rows = []
        with get_conn() as cx:
            type_rows = cx.execute(
                """
                SELECT ct.id, cm.country, cm.denomination, cm.series, ct.year,
                       COALESCE(ct.mint_mark,'') AS mint_mark, COALESCE(ct.variety,'') AS variety,
                       ct.mintage, ct.is_proof
                FROM coin_type ct
                JOIN coin_master cm ON cm.id = ct.master_id
                ORDER BY cm.country, cm.denomination, cm.series, ct.year, ct.mint_mark, ct.variety
                """
            ).fetchall()
        type_rows = [dict(r) for r in type_rows]
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
                with get_conn() as cx:
                    cx.execute(
                        """
                        UPDATE coin_type
                           SET year=?, mint_mark=?, variety=?, mintage=?, is_proof=?
                         WHERE id=?
                        """
                        ,
                        (int(e_year or 0), _clean_str(e_mint), _clean_str(e_var), int(e_mintage or 0), 1 if e_proof else 0, tid)
                    )
                st.success("Type updated.")
                st.rerun()


# =====================================================
# Metal Prices
# =====================================================
with tab_prices:
    st.subheader("Metal Prices")

    # Show latest prices
    with get_conn() as cx:
        rows = cx.execute(
            """
            SELECT metal, price_per_oz_usd, quoted_at_utc
            FROM metal_price
            WHERE (metal, quoted_at_utc) IN (
              SELECT metal, MAX(quoted_at_utc) FROM metal_price GROUP BY metal
            )
            ORDER BY metal
            """
        ).fetchall()
    df = pd.DataFrame([dict(r) for r in rows])
    if not df.empty:
        df = df.rename(columns={"metal": "Metal", "price_per_oz_usd": "Price Per Oz. (USD)", "quoted_at_utc": "Quoted (UTC)"})
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No prices yet. Add some below.")

    st.markdown("**Add/Update a Price**")
    c1, c2, c3 = st.columns(3)
    metal = c1.selectbox("Metal", ["Ag","Au","Pt","Pd"], index=0, key="mp_metal")
    price = c2.number_input("Price per oz (USD)", min_value=0.0, step=0.01, value=0.0, key="mp_price")
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    if st.button("Save Price", key="mp_save"):
        with get_conn() as cx:
            cx.execute(
                "INSERT INTO metal_price (metal, price_per_oz_usd, quoted_at_utc) VALUES (?,?,?)",
                (metal, float(price), now),
            )
        st.success(f"Saved {metal} = ${price:,.2f} @ {now} UTC")
        st.rerun()

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
                # Symbols you specified
                sym_map = {"Ag": "SI=F", "Au": "GC=F", "Pt": "PL=F", "Pd": "PA=F"}
                updated = []
                for m, sym in sym_map.items():
                    try:
                        t = yf.Ticker(sym)
                        data = t.history(period="1d")
                        last = float(data["Close"].iloc[-1])
                        with get_conn() as cx:
                            cx.execute(
                                "INSERT INTO metal_price (metal, price_per_oz_usd, quoted_at_utc) VALUES (?,?,?)",
                                (m, last, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")),
                            )
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
    tx_rows = _list_recent_transactions(100)
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
                with get_conn() as cx:
                    cx.execute("DELETE FROM tx WHERE id=?", (tx_id,))
                st.success(f"Transaction #{tx_id} voided.")
                st.rerun()
            except Exception as e:
                st.error(f"Could not void transaction: {e}")

    st.divider()
    st.subheader("Delete a lot (no relief)")
    lots = _list_open_lots()
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
                with get_conn() as cx:
                    used = cx.execute("SELECT COUNT(1) AS c FROM lot_relief WHERE lot_id=?", (chosen["id"],)).fetchone()["c"]
                    if used and used > 0:
                        st.error("This lot has relief (sales) linked. Cannot delete.")
                    else:
                        cx.execute("DELETE FROM lot WHERE id=?", (chosen["id"],))
                        st.success(f"Lot #{chosen['id']} deleted.")
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
                bio = io.BytesIO()
                with open(DB_PATH, "rb") as f:
                    bio.write(f.read())
                bio.seek(0)
                st.download_button(
                    label="Download backup",
                    data=bio,
                    file_name=f"coinapp-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.sqlite",
                    mime="application/octet-stream",
                    use_container_width=True,
                    key="reset_download_btn"
                )
            except Exception as e:
                st.error(f"Backup failed: {e}")
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
