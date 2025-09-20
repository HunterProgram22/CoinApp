# tests/test_coin_catalog_characterization.py
"""
Characterization tests for Coin Catalog functionality.
These tests capture the current behavior before and after refactoring.
"""
import pytest
from unittest.mock import patch, MagicMock, Mock
import sys
import os
import pandas as pd

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock streamlit before importing any modules that use it
sys.modules['streamlit'] = MagicMock()

# Import the refactored repository (if it exists)
try:
    from infrastructure.database.repositories.coin_catalog_repository import (
        CoinCatalogRepository
    )
    from presentation.components.coin_catalog_components import (
        CoinCatalogRenderer
    )

    REFACTORED_AVAILABLE = True
except ImportError:
    REFACTORED_AVAILABLE = False


class TestCoinCatalogRepository:
    """Test the coin catalog repository behavior"""

    @pytest.mark.skipif(not REFACTORED_AVAILABLE, reason="Refactored repository not available yet")
    def test_get_distinct_values_returns_expected_structure(self):
        """Test that get_distinct_values returns expected data structure"""
        # Arrange
        repository = CoinCatalogRepository()

        with patch('infrastructure.database.db_operations.execute_query_all') as mock_execute:
            mock_execute.return_value = [
                {'value': 'United States'},
                {'value': 'Canada'},
                {'value': 'United Kingdom'},
                {'value': None}  # Should be filtered out
            ]

            # Act
            result = repository.get_distinct_values("country")

            # Assert
            assert len(result) == 3
            assert result == ['United States', 'Canada', 'United Kingdom']
            assert None not in result

            # Verify query structure
            mock_execute.assert_called_once()
            called_args = mock_execute.call_args[0]
            query = called_args[0]
            assert 'SELECT DISTINCT country AS value' in query
            assert 'FROM coin_master' in query
            assert 'ORDER BY value' in query

    @pytest.mark.skipif(not REFACTORED_AVAILABLE, reason="Refactored repository not available yet")
    def test_get_distinct_values_with_filter(self):
        """Test get_distinct_values with filter parameters"""
        repository = CoinCatalogRepository()

        with patch('infrastructure.database.db_operations.execute_query_all') as mock_execute:
            mock_execute.return_value = [
                {'value': 'Dollar'},
                {'value': 'Half Dollar'}
            ]

            # Act
            result = repository.get_distinct_values("denomination", "coin_master", "country",
                                                    "United States")

            # Assert
            assert result == ['Dollar', 'Half Dollar']

            # Verify filter was applied
            call_args = mock_execute.call_args
            assert "WHERE country = ?" in call_args[0][0]
            assert call_args[0][1] == ("United States",)

    @pytest.mark.skipif(not REFACTORED_AVAILABLE, reason="Refactored repository not available yet")
    def test_search_coin_masters_with_country(self):
        """Test search_coin_masters with country filter"""
        repository = CoinCatalogRepository()

        with patch('infrastructure.database.db_operations.execute_query_all') as mock_execute:
            mock_execute.return_value = [
                {
                    'id': 1,
                    'country': 'United States',
                    'denomination': 'Dollar',
                    'series': 'Morgan',
                    'years_start': 1878,
                    'years_end': 1921,
                    'metal': 'Silver',
                    'fineness': 0.9000,
                    'weight_grams': 26.73,
                    'asset_category': 'Numismatic',
                    'numista_url': 'http://numista.com/1',
                    'ngc_url': 'http://ngc.com/1',
                    'pcgs_url': 'http://pcgs.com/1'
                }
            ]

            # Act
            result = repository.search_coin_masters(country="United States")

            # Assert
            assert len(result) == 1
            assert result[0]['country'] == 'United States'
            assert result[0]['series'] == 'Morgan'

            # Verify database was called with correct parameters
            mock_execute.assert_called_once()
            call_args = mock_execute.call_args
            assert "WHERE country = ?" in call_args[0][0]
            assert call_args[0][1] == ("United States",)

    @pytest.mark.skipif(not REFACTORED_AVAILABLE, reason="Refactored repository not available yet")
    def test_search_coin_masters_no_country_returns_empty(self):
        """Test search_coin_masters returns empty list when no country provided"""
        repository = CoinCatalogRepository()

        with patch('infrastructure.database.db_operations.execute_query_all') as mock_execute:
            # Act
            result = repository.search_coin_masters()

            # Assert
            assert result == []
            # Should not call database
            mock_execute.assert_not_called()

    @pytest.mark.skipif(not REFACTORED_AVAILABLE, reason="Refactored repository not available yet")
    def test_search_coin_types_with_both_parameters(self):
        """Test search_coin_types with both country and series"""
        repository = CoinCatalogRepository()

        with patch('infrastructure.database.db_operations.execute_query_all') as mock_execute:
            mock_execute.return_value = [
                {
                    'id': 1,
                    'denomination': 'Dollar',
                    'series': 'Morgan',
                    'year': 1878,
                    'mint_mark': 'S',
                    'variety': '',
                    'mintage': 9774000,
                    'is_proof': 0
                }
            ]

            # Act
            result = repository.search_coin_types(country="United States", series="Morgan")

            # Assert
            assert len(result) == 1
            assert result[0]['series'] == 'Morgan'
            assert result[0]['year'] == 1878

            # Verify database was called with both filters
            mock_execute.assert_called_once()
            call_args = mock_execute.call_args
            query = call_args[0][0]
            params = call_args[0][1]

            assert "WHERE cm.country = ?" in query
            assert "AND cm.series = ?" in query
            assert params == ("United States", "Morgan")

    @pytest.mark.skipif(not REFACTORED_AVAILABLE, reason="Refactored repository not available yet")
    def test_search_coin_types_missing_parameters_returns_empty(self):
        """Test search_coin_types returns empty list when parameters missing"""
        repository = CoinCatalogRepository()

        with patch('infrastructure.database.db_operations.execute_query_all') as mock_execute:
            # Test with no parameters
            result = repository.search_coin_types()
            assert result == []

            # Test with only country
            result = repository.search_coin_types(country="United States")
            assert result == []

            # Test with only series
            result = repository.search_coin_types(series="Morgan")
            assert result == []

            # Should not call database in any case
            mock_execute.assert_not_called()


