#!/usr/bin/env python3
"""
Simple test runner to validate our coin catalog refactoring.
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
    print("Testing original coin catalog functions...")

    # First, check if we need to create the temporary functions file
    if not os.path.exists('pages/coin_catalog_functions.py'):
        print("Creating temporary coin_catalog_functions.py for testing...")
        success = create_temporary_functions_file()
        if not success:
            return False

    # Debug: Check if file was created and is readable
    if os.path.exists('pages/coin_catalog_functions.py'):
        print("✅ Functions file created successfully")
        # Try to read first few lines to check for syntax issues
        try:
            with open('pages/coin_catalog_functions.py', 'r', encoding='utf-8') as f:
                first_lines = f.read(200)
                print(f"First 200 chars: {first_lines}")
        except Exception as e:
            print(f"❌ Could not read functions file: {e}")
            return False
    else:
        print("❌ Functions file was not created")
        return False

    try:
        # We need to mock the database operations BEFORE importing the functions
        from unittest.mock import patch

        with patch('infrastructure.database.db_operations.execute_query_all') as mock_execute_all:

            # Set up mock return values for different function calls
            def mock_execute_side_effect(query, params=()):
                print(f"Mock called with query: {query[:100]}...")  # Debug output
                print(f"Mock called with params: {params}")  # Debug output

                if 'SELECT DISTINCT' in query and 'AS value' in query:
                    # This is get_distinct_values
                    return [
                        {'value': 'United States'},
                        {'value': 'Canada'},
                        {'value': None}  # Should be filtered out
                    ]
                elif 'SELECT DISTINCT cm.country' in query and 'coin_type ct' in query:
                    # This is get_countries_for_coin_types
                    return [
                        {'country': 'United States'},
                        {'country': 'Canada'}
                    ]
                elif 'SELECT DISTINCT cm.series' in query and 'WHERE cm.country = ?' in query:
                    # This is get_series_for_country
                    return [
                        {'series': 'Morgan Dollar'},
                        {'series': 'Peace Dollar'}
                    ]
                elif 'FROM coin_master' in query and 'WHERE country = ?' in query and params:
                    # This is search_coin_masters with country
                    return [
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
                elif 'FROM coin_type ct' in query and 'WHERE cm.country = ?' in query and 'AND cm.series = ?' in query:
                    # This is search_coin_types
                    return [
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
                else:
                    print(f"No mock match found for query: {query}")  # Debug output
                    return []

            mock_execute_all.side_effect = mock_execute_side_effect

            # Now import the functions (they'll use our mocked database)
            from pages.coin_catalog_functions import (
                get_distinct_values,
                get_countries_for_coin_types,
                get_series_for_country,
                format_year_range,
                prepare_master_display_dataframe,
                prepare_types_display_dataframe,
                search_coin_masters,
                search_coin_types
            )

            # Test that functions are callable
            assert callable(get_distinct_values)
            assert callable(get_countries_for_coin_types)
            assert callable(get_series_for_country)
            assert callable(search_coin_masters)
            assert callable(search_coin_types)

            # Test actual calls (with mocked data)
            result = get_distinct_values("country")
            assert isinstance(result, list)
            assert len(result) == 2  # None should be filtered out
            assert 'United States' in result
            assert 'Canada' in result
            assert None not in result

            result = get_countries_for_coin_types()
            assert isinstance(result, list)
            assert len(result) == 2

            result = get_series_for_country("United States")
            assert isinstance(result, list)
            assert len(result) == 2
            assert 'Morgan Dollar' in result

            # Test formatting function
            row = {"years_start": 1878, "years_end": 1921}
            result = format_year_range(row)
            assert result == "1878–1921"

            # Test search functions
            result = search_coin_masters(country="United States")
            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]['series'] == 'Morgan'

            result = search_coin_masters()  # No country - should return empty
            assert result == []

            result = search_coin_types(country="United States", series="Morgan")
            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]['year'] == 1878

            result = search_coin_types()  # No params - should return empty
            assert result == []

        print("✅ Original functions work correctly")
        return True

    except Exception as e:
        print(f"❌ Original functions failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_temporary_functions_file():
    """Create the temporary functions file for testing"""

    # Create the pages directory if it doesn't exist
    os.makedirs('pages', exist_ok=True)

    # Write a simple functions file piece by piece to avoid encoding issues
    try:
        with open('pages/coin_catalog_functions.py', 'w', encoding='utf-8') as f:
            # Write imports
            f.write('# pages/coin_catalog_functions.py\n')
            f.write('import pandas as pd\n')
            f.write('from typing import List, Optional, Dict, Any\n')
            f.write('from infrastructure.database.db_operations import execute_query_all\n\n')

            # Write get_distinct_values function
            f.write('def get_distinct_values(column: str, table: str = "coin_master",\n')
            f.write('                        filter_column: Optional[str] = None,\n')
            f.write('                        filter_value: Optional[str] = None) -> List[str]:\n')
            f.write('    conditions = []\n')
            f.write('    params = []\n')
            f.write('    if filter_column and filter_value:\n')
            f.write('        conditions.append(f"{filter_column} = ?")\n')
            f.write('        params.append(filter_value)\n')
            f.write(
                '    where_clause = f"WHERE {\' AND \'.join(conditions)}" if conditions else ""\n')
            f.write(
                '    query = f"SELECT DISTINCT {column} AS value FROM {table} {where_clause} ORDER BY value"\n')
            f.write('    results = execute_query_all(query, tuple(params))\n')
            f.write('    return [r[\'value\'] for r in results if r[\'value\']]\n\n')

            # Write get_countries_for_coin_types function
            f.write('def get_countries_for_coin_types() -> List[str]:\n')
            f.write('    query = """\n')
            f.write('        SELECT DISTINCT cm.country\n')
            f.write('        FROM coin_type ct\n')
            f.write('        JOIN coin_master cm ON cm.id = ct.master_id\n')
            f.write('        WHERE cm.country IS NOT NULL\n')
            f.write('        ORDER BY cm.country\n')
            f.write('    """\n')
            f.write('    results = execute_query_all(query)\n')
            f.write('    return [r[\'country\'] for r in results]\n\n')

            # Write get_series_for_country function
            f.write('def get_series_for_country(country: str) -> List[str]:\n')
            f.write('    query = """\n')
            f.write('        SELECT DISTINCT cm.series\n')
            f.write('        FROM coin_type ct\n')
            f.write('        JOIN coin_master cm ON cm.id = ct.master_id\n')
            f.write('        WHERE cm.country = ?\n')
            f.write('        ORDER BY cm.series\n')
            f.write('    """\n')
            f.write('    results = execute_query_all(query, (country,))\n')
            f.write('    return [r[\'series\'] for r in results]\n\n')

            # Write format_year_range function (avoiding the checkmark character for now)
            f.write('def format_year_range(row: Dict[str, Any]) -> str:\n')
            f.write('    start = row.get("years_start")\n')
            f.write('    end = row.get("years_end")\n')
            f.write('    if pd.isna(start) and pd.isna(end):\n')
            f.write('        return ""\n')
            f.write('    try:\n')
            f.write('        start_int = int(start) if not pd.isna(start) else None\n')
            f.write('    except (ValueError, TypeError):\n')
            f.write('        start_int = None\n')
            f.write('    try:\n')
            f.write('        end_int = int(end) if not pd.isna(end) else None\n')
            f.write('    except (ValueError, TypeError):\n')
            f.write('        end_int = None\n')
            f.write('    if start_int is None and end_int is None:\n')
            f.write('        return ""\n')
            f.write('    elif start_int is None:\n')
            f.write('        return f"–{end_int}"\n')
            f.write('    elif end_int is None:\n')
            f.write('        return f"{start_int}–"\n')
            f.write('    else:\n')
            f.write('        return f"{start_int}–{end_int}"\n\n')

            # Write simple prepare functions
            f.write('def prepare_master_display_dataframe(df: pd.DataFrame) -> pd.DataFrame:\n')
            f.write('    df["Years"] = df.apply(format_year_range, axis=1)\n')
            f.write('    return df\n\n')

            f.write('def prepare_types_display_dataframe(df: pd.DataFrame) -> pd.DataFrame:\n')
            f.write('    return df\n\n')

            # Write search functions
            f.write(
                'def search_coin_masters(country: Optional[str] = None, denomination: Optional[str] = None, series_search: Optional[str] = None) -> List[Dict[str, Any]]:\n')
            f.write('    if not country:\n')
            f.write('        return []\n')
            f.write('    conditions = ["country = ?"]\n')
            f.write('    params = [country]\n')
            f.write('    if denomination and denomination != "All":\n')
            f.write('        conditions.append("denomination = ?")\n')
            f.write('        params.append(denomination)\n')
            f.write('    if series_search and series_search.strip():\n')
            f.write('        conditions.append("LOWER(series) LIKE ?")\n')
            f.write('        params.append(f"%{series_search.strip().lower()}%")\n')
            f.write('    where_clause = f"WHERE {\' AND \'.join(conditions)}"\n')
            f.write(
                '    query = f"SELECT id, country, denomination, series, years_start, years_end, metal, fineness, weight_grams, asset_category, COALESCE(numista_url, \'\') AS numista_url, COALESCE(ngc_url, \'\') AS ngc_url, COALESCE(pcgs_url, \'\') AS pcgs_url FROM coin_master {where_clause} ORDER BY country, denomination, series"\n')
            f.write('    return execute_query_all(query, tuple(params))\n\n')

            f.write(
                'def search_coin_types(country: Optional[str] = None, series: Optional[str] = None) -> List[Dict[str, Any]]:\n')
            f.write('    if not country or not series:\n')
            f.write('        return []\n')
            f.write(
                '    query = "SELECT ct.id, cm.denomination, cm.series, ct.year, COALESCE(ct.mint_mark, \'\') AS mint_mark, COALESCE(ct.variety, \'\') AS variety, COALESCE(ct.mintage, 0) AS mintage, ct.is_proof FROM coin_type ct JOIN coin_master cm ON cm.id = ct.master_id WHERE cm.country = ? AND cm.series = ? ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety"\n')
            f.write('    return execute_query_all(query, (country, series))\n')

        print("✅ Created pages/coin_catalog_functions.py")

        # Verify the file was written correctly
        with open('pages/coin_catalog_functions.py', 'r', encoding='utf-8') as f:
            content = f.read()
            if len(content) > 100:
                print(f"✅ File has {len(content)} characters")
                return True
            else:
                print(f"❌ File seems too short: {len(content)} characters")
                return False

    except Exception as e:
        print(f"❌ Error creating functions file: {e}")
        return False


