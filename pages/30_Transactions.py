# pages/30_Transactions.py
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from typing import Optional, List, Tuple, Dict, Any
from db_operations import execute_query_all, execute_query_single
from queries import (
    get_all_coin_types,
    get_storage_locations,
    create_buy_transaction,
    create_sell_transaction,
)

st.header("Transactions")


# ---------------------------------
# Data Access Functions
# ---------------------------------
def get_parties() -> List[str]:
    """Get list of unique parties from transactions."""
    query = """
        SELECT DISTINCT COALESCE(p.name, '') AS party
        FROM tx t 
        LEFT JOIN party p ON p.id = t.party_id
        WHERE COALESCE(p.name, '') <> ''
        ORDER BY party
    """
    results = execute_query_all(query)
    return [r['party'] for r in results]


def search_transactions(
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        tx_types: Optional[List[str]] = None,
        party: Optional[str] = None,
        search_text: Optional[str] = None
) -> pd.DataFrame:
    """Search transactions with filters."""
    conditions = []
    params = []

    if date_from and date_to:
        conditions.append("DATE(t.tx_date) BETWEEN DATE(?) AND DATE(?)")
        params.extend([date_from.isoformat(), date_to.isoformat()])

    if tx_types and len(tx_types) < 2:  # Only filter if not both BUY and SELL
        conditions.append("t.tx_type = ?")
        params.append(tx_types[0])

    if party:
        conditions.append("COALESCE(p.name, '') = ?")
        params.append(party)

    if search_text:
        search_pattern = f"%{search_text.strip()}%"
        conditions.append(
            "(cm.series LIKE ? OR ct.variety LIKE ? OR "
            "COALESCE(p.name, '') LIKE ? OR COALESCE(t.notes, '') LIKE ?)"
        )
        params.extend([search_pattern] * 4)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT
            t.id AS tx_id,
            t.tx_date,
            t.tx_type,
            COALESCE(p.name, '') AS party,
            cm.country,
            cm.denomination,
            cm.series,
            ct.year,
            ct.mint_mark,
            COALESCE(ct.variety, '') AS variety,
            tl.quantity,
            tl.unit_price,
            t.currency,
            t.shipping,
            t.tax,
            t.fees,
            COALESCE(t.notes, '') AS tx_notes
        FROM tx t
        JOIN tx_line tl ON tl.tx_id = t.id
        LEFT JOIN party p ON p.id = t.party_id
        LEFT JOIN coin_type ct ON ct.id = tl.coin_type_id
        LEFT JOIN coin_master cm ON cm.id = ct.master_id
        {where_clause}
        ORDER BY DATE(t.tx_date) DESC, t.id DESC, tl.id ASC
    """

    results = execute_query_all(query, tuple(params))
    return pd.DataFrame(results) if results else pd.DataFrame()


def get_spending_summary(
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
) -> pd.DataFrame:
    """Get spending summary for BUY transactions."""
    df = search_transactions(date_from, date_to, tx_types=["BUY"])

    if df.empty:
        return pd.DataFrame()

    # Calculate line totals
    df["line_total"] = (
            pd.to_numeric(df["unit_price"], errors="coerce").fillna(0.0) *
            pd.to_numeric(df["quantity"], errors="coerce").fillna(0.0)
    )

    # Add shipping, tax, fees to get true totals
    df["total_with_fees"] = (
            df["line_total"] +
            pd.to_numeric(df["shipping"], errors="coerce").fillna(0.0) +
            pd.to_numeric(df["tax"], errors="coerce").fillna(0.0) +
            pd.to_numeric(df["fees"], errors="coerce").fillna(0.0)
    )

    # Group by date and party
    df["Date"] = pd.to_datetime(df["tx_date"]).dt.date
    df["Series"] = df["series"].fillna("")

    agg = df.groupby(["Date", "party"], dropna=False).agg(
        Total_Spent_USD=("total_with_fees", "sum"),
        Items=("Series", lambda s: ", ".join(f"{n}×{k}" for k, n in s.value_counts().items())),
        Lines=("series", "count")
    ).reset_index().rename(columns={"party": "Party"})

    return agg.sort_values(["Date", "Party"], ascending=[False, True])


def get_spending_total(
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
) -> float:
    """Get total spending for a date range."""
    conditions = ["t.tx_type = 'BUY'"]
    params = []

    if date_from and date_to:
        conditions.append("DATE(t.tx_date) BETWEEN DATE(?) AND DATE(?)")
        params.extend([date_from.isoformat(), date_to.isoformat()])

    where_clause = f"WHERE {' AND '.join(conditions)}"

    query = f"""
        SELECT 
            COALESCE(SUM(ABS(tl.quantity) * COALESCE(tl.unit_price, 0)), 0) +
            COALESCE(SUM(DISTINCT t.shipping), 0) +
            COALESCE(SUM(DISTINCT t.tax), 0) +
            COALESCE(SUM(DISTINCT t.fees), 0) as total
        FROM tx t
        JOIN tx_line tl ON tl.tx_id = t.id
        {where_clause}
    """

    result = execute_query_single(query, tuple(params))
    return float(result['total']) if result and result['total'] else 0.0


def check_inventory_availability(coin_type_id: int, quantity: int) -> Tuple[bool, str, List[Dict]]:
    """Check if enough inventory is available for sale and return lot details."""
    query = """
        SELECT 
            l.id as lot_id,
            l.qty_remaining,
            l.acquired_date,
            cm.series,
            ct.year,
            ct.mint_mark,
            ct.variety
        FROM lot l
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        WHERE l.coin_type_id = ? AND l.qty_remaining > 0
        ORDER BY l.acquired_date ASC, l.id ASC
    """

    results = execute_query_all(query, (coin_type_id,))

    total_available = sum(r['qty_remaining'] for r in results)

    if total_available < quantity:
        if results:
            coin_desc = f"{results[0]['series']} {results[0]['year']}"
            if results[0]['mint_mark']:
                coin_desc += f" {results[0]['mint_mark']}"
            if results[0]['variety']:
                coin_desc += f" • {results[0]['variety']}"
        else:
            coin_desc = f"coin_type_id {coin_type_id}"

        return False, f"Insufficient inventory: Only {total_available} available for {coin_desc}, but trying to sell {quantity}", results

    return True, "", results


# ---------------------------------
# Helper Functions
# ---------------------------------
def calculate_date_range(preset: str) -> Tuple[Optional[date], Optional[date]]:
    """Calculate date range based on preset selection."""
    if preset == "All":
        return None, None

    today = date.today()
    presets = {
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
        "1y": timedelta(days=365)
    }

    if preset == "YTD":
        return date(today.year, 1, 1), today
    elif preset in presets:
        return today - presets[preset], today
    else:
        return today - timedelta(days=30), today


def format_coin_type_label(ct: Dict[str, Any]) -> str:
    """Format coin type for display."""
    mint_mark = f" {ct['mint_mark']}" if ct.get('mint_mark') else ""
    variety = f" • {ct['variety']}" if ct.get('variety') else ""
    return f"{ct['series']} {ct['year']}{mint_mark}{variety}"


def format_storage_label(storage: Dict[str, Any]) -> str:
    """Format storage location for display."""
    category = f" ({storage['category']})" if storage.get('category') else ""
    return f"{storage['name']}{category}"


def format_transaction_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Format transaction dataframe for display."""
    display_df = df.copy()

    # Rename columns
    display_df = display_df.rename(columns={
        "tx_date": "Date",
        "tx_type": "Type",
        "party": "Party",
        "country": "Country",
        "denomination": "Denomination",
        "series": "Series",
        "year": "Year",
        "mint_mark": "Mint Mark",
        "variety": "Variety",
        "quantity": "Qty",
        "unit_price": "Unit Price (USD)",
        "currency": "Currency",
        "shipping": "Shipping",
        "tax": "Tax",
        "fees": "Fees",
        "tx_notes": "Notes",
    })

    # Format money columns
    money_columns = ["Unit Price (USD)", "Shipping", "Tax", "Fees"]
    for col in money_columns:
        if col in display_df.columns:
            display_df[col] = pd.to_numeric(display_df[col], errors="coerce").fillna(0.0).map(
                lambda x: f"${x:,.2f}"
            )

    # Format year column
    if "Year" in display_df.columns:
        display_df["Year"] = pd.to_numeric(display_df["Year"], errors="coerce").map(
            lambda x: "" if pd.isna(x) else f"{int(x)}"
        )

    return display_df