class TestCoinCatalogComponents:
    """Test the UI components work correctly with the repository"""

    @pytest.mark.skipif(not REFACTORED_AVAILABLE, reason="Refactored components not available yet")
    def test_coin_catalog_renderer_initialization(self):
        """Test that CoinCatalogRenderer initializes with repository"""
        mock_repo = Mock()
        renderer = CoinCatalogRenderer(mock_repo)

        assert renderer.repository == mock_repo

    @pytest.mark.skipif(not REFACTORED_AVAILABLE, reason="Refactored components not available yet")
    def test_renderer_has_expected_methods(self):
        """Test that renderer has all expected methods"""
        mock_repo = Mock()
        renderer = CoinCatalogRenderer(mock_repo)

        # Test that renderer has key methods
        assert hasattr(renderer, 'render_master_filters')
        assert hasattr(renderer, 'render_master_results')
        assert hasattr(renderer, 'render_types_filters')
        assert hasattr(renderer, 'render_types_results')
        assert hasattr(renderer, 'render_coin_catalog_page')


class TestOriginalCoinCatalogFunctions:
    """Test the original functions from the page before refactoring"""

    def test_original_functions_work(self):
        """Test that the original functions can be called and return expected types"""

        # Test original functions with mocked database
        with patch('infrastructure.database.db_operations.execute_query_all') as mock_execute:
            mock_execute.return_value = [
                {'value': 'United States'},
                {'value': 'Canada'}
            ]

            # Import the original functions
            try:
                from pages.coin_catalog_functions import (
                    get_distinct_values,
                    get_countries_for_coin_types,
                    get_series_for_country,
                    search_coin_masters,
                    search_coin_types
                )

                # Test functions are callable
                assert callable(get_distinct_values)
                assert callable(get_countries_for_coin_types)
                assert callable(get_series_for_country)
                assert callable(search_coin_masters)
                assert callable(search_coin_types)

                # Test actual calls
                result = get_distinct_values("country")
                assert isinstance(result, list)
                assert len(result) == 2
                assert result == ['United States', 'Canada']

            except ImportError:
                # Functions file doesn't exist yet - this is expected before extraction
                pytest.skip("Original functions file not created yet")

    def test_format_year_range_function(self):
        """Test year range formatting with various inputs"""

        try:
            from pages.coin_catalog_functions import format_year_range

            # Test with both values
            row = {"years_start": 1878, "years_end": 1921}
            result = format_year_range(row)
            assert result == "1878–1921"

            # Test with start only
            row = {"years_start": 1878, "years_end": None}
            result = format_year_range(row)
            assert result == "1878–"

            # Test with end only
            row = {"years_start": None, "years_end": 1921}
            result = format_year_range(row)
            assert result == "–1921"

            # Test with no values
            row = {"years_start": None, "years_end": None}
            result = format_year_range(row)
            assert result == ""

        except ImportError:
            pytest.skip("Original functions file not created yet")

    def test_prepare_dataframe_functions(self):
        """Test dataframe preparation functions"""

        try:
            from pages.coin_catalog_functions import (
                prepare_master_display_dataframe,
                prepare_types_display_dataframe
            )

            # Test master dataframe preparation
            df = pd.DataFrame([
                {
                    'country': 'United States',
                    'denomination': 'Dollar',
                    'series': 'Morgan',
                    'years_start': 1878,
                    'years_end': 1921,
                    'asset_category': 'Numismatic',
                    'metal': 'Silver',
                    'fineness': 0.9000,
                    'weight_grams': 26.73,
                    'numista_url': 'http://numista.com/1',
                    'ngc_url': 'http://ngc.com/1',
                    'pcgs_url': 'http://pcgs.com/1'
                }
            ])

            result = prepare_master_display_dataframe(df)

            # Check that Years column was added
            assert 'Years' in result.columns
            assert result.iloc[0]['Years'] == '1878–1921'

            # Check column renaming
            expected_columns = ['Country', 'Denomination', 'Series', 'Years',
                                'Category', 'Metal', 'Fineness', 'Wt (g)',
                                'Numista', 'NGC', 'PCGS']
            for col in expected_columns:
                assert col in result.columns

        except ImportError:
            pytest.skip("Original functions file not created yet")


if __name__ == "__main__":
    # Simple test runner
    print("Running Coin Catalog Repository Tests...")

    try:
        if REFACTORED_AVAILABLE:
            # Run the refactored tests
            test_repo = TestCoinCatalogRepository()
            test_repo.test_get_distinct_values_returns_expected_structure()
            test_repo.test_search_coin_masters_with_country()
            test_repo.test_search_coin_types_with_both_parameters()

            test_components = TestCoinCatalogComponents()
            test_components.test_coin_catalog_renderer_initialization()

            print("✅ Refactored repository and components tests passed!")
        else:
            print("⭐ Skipping refactored tests - not created yet")

        # Test original functions
        test_original = TestOriginalCoinCatalogFunctions()
        test_original.test_original_functions_work()
        test_original.test_format_year_range_function()

        print("✅ All available tests passed!")

    except Exception as e:
        print(f"❌ Tests failed: {e}")
        import traceback

        traceback.print_exc()
        raise

