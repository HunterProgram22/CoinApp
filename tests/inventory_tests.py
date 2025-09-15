# tests/test_inventory_characterization.py
"""
Characterization tests for Inventory functionality.
These tests capture the current behavior before and after refactoring.
"""
import pytest
from unittest.mock import patch, MagicMock, Mock
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock streamlit before importing any modules that use it
sys.modules['streamlit'] = MagicMock()

# Import the refactored repository
from infrastructure.database.repositories.inventory_repository import (
    SQLInventoryRepository,
    InventoryByType,
    InventoryBySeries,
    SeriesDetail,
    FlaggedInventory
)


class TestInventoryRepository:
    """Test the inventory repository behavior"""
    
    def test_get_inventory_by_type_returns_expected_structure(self):
        """Test that get_inventory_by_type returns expected data structure"""
        # Arrange
        mock_db = Mock()
        repository = SQLInventoryRepository(mock_db)
        mock_db.execute_query_all.return_value = [
            {
                'coin_type_id': 1,
                'series': 'Morgan Silver Dollars',
                'year': 1921,
                'mint_mark': 'D',
                'variety': '',
                'coins_on_hand': 5
            }
        ]
        
        # Act
        result = repository.get_inventory_by_type()
        
        # Assert
        assert len(result) == 1
        assert isinstance(result[0], InventoryByType)
        assert result[0].coin_type_id == 1
        assert result[0].series == 'Morgan Silver Dollars'
        assert result[0].year == 1921
        assert result[0].coins_on_hand == 5
        
        # Verify the SQL query structure
        mock_db.execute_query_all.assert_called_once()
        called_args = mock_db.execute_query_all.call_args[0]
        query = called_args[0]
        assert 'SELECT' in query
        assert 'coin_type_id' in query
        assert 'series' in query
        assert 'qty_remaining > 0' in query
        assert 'GROUP BY' in query
        assert 'ORDER BY' in query

    def test_get_inventory_by_series_with_view_exists(self):
        """Test get_inventory_by_series when view exists"""
        # Arrange
        mock_db = Mock()
        repository = SQLInventoryRepository(mock_db)
        mock_db.execute_query_single.return_value = {'1': 1}  # View exists
        mock_db.execute_query_all.return_value = [
            {
                'series': 'Morgan Silver Dollars',
                'country': 'USA',
                'coins': 10,
                'est_value_usd': 250.50
            }
        ]
        
        # Act
        result = repository.get_inventory_by_series("All")
        
        # Assert
        assert len(result) == 1
        assert isinstance(result[0], InventoryBySeries)
        assert result[0].series == 'Morgan Silver Dollars'
        assert result[0].country == 'USA'
        assert result[0].coins == 10
        assert result[0].est_value_usd == 250.50
        
        mock_db.execute_query_single.assert_called_once()
        mock_db.execute_query_all.assert_called_once()
        
        # Verify view check query
        view_check_query = mock_db.execute_query_single.call_args[0][0]
        assert 'v_lot_value_details' in view_check_query
        
        # Verify main query uses view
        main_query = mock_db.execute_query_all.call_args[0][0]
        assert 'v_lot_value_details' in main_query

    @patch('pages.inventory_functions.execute_query_single')
    @patch('pages.inventory_functions.execute_query_all')
    def test_get_inventory_by_series_without_view(self, mock_execute_all, mock_execute_single):
        """Test get_inventory_by_series when view doesn't exist"""
        # Arrange
        mock_execute_single.return_value = None  # View doesn't exist
        expected_result = [
            {
                'series': 'Morgan Silver Dollars',
                'country': 'USA', 
                'coins': 10,
                'est_value_usd': None
            }
        ]
        mock_execute_all.return_value = expected_result
        
        # Act
        result = get_inventory_by_series("All")
        
        # Assert
        assert result == expected_result
        
        # Verify fallback query doesn't use view
        main_query = mock_execute_all.call_args[0][0]
        assert 'v_lot_value_details' not in main_query
        assert 'lot l' in main_query

    @patch('pages.inventory_functions.execute_query_all')
    def test_get_inventory_by_series_us_only_filter(self, mock_execute):
        """Test country filter functionality"""
        # Arrange
        mock_execute.side_effect = [
            {'1': 1},  # View check
            [{'series': 'Morgan Silver Dollars', 'country': 'USA', 'coins': 5}]
        ]
        
        # Act
        result = get_inventory_by_series("US Only")
        
        # Assert - verify WHERE clause is added for US filter
        main_query_call = mock_execute.call_args_list[1]
        query = main_query_call[0][0]
        assert "cm.country = 'USA'" in query

    def test_get_series_list_returns_list_of_strings(self):
        """Test that get_series_list returns a list of series names"""
        # Arrange
        mock_db = Mock()
        repository = SQLInventoryRepository(mock_db)
        mock_db.execute_query_all.return_value = [
            {'series': 'Morgan Silver Dollars'},
            {'series': 'Peace Silver Dollars'},
            {'series': 'Walking Liberty Half Dollars'}
        ]
        
        # Act
        result = repository.get_series_list()
        
        # Assert
        expected = ['Morgan Silver Dollars', 'Peace Silver Dollars', 'Walking Liberty Half Dollars']
        assert result == expected
        mock_db.execute_query_all.assert_called_once()

    def test_get_countries_with_inventory_returns_list_of_strings(self):
        """Test that get_countries_with_inventory returns country list"""
        # Arrange
        mock_db = Mock()
        repository = SQLInventoryRepository(mock_db)
        mock_db.execute_query_all.return_value = [
            {'country': 'USA'},
            {'country': 'Canada'},
            {'country': 'Mexico'}
        ]
        
        # Act
        result = repository.get_countries_with_inventory()
        
        # Assert
        expected = ['USA', 'Canada', 'Mexico']
        assert result == expected
        
        # Verify query filters for qty_remaining > 0
        query = mock_db.execute_query_all.call_args[0][0]
        assert 'qty_remaining > 0' in query
        assert 'DISTINCT' in query

    def test_get_series_list_for_country_with_country_filter(self):
        """Test series list filtered by country"""
        # Arrange
        mock_db = Mock()
        repository = SQLInventoryRepository(mock_db)
        mock_db.execute_query_all.return_value = [
            {'series': 'Morgan Silver Dollars'},
            {'series': 'Peace Silver Dollars'}
        ]
        
        # Act
        result = repository.get_series_list_for_country("USA")
        
        # Assert
        expected = ['Morgan Silver Dollars', 'Peace Silver Dollars']
        assert result == expected
        
        # Verify query has country parameter
        call_args = mock_db.execute_query_all.call_args
        query = call_args[0][0]
        params = call_args[0][1]
        assert 'cm.country = ?' in query
        assert params == ("USA",)

    @patch('pages.inventory_functions.execute_query_all')
    def test_get_series_list_for_country_without_filter(self, mock_execute):
        """Test series list without country filter"""
        # Arrange
        mock_execute.return_value = [
            {'series': 'Morgan Silver Dollars'},
            {'series': 'Canadian Maple Leafs'}
        ]
        
        # Act
        result = get_series_list_for_country(None)
        
        # Assert
        expected = ['Morgan Silver Dollars', 'Canadian Maple Leafs']
        assert result == expected
        
        # Verify query has no parameters
        call_args = mock_execute.call_args
        query = call_args[0][0]
        assert len(call_args[0]) == 1  # Only query, no params
        assert 'coin_master' in query


    @patch('infrastructure.database.repositories.inventory_repository.get_inventory_by_series_detail')
    def test_get_inventory_by_series_detail_structure(self, mock_helper):
        """Test the series detail query returns expected structure"""
        # Arrange
        mock_db = Mock()
        repository = SQLInventoryRepository(mock_db)
        mock_helper.return_value = [
            {
                'lot_id': 1,
                'series': 'Morgan Silver Dollars',
                'year': 1921,
                'mint_mark': 'D',
                'variety': '',
                'qty_remaining': 5,
                'unit_cost_usd': 25.00,
                'melt_unit_value': 20.50,
                'chosen_unit_value': 30.00,
                'lot_est_value': 150.00
            }
        ]
        
        # Act
        result = repository.get_inventory_by_series_detail("Morgan Silver Dollars")
        
        # Assert
        assert len(result) == 1
        assert isinstance(result[0], SeriesDetail)
        assert result[0].lot_id == 1
        assert result[0].series == 'Morgan Silver Dollars'
        assert result[0].year == 1921
        assert result[0].unit_cost_usd == 25.00

    @patch('infrastructure.database.repositories.inventory_repository.get_inventory_by_flags')  
    def test_get_inventory_by_flags_returns_dataclass(self, mock_helper):
        """Test flags query returns proper dataclass"""
        # Arrange
        mock_db = Mock()
        repository = SQLInventoryRepository(mock_db)
        mock_helper.return_value = [
            {
                'lot_id': 1,
                'series': 'Morgan Silver Dollars',
                'year': 1921,
                'mint_mark': 'D',
                'variety': '',
                'qty_remaining': 5,
                'unit_cost_usd': 25.00,
                'melt_unit_value': 20.50,
                'chosen_unit_value': 30.00,
                'lot_est_value': 150.00,
                'is_proof': False,
                'cert_number': None
            }
        ]
        
        # Act
        result = repository.get_inventory_by_flags(want_proofs=False, want_slabbed=False)
        
        # Assert
        assert len(result) == 1
        assert isinstance(result[0], FlaggedInventory)
        assert result[0].lot_id == 1
        assert result[0].is_proof is False
        assert result[0].cert_number is None