def create_download_button(label: str, df: pd.DataFrame, filename: str):
    """Create CSV download button."""
    st.download_button(
        label,
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv"
    )


# ---------------------------------
# UI Components
# ---------------------------------
def render_search_filters():
    """Render the search filter controls."""
    col0, col1, col2, col3 = st.columns([2, 2, 2, 2])

    preset = col0.selectbox(
        "Quick range",
        ["30d", "7d", "90d", "YTD", "1y", "All"],
        index=0,
        key="tx_preset"
    )

    start_dt, end_dt = calculate_date_range(preset)

    if preset != "All":
        start_dt = col1.date_input("Start", value=start_dt, key="tx_rev_start")
        end_dt = col2.date_input("End", value=end_dt, key="tx_rev_end")
    else:
        start_dt = col1.date_input(
            "Start",
            value=date.today() - timedelta(days=365 * 5),
            key="tx_rev_start"
        )
        end_dt = col2.date_input("End", value=date.today(), key="tx_rev_end")

    tx_types = col3.multiselect(
        "Type",
        ["BUY", "SELL"],
        default=["BUY", "SELL"],
        key="tx_rev_kinds"
    )

    col4, col5, col6 = st.columns([2, 2, 3])

    parties = get_parties()
    party_selection = col4.selectbox(
        "Party (optional)",
        ["(any)"] + parties,
        index=0,
        key="tx_rev_party"
    )
    party = None if party_selection == "(any)" else party_selection

    search_text = col5.text_input(
        "Search text (series/variety/party/notes)",
        key="tx_rev_search"
    )

    run_search = col6.button("Run Search", type="primary", key="tx_rev_run")

    return start_dt, end_dt, tx_types, party, search_text, run_search, preset


