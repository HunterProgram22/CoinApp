# tests/test_world_coins_characterization.py
"""
Characterization tests for World Coins functionality.
These tests capture the current behavior before refactoring.
"""
import pytest
from unittest.mock import patch, MagicMock, Mock
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock streamlit before importing any modules that use it
sys.modules['streamlit'] = MagicMock()


class TestWorldCoinsDataAccess:
    """Test the current world coins data access behavior"""
    
    def test_get_countries_on_hand_returns_list_of_strings(self):
        """Test that get_countries_on_hand returns a list of country names"""
        # We need to mock the database operations BEFORE importing the functions
        from unittest.mock import patch
        
        with patch('infrastructure.database.db_operations.execute_query_all') as mock_execute:
            mock_execute.return_value = [
                {'country': 'Canada'},
                {'country': 'Mexico'},
                {'country': 'United Kingdom'}
            ]
            
            # Now import the function
            from pages.world_coins_functions import get_countries_on_hand
            
            # Act
            result = get_countries_on_hand()
            
            # Assert
            expected = ['Canada', 'Mexico', 'United Kingdom']
            assert result == expected
            
            # Verify query structure
            mock_execute.assert_called_once()
            query = mock_execute.call_args[0][0]
            assert 'DISTINCT' in query
            assert 'country' in query
            assert 'qty_remaining > 0' in query

    def test_check_asset_category_support_when_exists(self):
        """Test asset category check when column exists"""
        with patch('infrastructure.database.db_operations.execute_query_single') as mock_execute:
            mock_execute.return_value = {'1': 1}  # Column exists
            
            from pages.world_coins_functions import check_asset_category_support
            
            # Act
            result = check_asset_category_support()
            
            # Assert
            assert result is True
            mock_execute.assert_called_once()
            query = mock_execute.call_args[0][0]
            assert 'pragma_table_info' in query
            assert 'asset_category' in query

    def test_check_asset_category_support_when_not_exists(self):
        """Test asset category check when column doesn't exist"""
        with patch('infrastructure.database.db_operations.execute_query_single') as mock_execute:
            mock_execute.return_value = None  # Column doesn't exist
            
            from pages.world_coins_functions import check_asset_category_support
            
            # Act
            result = check_asset_category_support()
            
            # Assert
            assert result is False

    def test_get_world_coins_summary_with_view_exists(self):
        """Test world coins summary when view exists"""
        with patch('infrastructure.database.db_operations.execute_query_single') as mock_single, \
             patch('infrastructure.database.db_operations.execute_query_all') as mock_all:
            
            mock_single.return_value = {'1': 1}  # View exists
            mock_all.return_value = [
                {
                    'Series': 'Canadian Silver Maple Leafs',
                    'Coins': 10,
                    'Melt Value (USD)': 250.50,
                    'Est. Value (USD)': 300.00
                }
            ]
            
            from pages.world_coins_functions import get_world_coins_summary
            
            # Act
            result = get_world_coins_summary("Canada")
            
            # Assert
            assert len(result) == 1
            assert result[0]['Series'] == 'Canadian Silver Maple Leafs'
            assert result[0]['Coins'] == 10
            
            # Verify view check happened
            mock_single.assert_called_once()
            view_check_query = mock_single.call_args[0][0]
            assert 'v_lot_value_details' in view_check_query
            
            # Verify main query uses view
            main_query = mock_all.call_args[0][0]
            assert 'v_lot_value_details' in main_query

    def test_get_world_coins_summary_without_view(self):
        """Test world coins summary when view doesn't exist"""
        with patch('infrastructure.database.db_operations.execute_query_single') as mock_single, \
             patch('infrastructure.database.db_operations.execute_query_all') as mock_all:
            
            mock_single.return_value = None  # View doesn't exist
            mock_all.return_value = [
                {
                    'Series': 'Canadian Silver Maple Leafs',
                    'Coins': 10,
                    'Melt Value (USD)': None,
                    'Est. Value (USD)': None
                }
            ]
            
            from pages.world_coins_functions import get_world_coins_summary
            
            # Act
            result = get_world_coins_summary("Canada")
            
            # Assert
            assert len(result) == 1
            assert result[0]['Series'] == 'Canadian Silver Maple Leafs'
            assert result[0]['Melt Value (USD)'] is None
            
            # Verify fallback query doesn't use view
            main_query = mock_all.call_args[0][0]
            assert 'v_lot_value_details' not in main_query

    def test_get_world_coins_summary_with_filters(self):
        """Test world coins summary with various filters"""
        with patch('infrastructure.database.db_operations.execute_query_single') as mock_single, \
             patch('infrastructure.database.db_operations.execute_query_all') as mock_all:
            
            mock_single.return_value = {'1': 1}  # View exists
            mock_all.return_value = [
                {
                    'Series': 'Canadian Proof Set',
                    'Coins': 5,
                    'Melt Value (USD)': 100.00,
                    'Est. Value (USD)': 150.00
                }
            ]
            
            from pages.world_coins_functions import get_world_coins_summary
            
            # Act - test with all filters
            result = get_world_coins_summary(
                country="Canada",
                want_proofs=True,
                want_slabbed=True,
                asset_category="COIN"
            )
            
            # Assert
            assert len(result) == 1
            
            # Verify filters are applied in query
            call_args = mock_all.call_args
            query = call_args[0][0]
            params = call_args[0][1]
            
            assert 'cm.country = ?' in query
            assert 'ct.is_proof = 1' in query
            assert 'asset_category = ?' in query
            assert 'Canada' in params
            assert 'COIN' in params

    def test_get_world_coins_detail_structure(self):
        """Test world coins detail returns expected structure"""
        with patch('infrastructure.database.db_operations.execute_query_single') as mock_single, \
             patch('infrastructure.database.db_operations.execute_query_all') as mock_all:
            
            # Mock multiple single queries (specimen check, code check, sold check, view check)
            mock_single.side_effect = [
                {'1': 1},  # Specimen table exists
                {'1': 1},  # Specimen code column exists  
                {'1': 1},  # Sold line id column exists
                {'1': 1}   # View exists
            ]
            
            mock_all.return_value = [
                {
                    'Series': 'Canadian Silver Maple Leafs',
                    'Year': 2023,
                    'Mint Mark': '',
                    'Variety': '',
                    'lot_id': 1,
                    'Acquired': '2023-01-15',
                    'Party': 'APMEX',
                    'Qty': 1,
                    'Unit Cost (USD)': 35.50,
                    'Melt Unit Value': 32.45,
                    'Chosen Unit Value': 35.00,
                    'Lot Est. Value': 35.00,
                    'Grade': 'MS-69',
                    'Flip IDs': '001, 002',
                    'Cert #': 'NGC123456'
                }
            ]
            
            from pages.world_coins_functions import get_world_coins_detail
            
            # Act
            result = get_world_coins_detail("Canada")
            
            # Assert
            assert len(result) == 1
            assert result[0]['Series'] == 'Canadian Silver Maple Leafs'
            assert result[0]['Year'] == 2023
            assert result[0]['lot_id'] == 1
            
            # Verify multiple table checks happened
            assert mock_single.call_count == 4
            
            # Verify complex query structure
            query = mock_all.call_args[0][0]
            assert 'WITH flip AS' in query  # CTE for flip IDs
            assert 'LEFT JOIN v_lot_value_details' in query
            assert 'LEFT JOIN flip f' in query


