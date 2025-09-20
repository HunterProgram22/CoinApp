# infrastructure/database/repositories/import_repository.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd


@dataclass
class ImportResult:
    """Result of an import operation"""
    success: bool
    created_count: int
    updated_count: int
    error_count: int
    errors: List[str]
    dry_run: bool


@dataclass
class ValidationResult:
    """Result of validation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]


class ImportDataRepository(ABC):
    """Abstract interface for data import operations"""

    @abstractmethod
    def import_transaction_batch(self, transactions: List[Dict[str, Any]],
                                 dry_run: bool = True) -> ImportResult:
        """Import a batch of transactions"""
        pass

    @abstractmethod
    def import_coin_masters(self, masters: List[Dict[str, Any]],
                            dry_run: bool = True) -> ImportResult:
        """Import coin masters"""
        pass

    @abstractmethod
    def import_coin_types(self, types: List[Dict[str, Any]], dry_run: bool = True) -> ImportResult:
        """Import coin types"""
        pass

    @abstractmethod
    def validate_transaction_data(self, data: pd.DataFrame) -> ValidationResult:
        """Validate transaction data before import"""
        pass

    @abstractmethod
    def validate_master_data(self, data: pd.DataFrame) -> ValidationResult:
        """Validate coin master data before import"""
        pass

    @abstractmethod
    def validate_type_data(self, data: pd.DataFrame) -> ValidationResult:
        """Validate coin type data before import"""
        pass


class ImportRepository(ImportDataRepository):
    """Concrete implementation of import repository"""

    def __init__(self, db_executor):
        self.db = db_executor

    def import_transaction_batch(self, transactions: List[Dict[str, Any]],
                                 dry_run: bool = True) -> ImportResult:
        """Import a batch of transactions"""
        from core.business_logic import TransactionBuilder
        from core.queries import find_or_create_party, find_or_create_storage
        from infrastructure.database.db import get_conn

        created = 0
        errors = []

        if dry_run:
            # Validation only
            for tx_data in transactions:
                try:
                    # Validate required fields
                    if not all(k in tx_data for k in ['tx_date', 'tx_type', 'items']):
                        errors.append(f"Missing required transaction fields")
                        continue

                    for item in tx_data.get('items', []):
                        if not all(k in item for k in ['coin_type_id', 'quantity']):
                            errors.append(f"Missing required item fields")
                            continue

                    created += 1
                except Exception as e:
                    errors.append(str(e))

            return ImportResult(
                success=len(errors) == 0,
                created_count=created,
                updated_count=0,
                error_count=len(errors),
                errors=errors,
                dry_run=True
            )

        # Actual import
        with get_conn() as conn:
            for tx_data in transactions:
                try:
                    builder = TransactionBuilder()
                    builder.set_basic_info(
                        tx_data['tx_date'],
                        tx_data['tx_type'],
                        tx_data.get('party_name'),
                        tx_data.get('currency', 'USD')
                    )
                    builder.set_costs(
                        tx_data.get('shipping', 0),
                        tx_data.get('tax', 0),
                        tx_data.get('fees', 0)
                    )
                    builder.set_notes(tx_data.get('notes'))

                    for item in tx_data.get('items', []):
                        builder.add_item(**item)

                    if tx_data['tx_type'] == 'BUY':
                        builder.build_buy_transaction()
                    elif tx_data['tx_type'] == 'SELL':
                        builder.build_sell_transaction()

                    created += 1
                except Exception as e:
                    errors.append(f"Transaction import error: {str(e)}")

        return ImportResult(
            success=len(errors) == 0,
            created_count=created,
            updated_count=0,
            error_count=len(errors),
            errors=errors[:50],  # Limit errors shown
            dry_run=False
        )

    def import_coin_masters(self, masters: List[Dict[str, Any]],
                            dry_run: bool = True) -> ImportResult:
        """Import coin masters"""
        from core.queries import upsert_coin_master

        created = 0
        updated = 0
        errors = []

        for master in masters:
            try:
                if not dry_run:
                    result = upsert_coin_master(
                        master['country'],
                        master['denomination'],
                        master['series'],
                        master.get('metal'),
                        master.get('fineness'),
                        master.get('weight_grams'),
                        master.get('diameter_mm'),
                        master.get('thickness_mm'),
                        master.get('edge'),
                        master.get('years_start'),
                        master.get('years_end'),
                        master.get('notes'),
                        master.get('asset_category', 'COIN'),
                        master.get('numista_url'),
                        master.get('ngc_url'),
                        master.get('pcgs_url')
                    )
                    updated += 1
                else:
                    created += 1
            except Exception as e:
                errors.append(f"Master '{master.get('series', 'unknown')}': {str(e)}")

        return ImportResult(
            success=len(errors) == 0,
            created_count=created if dry_run else 0,
            updated_count=updated,
            error_count=len(errors),
            errors=errors[:50],
            dry_run=dry_run
        )

    def import_coin_types(self, types: List[Dict[str, Any]], dry_run: bool = True) -> ImportResult:
        """Import coin types"""
        from core.queries import upsert_coin_master, upsert_coin_type

        created = 0
        errors = []

        for coin_type in types:
            try:
                if not dry_run:
                    # First ensure master exists
                    master_id = upsert_coin_master(
                        coin_type['country'],
                        coin_type['denomination'],
                        coin_type['series']
                    )

                    # Then create/update type
                    upsert_coin_type(
                        master_id,
                        coin_type['year'],
                        coin_type.get('mint_mark', ''),
                        coin_type.get('variety', ''),
                        mintage=coin_type.get('mintage'),
                        is_proof=coin_type.get('is_proof', 0),
                        designer=coin_type.get('designer'),
                        obv_desc=coin_type.get('obv_desc'),
                        rev_desc=coin_type.get('rev_desc')
                    )
                created += 1
            except Exception as e:
                errors.append(
                    f"Type '{coin_type.get('series', 'unknown')} {coin_type.get('year', '')}': {str(e)}")

        return ImportResult(
            success=len(errors) == 0,
            created_count=created,
            updated_count=0,
            error_count=len(errors),
            errors=errors[:50],
            dry_run=dry_run
        )

    def validate_transaction_data(self, data: pd.DataFrame) -> ValidationResult:
        """Validate transaction data before import"""
        errors = []
        warnings = []

        required_cols = ['tx_date', 'tx_type', 'country', 'denomination', 'series',
                         'year', 'quantity', 'unit_price']

        # Check required columns
        missing = [col for col in required_cols if col not in data.columns]
        if missing:
            errors.append(f"Missing required columns: {', '.join(missing)}")
            return ValidationResult(False, errors, warnings)

        # Validate tx_type values
        invalid_types = data[~data['tx_type'].isin(['BUY', 'SELL'])]['tx_type'].unique()
        if len(invalid_types) > 0:
            errors.append(f"Invalid tx_type values: {', '.join(invalid_types)}")

        # Check for nulls in required fields
        for col in required_cols:
            null_count = data[col].isna().sum()
            if null_count > 0:
                errors.append(f"Column '{col}' has {null_count} empty values")

        # Warnings for optional fields
        if 'mint_mark' not in data.columns:
            warnings.append("No mint_mark column - will use blank")
        if 'variety' not in data.columns:
            warnings.append("No variety column - will use blank")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def validate_master_data(self, data: pd.DataFrame) -> ValidationResult:
        """Validate coin master data before import"""
        errors = []
        warnings = []

        required = ["country", "denomination", "series"]
        missing = [c for c in required if c not in data.columns]

        if missing:
            errors.append(f"Missing required columns: {', '.join(missing)}")

        # Check for nulls in required fields
        for col in required:
            if col in data.columns:
                null_count = data[col].isna().sum()
                if null_count > 0:
                    errors.append(f"Column '{col}' has {null_count} empty values")

        # Validate numeric fields if present
        numeric_fields = ['fineness', 'weight_grams', 'diameter_mm', 'thickness_mm']
        for field in numeric_fields:
            if field in data.columns:
                try:
                    pd.to_numeric(data[field], errors='coerce')
                except:
                    warnings.append(f"Non-numeric values in '{field}' column")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def validate_type_data(self, data: pd.DataFrame) -> ValidationResult:
        """Validate coin type data before import"""
        errors = []
        warnings = []

        required = ["country", "denomination", "series", "year"]
        missing = [c for c in required if c not in data.columns]

        if missing:
            errors.append(f"Missing required columns: {', '.join(missing)}")

        # Check for nulls in required fields
        for col in required:
            if col in data.columns:
                null_count = data[col].isna().sum()
                if null_count > 0:
                    errors.append(f"Column '{col}' has {null_count} empty values")

        # Validate year is numeric
        if 'year' in data.columns:
            try:
                pd.to_numeric(data['year'], errors='coerce')
            except:
                errors.append("Non-numeric values in 'year' column")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
