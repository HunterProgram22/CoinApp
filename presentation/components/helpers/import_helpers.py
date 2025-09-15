# import_helpers.py
"""Helper functions and classes for data import operations."""
import pandas as pd
import streamlit as st
from typing import Dict, Any, Optional, Tuple
from infrastructure.database.db import get_conn
from core.queries import (
    upsert_coin_master,
    upsert_coin_type,
    upsert_storage,
    create_buy_transaction,
    create_sell_transaction,
)
from core.constants import ASSET_CATEGORIES

# ---------------------------------
# Data Normalization Functions
# ---------------------------------
BAD_EMPTY_VALUES = {"", "-", "–", "None", "none", "null", "nan", "NaN"}


def normalize_text(value: Any) -> Optional[str]:
    """Normalize text value, returning None for empty-like values."""
    if value is None:
        return None
    s = str(value).strip()
    return None if s in BAD_EMPTY_VALUES else s


def normalize_asset_category(value: Any) -> Optional[str]:
    """Normalize and validate asset category."""
    if value is None:
        return None
    s = str(value).strip().upper()
    return s if s in ASSET_CATEGORIES else None


def normalize_boolean(value: Any) -> bool:
    """Normalize boolean value from various formats."""
    if value is None:
        return False
    
    s = str(value).strip().lower()
    if s in {"1", "true", "yes", "y", "proof"}:
        return True
    elif s in {"0", "false", "no", "n", "business", "regular"}:
        return False
    else:
        return False


def safe_float(value: Any, default: float = 0.0) -> float:
    """Convert to float safely."""
    if value is None or value == "" or str(value).strip().lower() in {"nan", "none", "null", "-",
                                                                      "–"}:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """Convert to int safely."""
    if value is None or value == "" or str(value).strip().lower() in {"nan", "none", "null", "-",
                                                                      "–"}:
        return default
    try:
        return int(float(value))  # Handle "1.0" -> 1
    except (ValueError, TypeError):
        return default


def read_uploaded_file(uploaded_file) -> pd.DataFrame:
    """Read CSV or Excel file."""
    name = uploaded_file.name.lower()
    if name.endswith(".xlsx") or name.endswith(".xls"):
        try:
            return pd.read_excel(uploaded_file)
        except Exception as e:
            st.error(f"Unable to read Excel: {e}")
            st.stop()
    return pd.read_csv(uploaded_file)


# ---------------------------------
# Master Matching Functions
# ---------------------------------
class MasterMatcher:
    """Handle coin master matching and reporting."""

    def __init__(self):
        self.masters_to_create = []
        self.masters_matched = []
        self.master_mismatches = []

    def check_master(self, country: str, denomination: str, series: str,
                     requested_category: Optional[str] = None) -> Tuple[
        bool, Optional[int], Optional[str]]:
        """Check if master exists and return (exists, master_id, current_category)."""
        with get_conn() as cx:
            existing = cx.execute(
                "SELECT id, asset_category FROM coin_master WHERE country=? AND denomination=? AND series=?",
                (country, denomination, series)
            ).fetchone()

        if existing:
            self.masters_matched.append({
                'series': series,
                'country': country,
                'denomination': denomination,
                'existing_category': existing['asset_category'],
                'requested_category': requested_category or 'COIN'
            })

            # Check for category mismatch
            if requested_category and requested_category != existing['asset_category']:
                self.master_mismatches.append({
                    'series': series,
                    'current': existing['asset_category'],
                    'requested': requested_category
                })

            return True, existing['id'], existing['asset_category']
        else:
            self.masters_to_create.append({
                'country': country,
                'denomination': denomination,
                'series': series,
                'category': requested_category or 'COIN'
            })
            return False, None, None

    def display_report(self):
        """Display the master matching report in Streamlit."""
        if self.masters_matched:
            st.info(f"✓ Found {len(self.masters_matched)} existing masters")
            with st.expander(f"View matched masters ({len(self.masters_matched)})"):
                for m in self.masters_matched:
                    st.write(
                        f"• **{m['series']}** ({m['country']}/{m['denomination']}) - Category: {m['existing_category']}")

        if self.masters_to_create:
            st.warning(f"⚠️ Would create {len(self.masters_to_create)} NEW masters")
            with st.expander(f"View new masters to be created ({len(self.masters_to_create)})",
                             expanded=True):
                st.write(
                    "These series were NOT found and will be created with the specified category:")
                for m in self.masters_to_create:
                    cat_display = m['category'] if m['category'] else 'COIN (default)'
                    st.write(
                        f"• **{m['series']}** ({m['country']}/{m['denomination']}) → {cat_display}")
                st.caption(
                    "💡 If these should match existing masters, check for exact spelling/spacing in your import file")

        if self.master_mismatches:
            st.warning(f"⚠️ Found {len(self.master_mismatches)} category mismatches")
            with st.expander(f"View category mismatches ({len(self.master_mismatches)})"):
                st.write("These masters exist but have different categories:")
                for m in self.master_mismatches:
                    st.write(
                        f"• **{m['series']}** - Current: {m['current']}, Requested: {m['requested']}")
                st.caption("The import will update these to the requested category")


