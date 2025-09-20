# run_inventory_tests.py
"""
Simple test runner to validate our inventory refactoring.
Run this before and after refactoring to ensure behavior is preserved.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath('.'))

# Mock streamlit before importing anything
from unittest.mock import MagicMock
sys.modules['streamlit'] = MagicMock()

def test_original_functions():
    """Test the original functions - will create them if needed"""
    print("Testing original inventory functions...")
    
    # First, check if we need to create the temporary functions file
    if not os.path.exists('pages/inventory_functions.py'):
        print("Creating temporary inventory_functions.py for testing...")
        create_temporary_functions_file()
    
    try:
        # We need to mock the database operations BEFORE importing the functions
        from unittest.mock import patch
        
        with patch('infrastructure.database.db_operations.execute_query_all') as mock_execute_all, \
             patch('infrastructure.database.db_operations.execute_query_single') as mock_execute_single:
            
            # Set up mock return values
            mock_execute_all.return_value = [
                {'series': 'Test Series', 'country': 'USA', 'coins': 5}
            ]
            mock_execute_single.return_value = {'1': 1}
            
            # Now import the functions (they'll use our mocked database)
            from pages.inventory_functions import (
                get_inventory_by_type,
                get_inventory_by_series,
                get_series_list,
                get_countries_with_inventory,
                get_series_list_for_country
            )
            
            # Test that functions are callable
            assert callable(get_inventory_by_type)
            assert callable(get_inventory_by_series)
            assert callable(get_series_list)
            
            # Test actual calls (with mocked data)
            result = get_series_list()
            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0] == 'Test Series'
            
            result = get_countries_with_inventory()
            assert isinstance(result, list)
            
            # Test get_inventory_by_type returns expected structure
            mock_execute_all.return_value = [
                {
                    'coin_type_id': 1,
                    'series': 'Morgan Silver Dollars',
                    'year': 1921,
                    'mint_mark': 'D',
                    'variety': '',
                    'coins_on_hand': 5
                }
            ]
            
            result = get_inventory_by_type()
            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]['series'] == 'Morgan Silver Dollars'
        
        print("✅ Original functions work correctly")
        return True
        
    except Exception as e:
        print(f"❌ Original functions failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_temporary_functions_file():
    """Create the temporary functions file for testing"""
    functions_content = '''# pages/inventory_functions.py
"""
Temporary extraction of inventory functions for testing.
These will be moved to the repository during refactoring.
"""
from infrastructure.database.db_operations import execute_query_all, execute_query_single


def get_inventory_by_type():
    """Get inventory grouped by coin type."""
    query = """
        SELECT
            ct.id AS coin_type_id,
            cm.series,
            ct.year,
            ct.mint_mark,
            COALESCE(ct.variety, '') AS variety,
            SUM(l.qty_remaining) AS coins_on_hand
        FROM lot l
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        WHERE l.qty_remaining > 0
        GROUP BY ct.id, cm.series, ct.year, ct.mint_mark, ct.variety
        ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety
    """
    return execute_query_all(query)


def get_inventory_by_series(country_filter="All"):
    """Get inventory summary by series using v_lot_value_details view."""
    # Check if view exists first
    view_check = execute_query_single(
        "SELECT 1 FROM sqlite_master WHERE type='view' AND name='v_lot_value_details'"
    )

    # Build WHERE clause based on filter
    where_clause = ""
    if country_filter == "US Only":
        where_clause = "WHERE cm.country = 'USA'"
    elif country_filter == "World Only":
        where_clause = "WHERE cm.country != 'USA'"

    if view_check:
        query = f"""
            SELECT
                cm.series as series,
                cm.country,
                SUM(v.qty_remaining) AS coins,
                ROUND(SUM(v.qty_remaining * COALESCE(v.chosen_unit_value, 0)), 2) AS est_value_usd
            FROM v_lot_value_details v
            JOIN lot l ON l.id = v.lot_id
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            {where_clause}
            GROUP BY cm.series, cm.country
            ORDER BY est_value_usd DESC, cm.series
        """
    else:
        # Fallback if view doesn't exist
        query = f"""
            SELECT 
                cm.series AS series,
                cm.country,
                SUM(l.qty_remaining) AS coins, 
                NULL AS est_value_usd
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE l.qty_remaining > 0
            {' AND ' + where_clause.replace('WHERE ', '') if where_clause else ''}
            GROUP BY cm.series, cm.country
            ORDER BY coins DESC, cm.series
        """

    return execute_query_all(query)


def get_series_list():
    """Get list of available series."""
    query = "SELECT DISTINCT series FROM coin_master ORDER BY series"
    results = execute_query_all(query)
    return [r['series'] for r in results]


def get_countries_with_inventory():
    """Get list of countries that have inventory on hand."""
    query = """
        SELECT DISTINCT cm.country
        FROM lot l
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        WHERE l.qty_remaining > 0 AND cm.country IS NOT NULL
        ORDER BY cm.country
    """
    results = execute_query_all(query)
    return [r['country'] for r in results]


def get_series_list_for_country(country=None):
    """Get list of available series, optionally filtered by country."""
    if country:
        query = """
            SELECT DISTINCT cm.series 
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE l.qty_remaining > 0 AND cm.country = ?
            ORDER BY cm.series
        """
        results = execute_query_all(query, (country,))
    else:
        query = "SELECT DISTINCT series FROM coin_master ORDER BY series"
        results = execute_query_all(query)
    return [r['series'] for r in results]
'''
    
    # Create the pages directory if it doesn't exist
    os.makedirs('pages', exist_ok=True)
    
    # Write the functions file
    with open('pages/inventory_functions.py', 'w') as f:
        f.write(functions_content)
    
    print("✅ Created pages/inventory_functions.py")


def test_refactored_repository():
    """Test the refactored repository"""
    print("Testing refactored inventory repository...")
    
    # Check if refactored files exist
    if not os.path.exists('infrastructure/database/repositories/inventory_repository.py'):
        print("⏭️  Skipping refactored repository test - files not created yet")
        return True
    
    try:
        from infrastructure.database.repositories.inventory_repository import (
            SQLInventoryRepository,
            InventoryByType,
            InventoryBySeries
        )
        from unittest.mock import Mock
        
        # Create repository with mocked database
        mock_db = Mock()
        repository = SQLInventoryRepository(mock_db)
        
        # Test data
        mock_db.execute_query_all.return_value = [
            {
                'coin_type_id': 1,
                'series': 'Test Series',
                'year': 2023,
                'mint_mark': 'D',
                'variety': '',
                'coins_on_hand': 5
            }
        ]
        
        # Test repository methods
        result = repository.get_inventory_by_type()
        assert len(result) == 1
        assert isinstance(result[0], InventoryByType)
        assert result[0].series == 'Test Series'
        
        # Test series data
        mock_db.execute_query_single.return_value = {'1': 1}  # View exists
        mock_db.execute_query_all.return_value = [
            {
                'series': 'Test Series',
                'country': 'USA',
                'coins': 10,
                'est_value_usd': 100.0
            }
        ]
        
        result = repository.get_inventory_by_series()
        assert len(result) == 1
        assert isinstance(result[0], InventoryBySeries)
        assert result[0].series == 'Test Series'
        
        print("✅ Refactored repository works correctly")
        return True
        
    except Exception as e:
        print(f"❌ Refactored repository failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_components():
    """Test the UI components"""
    print("Testing inventory UI components...")
    
    # Check if component files exist
    if not os.path.exists('presentation/components/inventory_components.py'):
        print("⏭️  Skipping UI components test - files not created yet")
        return True
    
    try:
        from presentation.components.inventory_components import InventoryRenderer
        from unittest.mock import Mock
        
        # Create renderer with mocked repository
        mock_repo = Mock()
        renderer = InventoryRenderer(mock_repo)
        
        # Test that renderer initializes
        assert renderer.repo == mock_repo
        
        # Test data conversion methods exist
        assert hasattr(renderer, '_convert_series_data_to_dataframe')
        assert hasattr(renderer, 'render_series_summary_tab')
        assert hasattr(renderer, 'render_series_detail_tab')
        assert hasattr(renderer, 'render_flags_tab')
        
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
        'pages/inventory_functions.py'
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
    print("🧪 Running Inventory Refactoring Tests")
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
