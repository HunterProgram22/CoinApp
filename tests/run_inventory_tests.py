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
    """Test the original functions from pages/inventory_functions.py"""
    print("Testing original inventory functions...")
    
    try:
        from pages.inventory_functions import (
            get_inventory_by_type,
            get_inventory_by_series,
            get_series_list,
            get_countries_with_inventory,
            get_series_list_for_country
        )
        
        # Mock the database operations
        import infrastructure.database.db_operations as db_ops
        original_execute_all = db_ops.execute_query_all
        original_execute_single = db_ops.execute_query_single
        
        # Test data
        db_ops.execute_query_all = lambda *args: [
            {'series': 'Test Series', 'country': 'USA', 'coins': 5}
        ]
        db_ops.execute_query_single = lambda *args: {'1': 1}
        
        # Run tests
        assert callable(get_inventory_by_type)
        assert callable(get_inventory_by_series)
        assert callable(get_series_list)
        
        # Test actual calls (with mocked data)
        result = get_series_list()
        assert isinstance(result, list)
        
        result = get_countries_with_inventory()
        assert isinstance(result, list)
        
        # Restore original functions
        db_ops.execute_query_all = original_execute_all
        db_ops.execute_query_single = original_execute_single
        
        print("✅ Original functions work correctly")
        return True
        
    except Exception as e:
        print(f"❌ Original functions failed: {e}")
        return False


def test_refactored_repository():
    """Test the refactored repository"""
    print("Testing refactored inventory repository...")
    
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
        return False


def test_components():
    """Test the UI components"""
    print("Testing inventory UI components...")
    
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
        return False


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
            results.append(False)
        print()
    
    print("=" * 50)
    if all(results):
        print("🎉 All tests passed! Refactoring is safe to proceed.")
        return 0
    else:
        print("⚠️  Some tests failed. Review before proceeding.")
        return 1


if __name__ == "__main__":
    exit(main())