# ---------------------------------
# Transaction Import Class
# ---------------------------------
class TransactionImporter:
    """Handle transaction import logic."""

    REQUIRED_COLUMNS = [
        'tx_date', 'tx_type', 'country', 'denomination', 'series',
        'year', 'mint_mark', 'variety', 'quantity', 'unit_price'
    ]

    OPTIONAL_COLUMNS = [
        'party', 'currency', 'shipping', 'tax', 'fees', 'notes',
        'purchase_grade_company', 'purchase_grade_text', 'purchase_numeric_grade',
        'estimated_grade_text', 'estimated_numeric_grade', 'valuation_method',
        'manual_est_unit_value', 'storage_location', 'slab_cert', 'asset_category',
        'is_proof'  # Added is_proof support
    ]

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.problems = []
        self.created_tx = 0
        self.created_lines = 0
        self.master_matcher = MasterMatcher()

    def validate_columns(self) -> bool:
        """Validate required columns exist."""
        missing = [c for c in self.REQUIRED_COLUMNS if c not in self.df.columns]
        if missing:
            st.error("Missing required columns: " + ", ".join(missing))
            return False
        return True

    def prepare_dataframe(self):
        """Add missing optional columns and normalize data types."""
        # Add missing optional columns
        for col in self.OPTIONAL_COLUMNS:
            if col not in self.df.columns:
                self.df[col] = None

        # Normalize data types
        self.df['tx_date'] = pd.to_datetime(self.df['tx_date'], errors='coerce').dt.date
        self.df['tx_type'] = self.df['tx_type'].astype(str).str.strip().str.upper()
        self.df['quantity'] = pd.to_numeric(self.df['quantity'], errors='coerce').fillna(0).astype(
            int)
        self.df['unit_price'] = pd.to_numeric(self.df['unit_price'], errors='coerce').fillna(0.0)

        # Normalize money columns
        for col in ['shipping', 'tax', 'fees']:
            if col in self.df.columns:
                self.df[col] = pd.to_numeric(self.df[col], errors='coerce').fillna(0.0)
            else:
                self.df[col] = 0.0

        # Normalize asset_category
        if 'asset_category' in self.df.columns:
            self.df['asset_category'] = self.df['asset_category'].apply(normalize_asset_category)
        
        # Normalize is_proof
        if 'is_proof' in self.df.columns:
            self.df['is_proof'] = self.df['is_proof'].apply(normalize_boolean)

    def validate_data(self) -> bool:
        """Validate data integrity."""
        if self.df['tx_date'].isna().any():
            st.error("Some rows have invalid tx_date.")
            return False
        if (~self.df['tx_type'].isin(['BUY', 'SELL'])).any():
            st.error("Some rows have invalid tx_type (must be BUY/SELL).")
            return False
        return True

    def process_transaction_group(self, tx_date, tx_type, party, group_df, dry_run: bool):
        """Process a group of transaction lines."""
        # Normalize header fields
        try:
            tx_date_iso = tx_date.isoformat() if hasattr(tx_date, 'isoformat') else str(
                pd.to_datetime(tx_date).date())
        except Exception:
            self.problems.append(f"Invalid tx_date: {tx_date}")
            return

        tx_type_u = str(tx_type).strip().upper()
        if tx_type_u not in ("BUY", "SELL"):
            self.problems.append(f"Invalid tx_type: {tx_type}")
            return

        # Get currency
        if 'currency' in group_df.columns and not group_df['currency'].dropna().empty:
            currency = str(group_df['currency'].dropna().astype(str).str.strip().iloc[0] or "USD")
        else:
            currency = "USD"

        # Sum up costs
        ship = float(group_df['shipping'].sum())
        tax = float(group_df['tax'].sum())
        fees = float(group_df['fees'].sum())
        notes = None

        items = []
        for _, row in group_df.iterrows():
            # Process each line item
            item = self.process_line_item(row, dry_run)
            if item:
                items.append(item)

        if dry_run:
            self.created_tx += 1
            self.created_lines += len(items)
        else:
            self.create_transaction(tx_date_iso, tx_type_u, party, currency,
                                    ship, tax, fees, notes, items)

    def process_line_item(self, row, dry_run: bool) -> Optional[Dict[str, Any]]:
        """Process a single line item."""
        country = str(row['country'])
        denomination = str(row['denomination'])
        series = str(row['series'])

        # Check/create master
        cat = normalize_asset_category(
            row.get('asset_category')) if 'asset_category' in row else None

        if dry_run:
            self.master_matcher.check_master(country, denomination, series, cat)
            master_id = 1  # Dummy for dry run
        else:
            master_id = upsert_coin_master(country, denomination, series)
            if cat:
                try:
                    with get_conn() as cx:
                        cx.execute("UPDATE coin_master SET asset_category=? WHERE id=?",
                                   (cat, master_id))
                except Exception as e:
                    self.problems.append(f"Could not set asset_category for {series}: {e}")

        # Process coin type
        try:
            year = int(row['year'])
        except Exception:
            self.problems.append(f"Invalid year: {row.get('year')}")
            return None

        mint_mark = normalize_text(row.get('mint_mark')) or ""
        variety = normalize_text(row.get('variety')) or ""
        
        # Handle is_proof
        is_proof = normalize_boolean(row.get('is_proof', False))

        if not dry_run:
            # Create/update coin type with is_proof
            coin_type_id = upsert_coin_type(master_id, year, mint_mark, variety, is_proof=1 if is_proof else 0)
        else:
            coin_type_id = 1  # Dummy for dry run

        # Valuation and storage
        valuation = str(row.get('valuation_method') or 'AUTO').upper()
        if valuation not in ('AUTO', 'MELT_ONLY', 'GUIDE_ONLY', 'MANUAL'):
            valuation = 'AUTO'

        storage_name = normalize_text(row.get('storage_location'))
        storage_id = upsert_storage(storage_name) if (storage_name and not dry_run) else None

        return {
            'coin_type_id': coin_type_id,
            'quantity': safe_int(row.get('quantity')),
            'unit_price': safe_float(row.get('unit_price')),
            'purchase_grade_company': normalize_text(row.get('purchase_grade_company')),
            'purchase_grade_text': normalize_text(row.get('purchase_grade_text')),
            'purchase_numeric_grade': safe_float(row.get('purchase_numeric_grade')),
            'slab_cert': normalize_text(row.get('slab_cert')),
            'estimated_grade_text': normalize_text(row.get('estimated_grade_text')),
            'estimated_numeric_grade': safe_float(row.get('estimated_numeric_grade')),
            'valuation_method': valuation,
            'manual_est_unit_value': safe_float(row.get('manual_est_unit_value')),
            'storage_location_id': storage_id,
            'lot_notes': normalize_text(row.get('notes'))
        }

    def create_transaction(self, tx_date_iso, tx_type, party, currency,
                           ship, tax, fees, notes, items):
        """Create the actual transaction."""
        try:
            if tx_type == "BUY":
                create_buy_transaction(tx_date_iso, party, currency, ship, tax, fees, notes, items)
            else:
                sell_items = [{"coin_type_id": it["coin_type_id"],
                               "quantity": it["quantity"],
                               "unit_price": it["unit_price"]} for it in items]
                create_sell_transaction(tx_date_iso, party, currency, ship, tax, fees,
                                        notes, sell_items, method='FIFO')
            self.created_tx += 1
            self.created_lines += len(items)
        except Exception as e:
            self.problems.append(str(e))

    def import_transactions(self, dry_run: bool = True):
        """Main import method."""
        if not self.validate_columns():
            return

        self.prepare_dataframe()

        if not self.validate_data():
            return

        # Group by transaction
        grp_cols = ['tx_date', 'tx_type', 'party']
        for (tx_date, tx_type, party), group_df in self.df.groupby(grp_cols, dropna=False):
            self.process_transaction_group(tx_date, tx_type, party, group_df, dry_run)

        # Display results
        if dry_run:
            st.success(
                f"Dry run OK. Would create ~{self.created_tx} transactions and {self.created_lines} line items.")
            self.master_matcher.display_report()
            self.show_existing_masters()
        else:
            if self.problems:
                st.warning("Import finished with some issues:")
                for p in self.problems[:75]:
                    st.write("• ", p)
                if len(self.problems) > 75:
                    st.caption(f"...and {len(self.problems) - 75} more")
            st.success(
                f"Imported {self.created_tx} transactions and {self.created_lines} line items.")

    def show_existing_masters(self):
        """Show existing masters for reference."""
        with st.expander("📚 Show all existing masters (for reference)"):
            with get_conn() as cx:
                existing_masters = cx.execute(
                    """SELECT country, denomination, series, asset_category 
                       FROM coin_master 
                       ORDER BY series"""
                ).fetchall()
            if existing_masters:
                for em in existing_masters:
                    st.write(
                        f"• {em['series']} ({em['country']}/{em['denomination']}) - {em['asset_category']}")
            else:
                st.write("No masters in database yet")
