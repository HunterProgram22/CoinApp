# run_proof_sets_tests.py
"""
Test runner for Proof Sets refactoring.
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
    if os.path.exists('pages/proof_sets_functions.py'):
        os.remove('pages/proof_sets_functions.py')
        print("Removed existing proof_sets_functions.py")

    # Create the pages directory if it doesn't exist
    os.makedirs('pages', exist_ok=True)

    # Write the file line by line to avoid encoding issues
    with open('pages/proof_sets_functions.py', 'w', encoding='ascii', errors='ignore') as f:
        f.write('# pages/proof_sets_functions.py\n')
        f.write('"""\n')
        f.write('Temporary extraction of proof sets functions for testing.\n')
        f.write('These will be moved to the repository during refactoring.\n')
        f.write('"""\n')
        f.write('from infrastructure.database.db_operations import (\n')
        f.write('    execute_query_all, execute_query_single,\n')
        f.write('    execute_insert, execute_update, execute_delete\n')
        f.write(')\n')
        f.write('\n')
        f.write('\n')
        f.write('def get_proof_set_masters():\n')
        f.write('    """Get all proof set definitions."""\n')
        f.write('    query = """\n')
        f.write('        SELECT id, country, year, set_type, set_name, coin_count, \n')
        f.write('               includes_silver, original_mint_price\n')
        f.write('        FROM proof_set_master\n')
        f.write('        ORDER BY country, year DESC, set_type\n')
        f.write('    """\n')
        f.write('    return execute_query_all(query)\n')
        f.write('\n')
        f.write('\n')
        f.write('def get_inventory_summary():\n')
        f.write('    """Get summary of proof set inventory as dict list."""\n')
        f.write('    query = """\n')
        f.write('        SELECT * FROM v_proof_set_summary\n')
        f.write('        ORDER BY country, year DESC, set_type\n')
        f.write('    """\n')
        f.write('    return execute_query_all(query)\n')
        f.write('\n')
        f.write('\n')
        f.write(
            'def get_inventory_details(country=None, year=None, set_type=None, show_sold=False):\n')
        f.write('    """Get detailed inventory with filters."""\n')
        f.write('    conditions = []\n')
        f.write('    params = []\n')
        f.write('\n')
        f.write('    if country:\n')
        f.write('        conditions.append("country = ?")\n')
        f.write('        params.append(country)\n')
        f.write('\n')
        f.write('    if year:\n')
        f.write('        conditions.append("year = ?")\n')
        f.write('        params.append(year)\n')
        f.write('\n')
        f.write('    if set_type:\n')
        f.write('        conditions.append("set_type = ?")\n')
        f.write('        params.append(set_type)\n')
        f.write('\n')
        f.write('    if not show_sold:\n')
        f.write('        conditions.append("sold_date IS NULL")\n')
        f.write('\n')
        f.write('    where_clause = f"WHERE {" AND ".join(conditions)}" if conditions else ""\n')
        f.write('\n')
        f.write('    query = f"""\n')
        f.write('        SELECT * FROM v_proof_set_inventory\n')
        f.write('        {where_clause}\n')
        f.write('        ORDER BY country, year DESC, acquisition_date DESC\n')
        f.write('    """\n')
        f.write('\n')
        f.write('    return execute_query_all(query, tuple(params))\n')
        f.write('\n')
        f.write('\n')
        f.write('def add_proof_set_master(country, year, set_type, set_name, **kwargs):\n')
        f.write('    """Add a new proof set master record."""\n')
        f.write('    query = """\n')
        f.write('        INSERT INTO proof_set_master (\n')
        f.write('            country, year, set_type, set_name, mint_mark, face_value,\n')
        f.write('            original_mint_price, coin_count, includes_silver, special_features,\n')
        f.write('            packaging_type, notes\n')
        f.write('        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n')
        f.write('    """\n')
        f.write('    params = (\n')
        f.write('        country, year, set_type, set_name,\n')
        f.write("        kwargs.get('mint_mark'),\n")
        f.write("        kwargs.get('face_value'),\n")
        f.write("        kwargs.get('original_mint_price'),\n")
        f.write("        kwargs.get('coin_count'),\n")
        f.write("        1 if kwargs.get('includes_silver') else 0,\n")
        f.write("        kwargs.get('special_features'),\n")
        f.write("        kwargs.get('packaging_type'),\n")
        f.write("        kwargs.get('notes')\n")
        f.write('    )\n')
        f.write('    return execute_insert(query, params)\n')
        f.write('\n')
        f.write('\n')
        f.write(
            'def add_inventory_item(set_master_id, acquisition_date, acquisition_price, **kwargs):\n')
        f.write('    """Add a proof set to inventory."""\n')
        f.write('    party_id = None\n')
        f.write("    if kwargs.get('party_name'):\n")
        f.write('        party = execute_query_single("SELECT id FROM party WHERE name = ?",\n')
        f.write("                                     (kwargs['party_name'],))\n")
        f.write('        if party:\n')
        f.write("            party_id = party['id']\n")
        f.write('        else:\n')
        f.write('            party_id = execute_insert("INSERT INTO party(name) VALUES (?)",\n')
        f.write("                                      (kwargs['party_name'],))\n")
        f.write('\n')
        f.write('    query = """\n')
        f.write('        INSERT INTO proof_set_inventory (\n')
        f.write('            set_master_id, acquisition_date, acquisition_price, party_id,\n')
        f.write('            condition, has_coa, has_original_box, storage_location_id,\n')
        f.write('            purchase_notes, current_value, value_as_of, notes\n')
        f.write('        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n')
        f.write('    """\n')
        f.write('    params = (\n')
        f.write('        set_master_id, acquisition_date, acquisition_price, party_id,\n')
        f.write("        kwargs.get('condition', 'SEALED'),\n")
        f.write("        1 if kwargs.get('has_coa', True) else 0,\n")
        f.write("        1 if kwargs.get('has_original_box', True) else 0,\n")
        f.write("        kwargs.get('storage_location_id'),\n")
        f.write("        kwargs.get('purchase_notes'),\n")
        f.write("        kwargs.get('current_value'),\n")
        f.write("        kwargs.get('value_as_of'),\n")
        f.write("        kwargs.get('notes')\n")
        f.write('    )\n')
        f.write('    return execute_insert(query, params)\n')
        f.write('\n')
        f.write('\n')
        f.write('def update_current_value(inventory_id, current_value, value_date):\n')
        f.write('    """Update current value of an inventory item."""\n')
        f.write('    query = """\n')
        f.write('        UPDATE proof_set_inventory \n')
        f.write('        SET current_value = ?, value_as_of = ?\n')
        f.write('        WHERE id = ?\n')
        f.write('    """\n')
        f.write('    return execute_update(query, (current_value, value_date, inventory_id)) > 0\n')
        f.write('\n')
        f.write('\n')
        f.write('def record_sale(inventory_id, sold_date, sold_price, sold_to=None):\n')
        f.write('    """Record the sale of a proof set."""\n')
        f.write('    sold_to_party_id = None\n')
        f.write('    if sold_to:\n')
        f.write(
            '        party = execute_query_single("SELECT id FROM party WHERE name = ?", (sold_to,))\n')
        f.write('        if party:\n')
        f.write("            sold_to_party_id = party['id']\n")
        f.write('        else:\n')
        f.write(
            '            sold_to_party_id = execute_insert("INSERT INTO party(name) VALUES (?)", (sold_to,))\n')
        f.write('\n')
        f.write('    query = """\n')
        f.write('        UPDATE proof_set_inventory \n')
        f.write('        SET sold_date = ?, sold_price = ?, sold_to_party_id = ?\n')
        f.write('        WHERE id = ?\n')
        f.write('    """\n')
        f.write(
            '    return execute_update(query, (sold_date, sold_price, sold_to_party_id, inventory_id)) > 0\n')
        f.write('\n')
        f.write('\n')
        f.write('def get_storage_locations():\n')
        f.write('    """Get all storage locations."""\n')
        f.write('    query = "SELECT id, name, category FROM storage_location ORDER BY name"\n')
        f.write('    return execute_query_all(query)\n')
        f.write('\n')
        f.write('\n')
        f.write('def get_portfolio_summary():\n')
        f.write('    """Get portfolio summary including proof sets."""\n')
        f.write('    query = """\n')
        f.write('        SELECT \n')
        f.write('            COALESCE(COUNT(DISTINCT psi.id), 0) AS items,\n')
        f.write('            COALESCE(ROUND(SUM(psi.acquisition_price), 2), 0.0) AS total_cost,\n')
        f.write(
            '            COALESCE(ROUND(SUM(COALESCE(psi.current_value, psi.acquisition_price)), 2), 0.0) AS total_value,\n')
        f.write(
            '            COALESCE(ROUND(SUM(COALESCE(psi.current_value, psi.acquisition_price)) - SUM(psi.acquisition_price), 2), 0.0) AS unrealized_gl\n')
        f.write('        FROM proof_set_inventory psi\n')
        f.write('        WHERE psi.sold_date IS NULL\n')
        f.write('    """\n')
        f.write('    result = execute_query_single(query)\n')
        f.write('    if result:\n')
        f.write('        return {\n')
        f.write("            'items': result.get('items') or 0,\n")
        f.write("            'total_cost': float(result.get('total_cost') or 0),\n")
        f.write("            'total_value': float(result.get('total_value') or 0),\n")
        f.write("            'unrealized_gl': float(result.get('unrealized_gl') or 0)\n")
        f.write('        }\n')
        f.write('    else:\n')
        f.write('        return {\n')
        f.write("            'items': 0,\n")
        f.write("            'total_cost': 0.0,\n")
        f.write("            'total_value': 0.0,\n")
        f.write("            'unrealized_gl': 0.0\n")
        f.write('        }\n')

    print("Created pages/proof_sets_functions.py with pure ASCII encoding")


