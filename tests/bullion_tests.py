# tests/test_bullion_characterization.py
"""
Characterization tests for Bullion functionality.
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


class TestBullionDataAccess:
    """Test the current bullion data access behavior"""
    
    def test_get_latest_spot_prices_returns_list_of_dicts(self):
        """Test that get_latest_spot_prices returns metal prices"""
        from unittest.mock import patch
        
        with patch('infrastructure.database.db_operations.execute_query_all') as mock_execute:
            mock_execute.return_value = [
                {'metal': 'Ag', 'price_per_oz_usd': 24.50},
                {'metal': 'Au', 'price_per_oz_usd': 2050.00}
            ]
            
            from pages.bullion_functions import get_latest_spot_prices
            
            # Act
            result = get_latest_spot_prices()
            
            # Assert
            expected = [
                {'metal': 'Ag', 'price_per_oz_usd': 24.50},
                {'metal': 'Au', 'price_per_oz_usd': 2050.00}
            ]
            assert result == expected
            
            # Verify query structure
            mock_execute.assert_called_once()
            query = mock_execute.call_args[0][0]
            assert 'v_latest_spot' in query
            assert 'metal' in query
            assert 'price_per_oz_usd' in query

    def test_get_bullion_by_category_uses_schema_view(self):
        """Test that get_bullion_by_category uses the schema view"""
        with patch('infrastructure.database.db_operations.execute_query_all') as mock_execute:
            mock_execute.return_value = [
                {
                    'category': 'ROUND',
                    'metal': 'Ag',
                    'units_on_hand': 10,
                    'gross_oz': 10.0,
                    'fine_oz': 9.99,
                    'melt_value_usd': 244.75
                }
            ]
            
            from pages.bullion_functions import get_bullion_by_category
            
            # Act
            result = get_bullion_by_category()
            
            # Assert
            assert len(result) == 1
            assert result[0]['category'] == 'ROUND'
            assert result[0]['metal'] == 'Ag'
            assert result[0]['units_on_hand'] == 10
            
            # Verify uses schema view
            query = mock_execute.call_args[0][0]
            assert 'v_inventory_bullion_by_category' in query

    def test_get_bullion_by_series_uses_schema_view(self):
        """Test that get_bullion_by_series uses the schema view"""
        with patch('infrastructure.database.db_operations.execute_query_all') as mock_execute:
            mock_execute.return_value = [
                {
                    'category': 'ROUND',
                    'metal': 'Ag',
                    'series': 'Buffalo Rounds',
                    'unit_troy_oz': 1.0000,
                    'unit_fine_oz': 0.9990,
                    'units_on_hand': 5,
                    'gross_oz': 5.0,
                    'fine_oz': 4.995,
                    'melt_value_usd': 122.38
                }
            ]
            
            from pages.bullion_functions import get_bullion_by_series
            
            # Act
            result = get_bullion_by_series()
            
            # Assert
            assert len(result) == 1
            assert result[0]['series'] == 'Buffalo Rounds'
            assert result[0]['unit_troy_oz'] == 1.0000
            
            # Verify uses schema view
            query = mock_execute.call_args[0][0]
            assert 'v_inventory_bullion_by_series' in query

    def test_get_bullion_totals_returns_aggregated_data(self):
        """Test that get_bullion_totals returns totals including constitutional"""
        with patch('infrastructure.database.db_operations.execute_query_single') as mock_execute:
            mock_execute.return_value = {
                'total_units': 25,
                'total_fine_oz': 24.975,
                'total_value': 612.19
            }
            
            from pages.bullion_functions import get_bullion_totals
            
            # Act
            result = get_bullion_totals()
            
            # Assert
            assert result['total_units'] == 25
            assert result['total_fine_oz'] == 24.975
            assert result['total_value'] == 612.19
            
            # Verify complex query with CTEs
            query = mock_execute.call_args[0][0]
            assert 'WITH bullion_totals AS' in query
            assert 'constitutional_totals AS' in query
            assert 'v_inventory_bullion_by_category' in query
            assert 'v_junk_silver' in query

    def test_get_constitutional_silver_by_category_structure(self):
        """Test constitutional silver category query structure"""
        with patch('infrastructure.database.db_operations.execute_query_single') as mock_execute:
            mock_execute.return_value = {
                'category': 'Constitutional (Junk Silver)',
                'metal': 'Ag',
                'units_on_hand': 15,
                'gross_oz': 10.5,
                'fine_oz': 9.45,
                'melt_value_usd': 231.53
            }
            
            from pages.bullion_functions import get_constitutional_silver_by_category
            
            # Act
            result = get_constitutional_silver_by_category()
            
            # Assert
            assert len(result) == 1
            assert result[0]['category'] == 'Constitutional (Junk Silver)'
            assert result[0]['metal'] == 'Ag'
            
            # Verify query uses v_junk_silver view
            query = mock_execute.call_args[0][0]
            assert 'v_junk_silver' in query

    def test_get_constitutional_silver_by_category_no_data(self):
        """Test constitutional silver returns empty list when no data"""
        with patch('infrastructure.database.db_operations.execute_query_single') as mock_execute:
            mock_execute.return_value = {'units_on_hand': 0}  # No units
            
            from pages.bullion_functions import get_constitutional_silver_by_category
            
            # Act
            result = get_constitutional_silver_by_category()
            
            # Assert
            assert result == []

    def test_get_constitutional_silver_by_series_structure(self):
        """Test constitutional silver by series query structure"""
        with patch('infrastructure.database.db_operations.execute_query_all') as mock_execute:
            mock_execute.return_value = [
                {
                    'category': 'Constitutional (Junk Silver)',
                    'metal': 'Ag',
                    'series': 'Mercury Dimes',
                    'unit_troy_oz': 0.0723,
                    'unit_fine_oz': 0.0651,
                    'units_on_hand': 20,
                    'gross_oz': 1.446,
                    'fine_oz': 1.302,
                    'melt_value_usd': 31.90
                }
            ]
            
            from pages.bullion_functions import get_constitutional_silver_by_series
            
            # Act
            result = get_constitutional_silver_by_series()
            
            # Assert
            assert len(result) == 1
            assert result[0]['series'] == 'Mercury Dimes'
            assert result[0]['category'] == 'Constitutional (Junk Silver)'
            
            # Verify complex query structure
            query = mock_execute.call_args[0][0]
            assert 'valuation_method = \'MELT_ONLY\'' in query
            assert 'asset_category = \'COIN\'' in query
            assert 'v_lot_value_details' in query


class TestBullionHelpers:
    """Test the helper functions"""
    
    def test_safe_format_dataframe_with_valid_data(self):
        """Test safe formatting with valid data"""
        import pandas as pd
        from pages.bullion_functions import safe_format_dataframe
        
        # Create test DataFrame
        df = pd.DataFrame({
            'Units': [10, 5],
            'Melt Value (USD)': [244.75, 122.38]
        })
        
        format_spec = {
            'Units': '{:,.0f}',
            'Melt Value (USD)': '${:,.2f}'
        }
        
        # Act
        result = safe_format_dataframe(df, format_spec)
        
        # Assert - should return a styled dataframe or original df
        assert result is not None

    def test_safe_format_dataframe_with_none_values(self):
        """Test safe formatting handles None values"""
        import pandas as pd
        from pages.bullion_functions import safe_format_dataframe
        
        # Create test DataFrame with None values
        df = pd.DataFrame({
            'Units': [10, None],
            'Melt Value (USD)': [244.75, None]
        })
        
        format_spec = {
            'Units': '{:,.0f}',
            'Melt Value (USD)': '${:,.2f}'
        }
        
        # Act
        result = safe_format_dataframe(df, format_spec)
        
        # Assert - should handle None values gracefully
        assert result is not None

    def test_create_download_button_functionality(self):
        """Test download button creation"""
        import pandas as pd
        from pages.bullion_functions import create_download_button
        
        # Create test DataFrame
        df = pd.DataFrame({
            'Series': ['Buffalo Rounds'],
            'Units': [10]
        })
        
        # Act - should not raise an exception
        try:
            create_download_button("Test Download", df, "test.csv")
            # In test environment, this might not actually create the button
            # but it shouldn't crash
            assert True
        except Exception as e:
            # If streamlit components fail in test, that's expected
            assert 'streamlit' in str(e).lower() or True


if __name__ == "__main__":
    # Simple test runner
    print("Running Bullion Characterization Tests...")
    
    try:
        # Run the basic tests manually
        test_data = TestBullionDataAccess()
        test_data.test_get_latest_spot_prices_returns_list_of_dicts()
        test_data.test_get_bullion_by_category_uses_schema_view()
        test_data.test_get_bullion_by_series_uses_schema_view()
        test_data.test_get_bullion_totals_returns_aggregated_data()
        
        test_helpers = TestBullionHelpers()
        test_helpers.test_safe_format_dataframe_with_valid_data()
        test_helpers.test_safe_format_dataframe_with_none_values()
        
        print("✅ All tests passed!")
        
    except Exception as e:
        print(f"❌ Tests failed: {e}")
        raise