def render_buy_form():
    """Render the buy transaction form."""
    coin_types = get_all_coin_types()
    storage_options = get_storage_locations()

    with st.form("buy_form", clear_on_submit=False):
        colA, colB, colC = st.columns(3)
        tx_date = colA.date_input("Date", value=date.today(), key="buy_date")
        party_name = colB.text_input("Counterparty (Dealer/Person)", key="buy_party")
        currency = colC.text_input("Currency", value="USD", key="buy_ccy")

        # Use text inputs for money fields to avoid Streamlit number_input issues
        shipping = colA.text_input("Shipping", value="0.00", key="buy_ship")
        tax = colB.text_input("Tax", value="0.00", key="buy_tax")
        fees = colC.text_input("Fees", value="0.00", key="buy_fees")
        notes = st.text_area("Notes", height=70, key="buy_notes")

        st.subheader("Line Item")

        if coin_types:
            selection = st.selectbox(
                "Coin Type",
                coin_types,
                format_func=format_coin_type_label,
                key="buy_ct"
            )
            coin_type_id = selection["id"] if selection else None
        else:
            st.warning("Add at least one Coin Type in Admin → Coin Types.")
            coin_type_id = None

        quantity = st.number_input("Quantity", min_value=1, step=1, value=1, key="buy_qty")
        unit_price = st.text_input("Unit Price (per coin)", value="0.00", key="buy_unit")

        with st.expander("Grades & Valuation"):
            purchase_grade_company = st.text_input("Purchase Grade Company (PCGS/NGC/RAW)",
                                                   key="buy_pgc")
            purchase_grade_text = st.text_input("Purchase Grade Text (e.g., MS64)", key="buy_pgt")
            purchase_numeric_grade = st.number_input("Purchase Numeric Grade", min_value=0.0,
                                                     step=0.5, value=0.0, key="buy_png")
            slab_cert = st.text_input("Slab Cert #", key="buy_cert")

            estimated_grade_text = st.text_input("Estimated Grade (your current opinion)",
                                                 key="buy_egt")
            estimated_numeric_grade = st.number_input("Estimated Numeric Grade", min_value=0.0,
                                                      step=0.5, value=0.0, key="buy_eng")
            valuation_method = st.selectbox("Valuation Method",
                                            ["AUTO", "MELT_ONLY", "GUIDE_ONLY", "MANUAL"], index=0,
                                            key="buy_valm")
            manual_est_unit_value = st.text_input("Manual Unit Value (used only if MANUAL)",
                                                  value="0.00", key="buy_manual")

        with st.expander("Storage"):
            storage_location_id = None
            if storage_options:
                stg = st.selectbox(
                    "Storage Location",
                    storage_options,
                    format_func=format_storage_label,
                    key="buy_storage"
                )
                storage_location_id = stg["id"] if stg else None
            else:
                st.info("No storage locations yet. Add some in Admin → Storage.")

            lot_notes = st.text_input("Lot Notes", key="buy_lot_notes")

        submitted = st.form_submit_button("Save BUY", type="primary")

        if submitted:
            # Validate numeric inputs
            try:
                shipping_val = float(shipping) if shipping else 0.0
                tax_val = float(tax) if tax else 0.0
                fees_val = float(fees) if fees else 0.0
                unit_price_val = float(unit_price) if unit_price else 0.0
                manual_val = float(manual_est_unit_value) if manual_est_unit_value else 0.0
            except ValueError:
                st.error("Please enter valid numbers for monetary fields")
                return

            if not coin_type_id:
                st.error("Please add/select a Coin Type first.")
            else:
                create_buy_transaction(
                    tx_date=tx_date.isoformat(),
                    party_name=party_name,
                    currency=currency,
                    shipping=shipping_val,
                    tax=tax_val,
                    fees=fees_val,
                    notes=notes,
                    items=[{
                        "coin_type_id": int(coin_type_id),
                        "quantity": int(quantity),
                        "unit_price": unit_price_val,
                        "purchase_grade_company": purchase_grade_company or None,
                        "purchase_grade_text": purchase_grade_text or None,
                        "purchase_numeric_grade": float(purchase_numeric_grade or 0) or None,
                        "slab_cert": slab_cert or None,
                        "estimated_grade_text": estimated_grade_text or None,
                        "estimated_numeric_grade": float(estimated_numeric_grade or 0) or None,
                        "valuation_method": valuation_method,
                        "manual_est_unit_value": manual_val or None,
                        "storage_location_id": storage_location_id,
                        "lot_notes": lot_notes or None,
                    }]
                )
                st.success("BUY saved.")
                st.rerun()