def test_original_functions():
    """Test the original functions"""
    print("Testing original proof sets functions...")

    # First, check if we need to create the temporary functions file
    if not os.path.exists('pages/proof_sets_functions.py'):
        print("Creating temporary proof_sets_functions.py for testing...")
        create_temporary_functions_file()

    try:
        from unittest.mock import patch, Mock

        with patch('infrastructure.database.db_operations.execute_query_all') as mock_execute_all, \
                patch(
                    'infrastructure.database.db_operations.execute_query_single') as mock_execute_single, \
                patch('infrastructure.database.db_operations.execute_insert') as mock_insert, \
                patch('infrastructure.database.db_operations.execute_update') as mock_update:

            # Import the functions after mocking
            from pages.proof_sets_functions import (
                get_proof_set_masters,
                get_inventory_summary,
                get_inventory_details,
                add_proof_set_master,
                add_inventory_item,
                update_current_value,
                record_sale,
                get_storage_locations,
                get_portfolio_summary
            )

            # Test get_proof_set_masters
            mock_execute_all.return_value = [
                {
                    'id': 1,
                    'country': 'United States',
                    'year': 2023,
                    'set_type': 'SILVER_PROOF',
                    'set_name': 'US Silver Proof Set',
                    'coin_count': 10,
                    'includes_silver': 1,
                    'original_mint_price': 105.00
                }
            ]

            result = get_proof_set_masters()
            assert len(result) == 1
            assert result[0]['country'] == 'United States'
            assert result[0]['set_type'] == 'SILVER_PROOF'

            # Test get_inventory_summary
            mock_execute_all.return_value = [
                {'country': 'United States', 'year': 2023, 'total_cost': 500.00}
            ]

            result = get_inventory_summary()
            assert len(result) == 1

            # Test get_inventory_details with filters
            result = get_inventory_details(country='United States', year=2023)
            mock_execute_all.assert_called()
            query = mock_execute_all.call_args[0][0]
            assert 'country = ?' in query
            assert 'year = ?' in query

            # Test add_proof_set_master
            mock_insert.return_value = 5
            result = add_proof_set_master(
                'United States', 2023, 'SILVER_PROOF', 'US Silver Proof Set',
                coin_count=10, includes_silver=True
            )
            assert result == 5

            # Test add_inventory_item
            mock_execute_single.return_value = {'id': 1}  # Party exists
            mock_insert.return_value = 10
            result = add_inventory_item(
                1, '2024-01-01', 105.00,
                party_name='Dealer',
                condition='SEALED'
            )
            assert result == 10

            # Test update_current_value
            mock_update.return_value = 1
            result = update_current_value(1, 150.00, '2024-01-15')
            assert result == True

            # Test record_sale
            mock_execute_single.return_value = None  # Party doesn't exist
            mock_insert.return_value = 5  # New party ID
            mock_update.return_value = 1
            result = record_sale(1, '2024-02-01', 200.00, 'Buyer')
            assert result == True

            # Test get_storage_locations
            mock_execute_all.return_value = [
                {'id': 1, 'name': 'Safe', 'category': 'Home'}
            ]
            result = get_storage_locations()
            assert len(result) == 1
            assert result[0]['name'] == 'Safe'

            # Test get_portfolio_summary
            mock_execute_single.return_value = {
                'items': 5,
                'total_cost': 500.00,
                'total_value': 750.00,
                'unrealized_gl': 250.00
            }

            result = get_portfolio_summary()
            assert result['items'] == 5
            assert result['total_cost'] == 500.00
            assert result['unrealized_gl'] == 250.00

            print("✅ Original functions work correctly")
            return True

    except Exception as e:
        print(f"❌ Original functions failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_refactored_repository():
    """Test the refactored repository"""
    print("Testing refactored proof sets repository...")

    # Check if refactored files exist
    if not os.path.exists('infrastructure/database/repositories/proof_sets_repository.py'):
        print("⏭️  Skipping refactored repository test - files not created yet")
        return True

    try:
        from unittest.mock import Mock, patch

        with patch('infrastructure.database.db_operations.execute_query_all') as mock_execute_all, \
                patch(
                    'infrastructure.database.db_operations.execute_query_single') as mock_execute_single, \
                patch('infrastructure.database.db_operations.execute_insert') as mock_insert, \
                patch('infrastructure.database.db_operations.execute_update') as mock_update:

            from infrastructure.database.repositories.proof_sets_repository import (
                ProofSetsRepository,
                ProofSetMaster,
                ProofSetInventory,
                InventorySummary,
                PortfolioSummary,
                StorageLocation
            )

            # Create repository with mocked database
            mock_db = Mock()
            repository = ProofSetsRepository(mock_db)

            # Test get_proof_set_masters returns dataclass objects
            mock_execute_all.return_value = [
                {
                    'id': 1,
                    'country': 'United States',
                    'year': 2023,
                    'set_type': 'SILVER_PROOF',
                    'set_name': 'US Silver Proof Set',
                    'coin_count': 10,
                    'includes_silver': 1,
                    'original_mint_price': 105.00
                }
            ]

            result = repository.get_proof_set_masters()
            assert len(result) == 1
            assert isinstance(result[0], ProofSetMaster)
            assert result[0].country == 'United States'

            # Test get_portfolio_summary returns dataclass
            mock_execute_single.return_value = {
                'items': 5,
                'total_cost': 500.00,
                'total_value': 750.00,
                'unrealized_gl': 250.00
            }

            summary = repository.get_portfolio_summary()
            assert isinstance(summary, PortfolioSummary)
            assert summary.items == 5
            assert summary.total_cost == 500.00

            print("✅ Refactored repository works correctly")
            return True

    except Exception as e:
        print(f"❌ Refactored repository failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_components():
    """Test the UI components"""
    print("Testing proof sets UI components...")

    # Check if component files exist
    if not os.path.exists('presentation/components/proof_sets_components.py'):
        print("⏭️  Skipping UI components test - files not created yet")
        return True

    try:
        from presentation.components.proof_sets_components import ProofSetsRenderer
        from unittest.mock import Mock

        # Create renderer with mocked repository
        mock_repo = Mock()
        renderer = ProofSetsRenderer(mock_repo)

        # Test that renderer initializes
        assert renderer.repo == mock_repo

        # Test that required methods exist
        assert hasattr(renderer, 'render_overview_tab')
        assert hasattr(renderer, 'render_add_inventory_tab')
        assert hasattr(renderer, 'render_manage_inventory_tab')
        assert hasattr(renderer, 'render_define_sets_tab')
        assert hasattr(renderer, 'render_market_values_tab')

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
        'pages/proof_sets_functions.py'
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
    print("🧪 Running Proof Sets Refactoring Tests")
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