class TestInventoryComponents:
    """Test the UI components work correctly with the repository"""
    
    def test_inventory_renderer_initialization(self):
        """Test that InventoryRenderer initializes with repository"""
        from presentation.components.inventory_components import InventoryRenderer
        
        mock_repo = Mock()
        renderer = InventoryRenderer(mock_repo)
        
        assert renderer.repo == mock_repo

    def test_convert_series_data_to_dataframe(self):
        """Test data conversion to DataFrame"""
        from presentation.components.inventory_components import InventoryRenderer
        
        mock_repo = Mock()
        renderer = InventoryRenderer(mock_repo)
        
        series_data = [
            InventoryBySeries(
                series='Morgan Silver Dollars',
                country='USA',
                coins=10,
                est_value_usd=250.50
            )
        ]
        
        df = renderer._convert_series_data_to_dataframe(series_data, "All")
        
        assert len(df) == 1
        assert 'Series' in df.columns
        assert 'Country' in df.columns
        assert df.iloc[0]['Series'] == 'Morgan Silver Dollars'
        assert df.iloc[0]['Coins'] == 10


if __name__ == "__main__":
    # Simple test runner
    print("Running Inventory Repository Tests...")
    
    try:
        # Run the basic tests manually
        test_repo = TestInventoryRepository()
        test_repo.test_get_inventory_by_type_returns_expected_structure()
        test_repo.test_get_series_list_returns_list_of_strings()
        test_repo.test_get_countries_with_inventory_returns_list_of_strings()
        
        test_components = TestInventoryComponents()
        test_components.test_inventory_renderer_initialization()
        
        print("✅ All tests passed!")
        
    except Exception as e:
        print(f"❌ Tests failed: {e}")
        raise