def check_inventory_availability(coin_type_id: int, quantity: int) -> Tuple[bool, str, List[Dict]]:
    """Check if enough inventory is available for sale and return lot details."""
    query = """
        SELECT 
            l.id as lot_id,
            l.qty_remaining,
            l.acquired_date,
            cm.series,
            ct.year,
            ct.mint_mark,
            ct.variety
        FROM lot l
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        WHERE l.coin_type_id = ? AND l.qty_remaining > 0
        ORDER BY l.acquired_date ASC, l.id ASC
    """

    results = execute_query_all(query, (coin_type_id,))

    total_available = sum(r['qty_remaining'] for r in results)

    if total_available < quantity:
        if results:
            coin_desc = f"{results[0]['series']} {results[0]['year']}"
            if results[0]['mint_mark']:
                coin_desc += f" {results[0]['mint_mark']}"
            if results[0]['variety']:
                coin_desc += f" • {results[0]['variety']}"
        else:
            coin_desc = f"coin_type_id {coin_type_id}"

        return False, f"Insufficient inventory: Only {total_available} available for {coin_desc}, but trying to sell {quantity}", results

    return True, "", results


def render_sell_form():
    """Render the sell transaction form."""
    coin_types = get_all_coin_types()

    with st.form("sell_form", clear_on_submit=False):
        colA, colB, colC = st.columns(3)
        tx_date = colA.date_input("Date", value=date.today(), key="sell_date")
        party_name = colB.text_input("Counterparty (Buyer)", key="sell_party")
        currency = colC.text_input("Currency", value="USD", key="sell_ccy")

        shipping = colA.text_input("Shipping", value="0.00", key="sell_ship")
        tax = colB.text_input("Tax", value="0.00", key="sell_tax")
        fees = colC.text_input("Fees", value="0.00", key="sell_fees")
        notes = st.text_area("Notes", height=70, key="sell_notes")

        st.subheader("Line Item")

        if coin_types:
            selection = st.selectbox(
                "Coin Type",
                coin_types,
                format_func=format_coin_type_label,
                key="sell_ct"
            )
            coin_type_id = selection["id"] if selection else None

            # Show available inventory for selected coin with lot breakdown
            if coin_type_id:
                has_inv, msg, lots = check_inventory_availability(coin_type_id, 0)
                if lots:
                    total = sum(lot['qty_remaining'] for lot in lots)
                    st.info(f"**Available to sell: {total}**")

                    # Show lot breakdown in expander
                    with st.expander("View lot details"):
                        for lot in lots:
                            st.write(
                                f"• Lot #{lot['lot_id']}: {lot['qty_remaining']} units (acquired {lot['acquired_date']})")
                else:
                    st.warning("No inventory available for this coin type")
        else:
            st.warning("Add at least one Coin Type in Admin → Coin Types.")
            coin_type_id = None

        quantity = st.number_input("Quantity to SELL", min_value=1, step=1, value=1, key="sell_qty")
        unit_price = st.text_input("Unit Price (per coin)", value="0.00", key="sell_unit")

        submitted = st.form_submit_button("Save SELL (FIFO)", type="primary")

        if submitted:
            # Validate numeric inputs
            try:
                shipping_val = float(shipping) if shipping else 0.0
                tax_val = float(tax) if tax else 0.0
                fees_val = float(fees) if fees else 0.0
                unit_price_val = float(unit_price) if unit_price else 0.0
            except ValueError:
                st.error("Please enter valid numbers for monetary fields")
                return

            if not coin_type_id:
                st.error("Please add/select a Coin Type first.")
                return

            # Check inventory before attempting sale with detailed lot info
            has_inventory, error_msg, lots = check_inventory_availability(coin_type_id, quantity)
            if not has_inventory:
                st.error(error_msg)
                if lots:
                    st.write("**Available lots:**")
                    for lot in lots:
                        st.write(f"• Lot #{lot['lot_id']}: {lot['qty_remaining']} units")
                return

            try:
                create_sell_transaction(
                    tx_date=tx_date.isoformat(),
                    party_name=party_name,
                    currency=currency,
                    shipping=shipping_val,
                    tax=tax_val,
                    fees=fees_val,
                    notes=notes,
                    items=[{
                        "coin_type_id": int(coin_type_id),
                        "quantity": int(quantity),
                        "unit_price": unit_price_val
                    }],
                    method='FIFO'
                )
                st.success("SELL saved (FIFO).")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Transaction failed: {str(e)}")
                # Show debug info
                st.write("Debug: Attempted to sell", quantity, "units")
                if lots:
                    st.write("Available lots were:")
                    for lot in lots:
                        st.write(f"• Lot #{lot['lot_id']}: {lot['qty_remaining']} units")


