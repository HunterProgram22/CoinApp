# run_coin_registry_tests.py
"""
Test runner for Coin Registry refactoring.
Run this before and after refactoring to ensure behavior is preserved.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath('.'))

# Mock streamlit before importing anything
from unittest.mock import MagicMock

sys.modules['streamlit'] = MagicMock()


def create_temporary_functions_file():
    """Create the temporary functions file for testing"""

    # First, remove any existing file to ensure clean slate
    if os.path.exists('pages/coin_registry_functions.py'):
        os.remove('pages/coin_registry_functions.py')
        print("Removed existing coin_registry_functions.py")

    # Create the pages directory if it doesn't exist
    os.makedirs('pages', exist_ok=True)

    # Write the file line by line to avoid encoding issues
    with open('pages/coin_registry_functions.py', 'w', encoding='ascii', errors='ignore') as f:
        f.write('# pages/coin_registry_functions.py\n')
        f.write('"""\n')
        f.write('Temporary extraction of coin registry functions for testing.\n')
        f.write('These will be moved to the repository during refactoring.\n')
        f.write('"""\n')
        f.write('from infrastructure.database.db_operations import (\n')
        f.write('    execute_query_all, execute_query_single,\n')
        f.write('    execute_insert, execute_update, execute_delete\n')
        f.write(')\n')
        f.write('from core.queries import (\n')
        f.write('    get_specimen_by_code,\n')
        f.write('    get_specimens_on_hand,\n')
        f.write('    create_specimens_for_lot,\n')
        f.write('    create_or_update_series_code,\n')
        f.write('    get_all_lots,\n')
        f.write(')\n')
        f.write('\n')
        f.write('\n')
        f.write('def get_slabbed_series_list():\n')
        f.write('    """Get list of series that have slabbed coins."""\n')
        f.write('    query = """\n')
        f.write('        SELECT DISTINCT cm.series\n')
        f.write('        FROM lot l\n')
        f.write('        JOIN coin_type ct ON ct.id = l.coin_type_id\n')
        f.write('        JOIN coin_master cm ON cm.id = ct.master_id\n')
        f.write('        WHERE l.qty_remaining > 0 \n')
        f.write('        AND l.slab_cert IS NOT NULL \n')
        f.write("        AND TRIM(l.slab_cert) != ''\n")
        f.write('        ORDER BY cm.series\n')
        f.write('    """\n')
        f.write('    results = execute_query_all(query)\n')
        f.write("    return [r['series'] for r in results]\n")
        f.write('\n')
        f.write('\n')
        f.write('def get_slabbed_coins_by_series(series=None):\n')
        f.write('    """Get all slabbed coins, optionally filtered by series."""\n')
        f.write('    conditions = [\n')
        f.write('        "l.qty_remaining > 0",\n')
        f.write('        "l.slab_cert IS NOT NULL",\n')
        f.write('        "TRIM(l.slab_cert) != \'\'"\n')
        f.write('    ]\n')
        f.write('    params = []\n')
        f.write('\n')
        f.write('    if series:\n')
        f.write('        conditions.append("cm.series = ?")\n')
        f.write('        params.append(series)\n')
        f.write('\n')
        f.write('    where_clause = " AND ".join(conditions)\n')
        f.write('\n')
        f.write('    query = f"""\n')
        f.write('        SELECT \n')
        f.write('            l.id as lot_id,\n')
        f.write('            cm.series,\n')
        f.write('            ct.year,\n')
        f.write('            ct.mint_mark,\n')
        f.write("            COALESCE(ct.variety, '') as variety,\n")
        f.write('            l.qty_remaining as quantity,\n')
        f.write("            COALESCE(l.purchase_grade_company, '') as grade_company,\n")
        f.write("            COALESCE(l.purchase_grade_text, '') as grade,\n")
        f.write('            COALESCE(l.purchase_numeric_grade, 0) as numeric_grade,\n')
        f.write('            l.slab_cert as cert_number,\n')
        f.write('            l.acquired_date,\n')
        f.write('            ROUND(l.unit_cost, 2) as cost,\n')
        f.write("            COALESCE(p.name, '') as acquired_from\n")
        f.write('        FROM lot l\n')
        f.write('        JOIN coin_type ct ON ct.id = l.coin_type_id\n')
        f.write('        JOIN coin_master cm ON cm.id = ct.master_id\n')
        f.write('        JOIN tx_line tl ON tl.id = l.acquisition_line_id\n')
        f.write('        JOIN tx t ON t.id = tl.tx_id\n')
        f.write('        LEFT JOIN party p ON p.id = t.party_id\n')
        f.write('        WHERE {where_clause}\n')
        f.write(
            '        ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety, l.purchase_numeric_grade DESC\n')
        f.write('    """\n')
        f.write('\n')
        f.write('    return execute_query_all(query, tuple(params))\n')
        f.write('\n')
        f.write('\n')
        f.write('def get_slabbed_summary():\n')
        f.write('    """Get summary statistics for slabbed coins."""\n')
        f.write('    query = """\n')
        f.write('        SELECT \n')
        f.write('            COUNT(DISTINCT l.id) as total_slabs,\n')
        f.write('            COUNT(DISTINCT cm.series) as total_series,\n')
        f.write('            SUM(l.qty_remaining) as total_coins,\n')
        f.write('            COUNT(DISTINCT l.purchase_grade_company) as grading_companies,\n')
        f.write('            ROUND(SUM(l.qty_remaining * l.unit_cost), 2) as total_cost\n')
        f.write('        FROM lot l\n')
        f.write('        JOIN coin_type ct ON ct.id = l.coin_type_id\n')
        f.write('        JOIN coin_master cm ON cm.id = ct.master_id\n')
        f.write('        WHERE l.qty_remaining > 0 \n')
        f.write('        AND l.slab_cert IS NOT NULL \n')
        f.write("        AND TRIM(l.slab_cert) != ''\n")
        f.write('    """\n')
        f.write('    return execute_query_single(query)\n')
        f.write('\n')
        f.write('\n')
        f.write('def get_slabbed_by_grade_company():\n')
        f.write('    """Get breakdown by grading company."""\n')
        f.write('    query = """\n')
        f.write('        SELECT \n')
        f.write("            COALESCE(l.purchase_grade_company, 'Unknown') as company,\n")
        f.write('            COUNT(DISTINCT l.id) as slab_count,\n')
        f.write('            SUM(l.qty_remaining) as coin_count,\n')
        f.write('            ROUND(AVG(l.purchase_numeric_grade), 1) as avg_grade\n')
        f.write('        FROM lot l\n')
        f.write('        WHERE l.qty_remaining > 0 \n')
        f.write('        AND l.slab_cert IS NOT NULL \n')
        f.write("        AND TRIM(l.slab_cert) != ''\n")
        f.write('        GROUP BY l.purchase_grade_company\n')
        f.write('        ORDER BY slab_count DESC\n')
        f.write('    """\n')
        f.write('    return execute_query_all(query)\n')
        f.write('\n')
        f.write('\n')
        f.write('def get_specimens_by_series(series=None):\n')
        f.write('    """Get specimens optionally filtered by series."""\n')
        f.write('    conditions = ["s.sold_line_id IS NULL"]\n')
        f.write('    params = []\n')
        f.write('\n')
        f.write('    if series and series != "All":\n')
        f.write('        conditions.append("cm.series = ?")\n')
        f.write('        params.append(series)\n')
        f.write('\n')
        f.write('    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""\n')
        f.write('\n')
        f.write('    query = f"""\n')
        f.write('        SELECT \n')
        f.write('            s.code,\n')
        f.write('            cm.series,\n')
        f.write('            ct.year,\n')
        f.write('            ct.mint_mark,\n')
        f.write("            COALESCE(ct.variety, '') as variety,\n")
        f.write('            s.lot_id,\n')
        f.write("            COALESCE(s.notes, '') as notes\n")
        f.write('        FROM specimen s\n')
        f.write('        JOIN coin_type ct ON ct.id = s.coin_type_id\n')
        f.write('        JOIN coin_master cm ON cm.id = ct.master_id\n')
        f.write('        {where_clause}\n')
        f.write('        ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety, s.code\n')
        f.write('    """\n')
        f.write('\n')
        f.write('    return execute_query_all(query, tuple(params))\n')
        f.write('\n')
        f.write('\n')
        f.write('def count_specimens_for_lot(lot_id):\n')
        f.write('    """Count specimens assigned to a specific lot."""\n')
        f.write('    query = "SELECT COUNT(*) AS count FROM specimen WHERE lot_id = ?"\n')
        f.write('    result = execute_query_single(query, (lot_id,))\n')
        f.write("    return result['count'] if result else 0\n")
        f.write('\n')
        f.write('\n')
        f.write('def create_specific_codes_for_lot(lot_id, codes):\n')
        f.write('    """Create specific specimen codes for a lot."""\n')
        f.write('    created = []\n')
        f.write('    errors = []\n')
        f.write('\n')
        f.write('    codes = [c.strip().upper() for c in codes if str(c).strip()]\n')
        f.write('    if not codes:\n')
        f.write('        return created, ["No codes provided."]\n')
        f.write('\n')
        f.write('    lot_query = "SELECT coin_type_id FROM lot WHERE id = ?"\n')
        f.write('    lot_result = execute_query_single(lot_query, (lot_id,))\n')
        f.write('\n')
        f.write('    if not lot_result:\n')
        f.write('        return created, [f"Unknown lot_id {lot_id}"]\n')
        f.write('\n')
        f.write("    coin_type_id = lot_result['coin_type_id']\n")
        f.write('\n')
        f.write('    for code in codes:\n')
        f.write('        exists_query = "SELECT 1 FROM specimen WHERE code = ?"\n')
        f.write('        exists = execute_query_single(exists_query, (code,))\n')
        f.write('\n')
        f.write('        if exists:\n')
        f.write('            errors.append(f"{code} already exists.")\n')
        f.write('            continue\n')
        f.write('\n')
        f.write('        try:\n')
        f.write('            execute_insert(\n')
        f.write(
            '                "INSERT INTO specimen(code, coin_type_id, lot_id) VALUES (?, ?, ?)",\n')
        f.write('                (code, coin_type_id, lot_id)\n')
        f.write('            )\n')
        f.write('            created.append(code)\n')
        f.write('        except Exception as e:\n')
        f.write('            errors.append(f"Error creating {code}: {str(e)}")\n')
        f.write('\n')
        f.write('    return created, errors\n')
        f.write('\n')
        f.write('\n')
        f.write('def update_specimen(old_code, new_code=None, new_lot_id=None, notes=None):\n')
        f.write('    """Update an existing specimen."""\n')
        f.write('    query = "SELECT id, sold_line_id FROM specimen WHERE code = ?"\n')
        f.write('    specimen = execute_query_single(query, (old_code,))\n')
        f.write('\n')
        f.write('    if not specimen:\n')
        f.write('        return False, "Specimen not found."\n')
        f.write('\n')
        f.write('    if new_code:\n')
        f.write(
            '        exists = execute_query_single("SELECT 1 FROM specimen WHERE code = ?", (new_code,))\n')
        f.write('        if exists:\n')
        f.write('            return False, "The new code already exists."\n')
        f.write('\n')
        f.write('    updates = []\n')
        f.write('    params = []\n')
        f.write('\n')
        f.write('    if new_code:\n')
        f.write('        updates.append("code = ?")\n')
        f.write('        params.append(new_code)\n')
        f.write('\n')
        f.write('    if new_lot_id is not None:\n')
        f.write("        if specimen['sold_line_id'] is not None:\n")
        f.write('            return False, "Cannot move a sold specimen."\n')
        f.write('        updates.append("lot_id = ?")\n')
        f.write('        params.append(new_lot_id)\n')
        f.write('\n')
        f.write('    if notes is not None:\n')
        f.write('        updates.append("notes = ?")\n')
        f.write('        params.append(notes)\n')
        f.write('\n')
        f.write('    if not updates:\n')
        f.write('        return True, "Nothing to update."\n')
        f.write('\n')
        f.write("    params.append(specimen['id'])\n")
        f.write('    update_query = f"UPDATE specimen SET {", ".join(updates)} WHERE id = ?"\n')
        f.write('\n')
        f.write('    try:\n')
        f.write('        execute_update(update_query, tuple(params))\n')
        f.write('        return True, "Updated."\n')
        f.write('    except Exception as e:\n')
        f.write('        return False, f"Update failed: {str(e)}"\n')
        f.write('\n')
        f.write('\n')
        f.write('def delete_specimen(code):\n')
        f.write('    """Delete a specimen if not sold."""\n')
        f.write('    query = "SELECT sold_line_id FROM specimen WHERE code = ?"\n')
        f.write('    specimen = execute_query_single(query, (code,))\n')
        f.write('\n')
        f.write('    if not specimen:\n')
        f.write('        return False, "Specimen not found."\n')
        f.write('\n')
        f.write("    if specimen['sold_line_id'] is not None:\n")
        f.write('        return False, "Cannot delete a specimen that has been sold."\n')
        f.write('\n')
        f.write('    try:\n')
        f.write('        execute_delete("DELETE FROM specimen WHERE code = ?", (code,))\n')
        f.write('        return True, "Deleted."\n')
        f.write('    except Exception as e:\n')
        f.write('        return False, f"Delete failed: {str(e)}"\n')

    print("Created pages/coin_registry_functions.py with pure ASCII encoding")