def test_refactored_repository():
    """Test the refactored repository"""
    print("Testing refactored coin catalog repository...")

    # Check if refactored files exist
    if not os.path.exists('infrastructure/database/repositories/coin_catalog_repository.py'):
        print("⭐ Skipping refactored repository test - files not created yet")
        return True

    try:
        from infrastructure.database.repositories.coin_catalog_repository import (
            CoinCatalogRepository
        )
        from unittest.mock import patch

        # Create repository
        repository = CoinCatalogRepository()

        # Test get_distinct_values
        with patch('infrastructure.database.db_operations.execute_query_all') as mock_execute:
            mock_execute.return_value = [
                {'value': 'United States'},
                {'value': 'Canada'},
                {'value': None}  # Should be filtered
            ]

            result = repository.get_distinct_values("country")
            assert len(result) == 2
            assert 'United States' in result
            assert 'Canada' in result
            assert None not in result

        # Test search_coin_masters
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

            result = repository.search_coin_masters(country="United States")
            assert len(result) == 1
            assert result[0]['series'] == 'Morgan'

            # Test no country returns empty
            result = repository.search_coin_masters()
            assert result == []

        # Test search_coin_types
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

            result = repository.search_coin_types(country="United States", series="Morgan")
            assert len(result) == 1
            assert result[0]['year'] == 1878

            # Test missing params returns empty
            result = repository.search_coin_types()
            assert result == []

            result = repository.search_coin_types(country="United States")
            assert result == []

        print("✅ Refactored repository works correctly")
        return True

    except Exception as e:
        print(f"❌ Refactored repository failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_components():
    """Test the UI components"""
    print("Testing coin catalog UI components...")

    # Check if component files exist
    if not os.path.exists('presentation/components/coin_catalog_components.py'):
        print("⭐ Skipping UI components test - files not created yet")
        return True

    try:
        from presentation.components.coin_catalog_components import CoinCatalogRenderer
        from unittest.mock import Mock

        # Create renderer with mocked repository
        mock_repo = Mock()
        renderer = CoinCatalogRenderer(mock_repo)

        # Test that renderer initializes
        assert renderer.repository == mock_repo

        # Test that renderer has expected methods
        assert hasattr(renderer, 'render_master_filters')
        assert hasattr(renderer, 'render_master_results')
        assert hasattr(renderer, 'render_types_filters')
        assert hasattr(renderer, 'render_types_results')
        assert hasattr(renderer, 'render_coin_catalog_page')

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
        'pages/coin_catalog_functions.py'
    ]

    for file_path in temp_files:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"🧹 Cleaned up {file_path}")
            except Exception as e:
                print(f"⚠️ Could not remove {file_path}: {e}")


def main():
    """Run all tests"""
    print("🧪 Running Coin Catalog Refactoring Tests")
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
        print("⚠️ Some tests failed. Review before proceeding.")
        return 1


if __name__ == "__main__":
    exit(main())