class TestWorldCoinsHelpers:
    """Test the helper functions"""
    
    def test_format_year_columns_for_display(self):
        """Test year column formatting"""
        import pandas as pd
        from pages.world_coins_functions import format_year_columns_for_display
        
        # Create test DataFrame
        df = pd.DataFrame({
            'Year': [2023.0, float('nan'), 1985.0],
            'Series': ['Test1', 'Test2', 'Test3']
        })
        
        # Act
        result = format_year_columns_for_display(df)
        
        # Assert
        assert result['Year'].iloc[0] == '2023'
        assert result['Year'].iloc[1] == ''  # NaN should become empty string
        assert result['Year'].iloc[2] == '1985'

    def test_format_money_columns(self):
        """Test money column formatting"""
        import pandas as pd
        from pages.world_coins_functions import format_money_columns
        
        # Create test DataFrame
        df = pd.DataFrame({
            'Unit Cost (USD)': [25.50, 30.00],
            'Series': ['Test1', 'Test2']
        })
        
        # Act
        display_df, csv_df = format_money_columns(df, ['Unit Cost (USD)'])
        
        # Assert
        assert display_df['Unit Cost (USD)'].iloc[0] == '$25.50'
        assert csv_df['Unit Cost (USD)'].iloc[0] == 25.50  # CSV keeps numeric


if __name__ == "__main__":
    # Simple test runner
    print("Running World Coins Characterization Tests...")
    
    try:
        # Run the basic tests manually
        test_data = TestWorldCoinsDataAccess()
        test_data.test_get_countries_on_hand_returns_list_of_strings()
        test_data.test_check_asset_category_support_when_exists()
        test_data.test_check_asset_category_support_when_not_exists()
        
        test_helpers = TestWorldCoinsHelpers()
        test_helpers.test_format_year_columns_for_display()
        test_helpers.test_format_money_columns()
        
        print("✅ All tests passed!")
        
    except Exception as e:
        print(f"❌ Tests failed: {e}")
        raise