# ---------------------------------
# Main UI Tabs
# ---------------------------------
tab_review, tab_add, tab_spend = st.tabs(["Review / Search", "Add Transaction", "Spending Log"])

# ===== Review / Search Tab =====
with tab_review:
    start_dt, end_dt, tx_types, party, search_text, run_search, preset = render_search_filters()

    if run_search:
        # Handle "All" preset
        if preset == "All":
            start_dt, end_dt = None, None

        df = search_transactions(start_dt, end_dt, tx_types, party, search_text)

        if df.empty:
            st.info("No transactions matched your filters.")
        else:
            display_df = format_transaction_dataframe(df)
            st.dataframe(display_df, width='stretch', hide_index=True)
            create_download_button("Download CSV (Transactions)", df, "transactions.csv")

# ===== Add Transaction Tab =====
with tab_add:
    try:
        tx_mode = st.segmented_control(
            "Transaction Type",
            options=["BUY", "SELL"],
            default="BUY",
            key="tx_mode"
        )
    except AttributeError:
        tx_mode = st.radio(
            "Transaction Type",
            ["BUY", "SELL"],
            index=0,
            horizontal=True,
            key="tx_mode"
        )

    if tx_mode == "BUY":
        render_buy_form()
    else:
        render_sell_form()

# ===== Spending Log Tab =====
with tab_spend:
    col0, col1, col2 = st.columns([2, 2, 2])

    sp_preset = col0.selectbox(
        "Quick range",
        ["30d", "7d", "90d", "YTD", "1y", "All"],
        index=0,
        key="sp_preset"
    )

    sp_start, sp_end = calculate_date_range(sp_preset)

    if sp_preset != "All":
        sp_start = col1.date_input("Start", value=sp_start, key="sp_start")
        sp_end = col2.date_input("End", value=sp_end, key="sp_end")
    else:
        sp_start = col1.date_input(
            "Start",
            value=date.today() - timedelta(days=365),
            key="sp_start"
        )
        sp_end = col2.date_input("End", value=date.today(), key="sp_end")

    run_sp = st.button("Run Spending Log", type="primary", key="sp_run")

    if run_sp:
        # Handle "All" preset
        if sp_preset == "All":
            sp_start, sp_end = None, None

        # Display total spending card
        total_spent = get_spending_total(sp_start, sp_end)

        if sp_preset == "All":
            period_label = "All Time"
        elif sp_start and sp_end:
            period_label = f"{sp_start.strftime('%b %d, %Y')} - {sp_end.strftime('%b %d, %Y')}"
        else:
            period_label = "Selected Period"

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.info(f"### Total Spent: ${total_spent:,.2f}\n**Period:** {period_label}")

        # Display spending summary table
        agg = get_spending_summary(sp_start, sp_end)

        if agg.empty:
            st.info("No BUY transactions in that range.")
        else:
            # Format for display
            display_agg = agg.copy()
            display_agg["Total_Spent_USD"] = display_agg["Total_Spent_USD"].map(
                lambda x: f"${x:,.2f}"
            )
            st.dataframe(display_agg, width='stretch', hide_index=True)
            create_download_button("Download CSV (Spending Log)", agg, "spending_log.csv")