# Replace the test_original_functions in run_coin_registry_tests.py with this fixed version:

def test_original_functions():
    """Test the original functions"""
    print("Testing original coin registry functions...")

    # First, check if we need to create the temporary functions file
    if not os.path.exists('pages/coin_registry_functions.py'):
        print("Creating temporary coin_registry_functions.py for testing...")
        create_temporary_functions_file()

    try:
        from unittest.mock import patch, Mock

        # Mock core.queries functions
        mock_queries = {
            'get_specimen_by_code': Mock(return_value={'code': 'P1', 'series': 'Peace'}),
            'get_specimens_on_hand': Mock(return_value=[]),
            'create_specimens_for_lot': Mock(return_value=['P1', 'P2']),
            'create_or_update_series_code': Mock(return_value=1),
            'get_all_lots': Mock(return_value=[])
        }

        with patch.dict('sys.modules', {'core.queries': Mock(**mock_queries)}):
            with patch(
                    'infrastructure.database.db_operations.execute_query_all') as mock_execute_all, \
                    patch(
                        'infrastructure.database.db_operations.execute_query_single') as mock_execute_single, \
                    patch('infrastructure.database.db_operations.execute_insert') as mock_insert, \
                    patch('infrastructure.database.db_operations.execute_update') as mock_update, \
                    patch('infrastructure.database.db_operations.execute_delete') as mock_delete:
                # Import the functions after mocking
                from pages.coin_registry_functions import (
                    get_slabbed_series_list,
                    get_slabbed_coins_by_series,
                    get_slabbed_summary,
                    get_slabbed_by_grade_company,
                    get_specimens_by_series,
                    count_specimens_for_lot,
                    create_specific_codes_for_lot,
                    update_specimen,
                    delete_specimen
                )

                # Test get_slabbed_series_list
                mock_execute_all.return_value = [
                    {'series': 'Morgan Silver Dollars'},
                    {'series': 'Peace Silver Dollars'}
                ]
                result = get_slabbed_series_list()
                assert len(result) == 2
                assert 'Morgan Silver Dollars' in result

                # Test get_slabbed_coins_by_series
                mock_execute_all.return_value = [
                    {
                        'lot_id': 1,
                        'series': 'Morgan Silver Dollars',
                        'year': 1921,
                        'mint_mark': 'D',
                        'variety': '',
                        'quantity': 1,
                        'grade_company': 'PCGS',
                        'grade': 'MS63',
                        'numeric_grade': 63,
                        'cert_number': '12345678',
                        'acquired_date': '2024-01-01',
                        'cost': 50.00,
                        'acquired_from': 'Dealer'
                    }
                ]
                result = get_slabbed_coins_by_series('Morgan Silver Dollars')
                assert len(result) == 1
                assert result[0]['cert_number'] == '12345678'

                # Test get_slabbed_summary
                mock_execute_single.return_value = {
                    'total_slabs': 10,
                    'total_series': 3,
                    'total_coins': 15,
                    'grading_companies': 2,
                    'total_cost': 1500.00
                }
                result = get_slabbed_summary()
                assert result['total_slabs'] == 10
                assert result['total_cost'] == 1500.00

                # Test count_specimens_for_lot
                mock_execute_single.return_value = {'count': 5}
                result = count_specimens_for_lot(1)
                assert result == 5

                # Test update_specimen - Fix: setup multiple return values
                # First call gets the specimen, second checks if new code exists
                mock_execute_single.side_effect = [
                    {'id': 1, 'sold_line_id': None},  # First call: get specimen
                    None  # Second call: check if new code exists (None = doesn't exist)
                ]
                mock_update.return_value = 1
                success, msg = update_specimen('P1', new_code='P2')
                assert success == True

                # Reset side_effect for next test
                mock_execute_single.side_effect = None

                # Test delete_specimen
                mock_execute_single.return_value = {'sold_line_id': None}
                mock_delete.return_value = True
                success, msg = delete_specimen('P1')
                assert success == True

                print("✅ Original functions work correctly")
                return True

    except Exception as e:
        print(f"❌ Original functions failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_refactored_repository():
    """Test the refactored repository"""
    print("Testing refactored coin registry repository...")

    # Check if refactored files exist
    if not os.path.exists('infrastructure/database/repositories/coin_registry_repository.py'):
        print("⏭️  Skipping refactored repository test - files not created yet")
        return True

    try:
        from unittest.mock import Mock, patch

        with patch('infrastructure.database.db_operations.execute_query_all') as mock_execute_all, \
                patch(
                    'infrastructure.database.db_operations.execute_query_single') as mock_execute_single, \
                patch('infrastructure.database.db_operations.execute_insert') as mock_insert, \
                patch('infrastructure.database.db_operations.execute_update') as mock_update, \
                patch('infrastructure.database.db_operations.execute_delete') as mock_delete:

            from infrastructure.database.repositories.coin_registry_repository import (
                CoinRegistryRepository,
                SlabbedCoin,
                SlabbedSummary,
                GradingCompanySummary,
                Specimen
            )

            # Create repository with mocked database
            mock_db = Mock()
            repository = CoinRegistryRepository(mock_db)

            # Test get_slabbed_series_list
            mock_execute_all.return_value = [
                {'series': 'Morgan Silver Dollars'}
            ]
            result = repository.get_slabbed_series_list()
            assert len(result) == 1
            assert result[0] == 'Morgan Silver Dollars'

            # Test get_slabbed_summary returns dataclass
            mock_execute_single.return_value = {
                'total_slabs': 10,
                'total_series': 3,
                'total_coins': 15,
                'grading_companies': 2,
                'total_cost': 1500.00
            }
            summary = repository.get_slabbed_summary()
            assert isinstance(summary, SlabbedSummary)
            assert summary.total_slabs == 10

            print("✅ Refactored repository works correctly")
            return True

    except Exception as e:
        print(f"❌ Refactored repository failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_components():
    """Test the UI components"""
    print("Testing coin registry UI components...")

    # Check if component files exist
    if not os.path.exists('presentation/components/coin_registry_components.py'):
        print("⏭️  Skipping UI components test - files not created yet")
        return True

    try:
        from presentation.components.coin_registry_components import CoinRegistryRenderer
        from unittest.mock import Mock

        # Create renderer with mocked repository
        mock_repo = Mock()
        renderer = CoinRegistryRenderer(mock_repo)

        # Test that renderer initializes
        assert renderer.repo == mock_repo

        # Test that required methods exist
        assert hasattr(renderer, 'render_slabbed_coins_tab')
        assert hasattr(renderer, 'render_browse_specimens_tab')
        assert hasattr(renderer, 'render_add_flips_tab')
        assert hasattr(renderer, 'render_edit_flip_tab')
        assert hasattr(renderer, 'render_lookup_flip_tab')

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
        'pages/coin_registry_functions.py'
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
    print("🧪 Running Coin Registry Refactoring Tests")
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
            pass

        return 0
    else:
        print("⚠️  Some tests failed. Review before proceeding.")
        return 1


if __name__ == "__main__":
    exit(main())
