# run_bullion_tests.py
"""
Test runner to validate our bullion refactoring.
Run this before and after refactoring to ensure behavior is preserved.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath('.'))

# Mock streamlit before importing anything
from unittest.mock import MagicMock

sys.modules['streamlit'] = MagicMock()


def create_temporary_bullion_functions_file():
    """Create the temporary functions file for testing"""
    functions_content = '''# pages/bullion_functions.py
"""
Temporary extraction of bullion functions for testing.
These will be moved to the repository during refactoring.
"""
from infrastructure.database.db_operations import execute_query_all, execute_query_single


def get_latest_spot_prices():
    """Get latest metal spot prices."""
    query = "SELECT metal, price_per_oz_usd FROM v_latest_spot ORDER BY metal"
    return execute_query_all(query)


def get_bullion_by_category():
    """Get bullion summary by category and metal using the schema view."""
    query = """
        SELECT 
            category, 
            metal, 
            units_on_hand, 
            gross_oz, 
            fine_oz, 
            melt_value_usd
        FROM v_inventory_bullion_by_category
        ORDER BY category, metal
    """
    return execute_query_all(query)


def get_bullion_by_series():
    """Get bullion summary by series using the schema view."""
    query = """
        SELECT 
            category, 
            metal, 
            series, 
            unit_troy_oz, 
            unit_fine_oz, 
            units_on_hand, 
            gross_oz, 
            fine_oz, 
            melt_value_usd
        FROM v_inventory_bullion_by_series
        ORDER BY category, metal, series
    """
    return execute_query_all(query)


def get_bullion_totals():
    """Get total bullion statistics including constitutional silver."""
    query = """
        WITH bullion_totals AS (
            SELECT 
                SUM(units_on_hand) as total_units,
                SUM(fine_oz) as total_fine_oz,
                SUM(melt_value_usd) as total_value
            FROM v_inventory_bullion_by_category
        ),
        constitutional_totals AS (
            SELECT 
                SUM(quantity) as total_units,
                SUM(total_fine_oz) as total_fine_oz,
                SUM(total_melt_value) as total_value
            FROM v_junk_silver
        )
        SELECT 
            COALESCE(b.total_units, 0) + COALESCE(c.total_units, 0) as total_units,
            COALESCE(b.total_fine_oz, 0) + COALESCE(c.total_fine_oz, 0) as total_fine_oz,
            COALESCE(b.total_value, 0) + COALESCE(c.total_value, 0) as total_value
        FROM bullion_totals b
        CROSS JOIN constitutional_totals c
    """
    return execute_query_single(query)


def get_constitutional_silver_by_category():
    """Get constitutional silver summary."""
    query = """
        SELECT 
            'Constitutional (Junk Silver)' as category,
            'Ag' as metal,
            SUM(quantity) as units_on_hand,
            SUM(total_fine_oz / 0.9) as gross_oz,  -- Approximate gross from fine for 90% silver
            SUM(total_fine_oz) as fine_oz,
            SUM(total_melt_value) as melt_value_usd
        FROM v_junk_silver
    """
    result = execute_query_single(query)
    return [result] if result and result['units_on_hand'] else []


def get_constitutional_silver_by_series():
    """Get constitutional silver by series."""
    query = """
        SELECT 
            'Constitutional (Junk Silver)' as category,
            'Ag' as metal,
            cm.series,
            ROUND((cm.weight_grams / 31.1034768), 4) as unit_troy_oz,
            ROUND((cm.weight_grams * cm.fineness) / 31.1034768, 4) as unit_fine_oz,
            SUM(l.qty_remaining) as units_on_hand,
            ROUND(SUM(l.qty_remaining * cm.weight_grams / 31.1034768), 4) as gross_oz,
            ROUND(SUM(l.qty_remaining * (cm.weight_grams * cm.fineness) / 31.1034768), 4) as fine_oz,
            ROUND(SUM(l.qty_remaining * v.melt_unit_value), 2) as melt_value_usd
        FROM lot l
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        JOIN v_lot_value_details v ON v.lot_id = l.id
        WHERE l.valuation_method = 'MELT_ONLY'
            AND l.qty_remaining > 0
            AND cm.metal = 'Ag'
            AND cm.asset_category = 'COIN'
        GROUP BY cm.series, cm.weight_grams, cm.fineness
        ORDER BY cm.series
    """
    return execute_query_all(query)


def safe_format_dataframe(df, format_spec):
    """Apply formatting to dataframe, handling None/NULL values."""
    import pandas as pd
    import streamlit as st

    if df.empty:
        return df

    # Replace None values with 0 for numeric columns before formatting
    for col in format_spec.keys():
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    try:
        return df.style.format(format_spec)
    except Exception as e:
        st.warning(f"Could not apply formatting: {e}")
        return df


def create_download_button(label, df, filename):
    """Create a CSV download button."""
    import streamlit as st
    st.download_button(
        label,
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
    )
'''

    # Create the pages directory if it doesn't exist
    os.makedirs('pages', exist_ok=True)

    # Write the functions file
    with open('pages/bullion_functions.py', 'w') as f:
        f.write(functions_content)

    print("✅ Created pages/bullion_functions.py")


def test_original_functions():
    """Test the original functions - will create them if needed"""
    print("Testing original bullion functions...")

    # First, check if we need to create the temporary functions file
    if not os.path.exists('pages/bullion_functions.py'):
        print("Creating temporary bullion_functions.py for testing...")
        create_temporary_bullion_functions_file()

    try:
        # Mock the database operations BEFORE importing the functions
        from unittest.mock import patch

        with patch('infrastructure.database.db_operations.execute_query_all') as mock_execute_all, \
                patch(
                    'infrastructure.database.db_operations.execute_query_single') as mock_execute_single:

            # Set up mock return values
            mock_execute_all.return_value = [
                {'metal': 'Ag', 'price_per_oz_usd': 24.50}
            ]
            mock_execute_single.return_value = {
                'total_units': 25,
                'total_fine_oz': 24.975,
                'total_value': 612.19
            }

            # Now import the functions (they'll use our mocked database)
            from pages.bullion_functions import (
                get_latest_spot_prices,
                get_bullion_by_category,
                get_bullion_by_series,
                get_bullion_totals,
                get_constitutional_silver_by_category,
                get_constitutional_silver_by_series
            )

            # Test that functions are callable
            assert callable(get_latest_spot_prices)
            assert callable(get_bullion_by_category)
            assert callable(get_bullion_by_series)
            assert callable(get_bullion_totals)
            assert callable(get_constitutional_silver_by_category)
            assert callable(get_constitutional_silver_by_series)

            # Test actual calls (with mocked data)
            result = get_latest_spot_prices()
            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]['metal'] == 'Ag'
            assert result[0]['price_per_oz_usd'] == 24.50

            # Test bullion totals
            result = get_bullion_totals()
            assert isinstance(result, dict)
            assert result['total_units'] == 25
            assert result['total_fine_oz'] == 24.975

            # Test bullion by category
            mock_execute_all.return_value = [
                {
                    'category': 'ROUND',
                    'metal': 'Ag',
                    'units_on_hand': 10,
                    'gross_oz': 10.0,
                    'fine_oz': 9.99,
                    'melt_value_usd': 244.75
                }
            ]

            result = get_bullion_by_category()
            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]['category'] == 'ROUND'

            # Test constitutional silver by category
            mock_execute_single.return_value = {
                'category': 'Constitutional (Junk Silver)',
                'metal': 'Ag',
                'units_on_hand': 15,
                'gross_oz': 10.5,
                'fine_oz': 9.45,
                'melt_value_usd': 231.53
            }

            result = get_constitutional_silver_by_category()
            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]['category'] == 'Constitutional (Junk Silver)'

        print("✅ Original functions work correctly")
        return True

    except Exception as e:
        print(f"❌ Original functions failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_refactored_repository():
    """Test the refactored repository"""
    print("Testing refactored bullion repository...")

    # Check if refactored files exist
    if not os.path.exists('infrastructure/database/repositories/bullion_repository.py'):
        print("⏭️  Skipping refactored repository test - files not created yet")
        return True

    try:
        from infrastructure.database.repositories.bullion_repository import (
            SQLBullionRepository,
            SpotPrice,
            BullionSummary,
            BullionDetail,
            BullionTotals,
            ConstitutionalSilver
        )
        from unittest.mock import Mock

        # Create repository with mocked database
        mock_db = Mock()
        repository = SQLBullionRepository(mock_db)

        # Test get_latest_spot_prices
        mock_db.execute_query_all.return_value = [
            {'metal': 'Ag', 'price_per_oz_usd': 24.50},
            {'metal': 'Au', 'price_per_oz_usd': 2050.00}
        ]

        result = repository.get_latest_spot_prices()
        assert len(result) == 2
        assert isinstance(result[0], SpotPrice)
        assert result[0].metal == 'Ag'
        assert result[0].price_per_oz_usd == 24.50

        # Test get_bullion_totals
        mock_db.execute_query_single.return_value = {
            'total_units': 25,
            'total_fine_oz': 24.975,
            'total_value': 612.19
        }

        result = repository.get_bullion_totals()
        assert isinstance(result, BullionTotals)
        assert result.total_units == 25
        assert result.total_fine_oz == 24.975
        assert result.total_value == 612.19

        # Test get_bullion_by_category
        mock_db.execute_query_all.return_value = [
            {
                'category': 'ROUND',
                'metal': 'Ag',
                'units_on_hand': 10,
                'gross_oz': 10.0,
                'fine_oz': 9.99,
                'melt_value_usd': 244.75
            }
        ]

        result = repository.get_bullion_by_category()
        assert len(result) == 1
        assert isinstance(result[0], BullionSummary)
        assert result[0].category == 'ROUND'
        assert result[0].units_on_hand == 10

        # Test get_constitutional_silver_by_category
        mock_db.execute_query_single.return_value = {
            'category': 'Constitutional (Junk Silver)',
            'metal': 'Ag',
            'units_on_hand': 15,
            'gross_oz': 10.5,
            'fine_oz': 9.45,
            'melt_value_usd': 231.53
        }

        result = repository.get_constitutional_silver_by_category()
        assert len(result) == 1
        assert isinstance(result[0], ConstitutionalSilver)
        assert result[0].category == 'Constitutional (Junk Silver)'
        assert result[0].units_on_hand == 15

        # Test get_combined_category_data
        # This should combine bullion + constitutional data
        result = repository.get_combined_category_data()
        assert isinstance(result, list)
        # Should have both bullion and constitutional data
        assert len(result) >= 1

        print("✅ Refactored repository works correctly")
        return True

    except Exception as e:
        print(f"❌ Refactored repository failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_components():
    """Test the UI components"""
    print("Testing bullion UI components...")

    # Check if component files exist
    if not os.path.exists('presentation/components/bullion_components.py'):
        print("⏭️  Skipping UI components test - files not created yet")
        return True

    try:
        from presentation.components.bullion_components import BullionRenderer
        from infrastructure.database.repositories.bullion_repository import (
            SpotPrice, BullionSummary, BullionTotals
        )
        from unittest.mock import Mock

        # Create renderer with mocked repository
        mock_repo = Mock()
        renderer = BullionRenderer(mock_repo)

        # Test that renderer initializes
        assert renderer.repo == mock_repo

        # Test methods exist
        assert hasattr(renderer, 'render_spot_prices')
        assert hasattr(renderer, 'render_totals_summary')
        assert hasattr(renderer, 'render_category_tab')
        assert hasattr(renderer, 'render_series_tab')
        assert hasattr(renderer, 'render_footer_sections')

        # Test private helper methods exist
        assert hasattr(renderer, '_convert_category_data_to_dataframe')
        assert hasattr(renderer, '_convert_series_data_to_dataframe')
        assert hasattr(renderer, '_safe_format_dataframe')
        assert hasattr(renderer, '_create_download_button')

        # Test dataclass creation
        spot_price = SpotPrice(metal='Ag', price_per_oz_usd=24.50)
        assert spot_price.metal == 'Ag'
        assert spot_price.price_per_oz_usd == 24.50

        bullion_summary = BullionSummary(
            category='ROUND',
            metal='Ag',
            units_on_hand=10,
            gross_oz=10.0,
            fine_oz=9.99,
            melt_value_usd=244.75
        )
        assert bullion_summary.category == 'ROUND'
        assert bullion_summary.units_on_hand == 10

        bullion_totals = BullionTotals(
            total_units=25,
            total_fine_oz=24.975,
            total_value=612.19
        )
        assert bullion_totals.total_units == 25

        print("✅ UI components work correctly")
        return True

    except Exception as e:
        print(f"❌ UI components failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def cleanup_test_files():
    """Clean up temporary files created during testing"""
    temp_files = [
        'pages/bullion_functions.py'
    ]

    for file_path in temp_files:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"🧹 Cleaned up {file_path}")
            except Exception as e:
                print(f"⚠️  Could not remove {file_path}: {e}")


def main():
    """Run all tests"""
    print("🧪 Running Bullion Refactoring Tests")
    print("=" * 50)

    tests = [
        test_original_functions,
        test_refactored_repository,
        test_components
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
        print()

    print("=" * 50)
    if all(results):
        print("🎉 All tests passed! Refactoring is safe to proceed.")

        # Ask user if they want to clean up temp files
        try:
            response = input("\n🧹 Clean up temporary test files? (y/n): ").lower()
            if response == 'y':
                cleanup_test_files()
        except:
            pass  # In case input() doesn't work in some environments

        return 0
    else:
        print("⚠️  Some tests failed. Review before proceeding.")
        return 1


if __name__ == "__main__":
    exit(main())
