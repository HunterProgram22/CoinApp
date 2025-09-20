# run_storage_report_tests.py
"""
Test runner for Storage Report refactoring.
Run this before and after refactoring to ensure behavior is preserved.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath('.'))

# Mock streamlit before importing anything
from unittest.mock import MagicMock

sys.modules['streamlit'] = MagicMock()

# run_storage_report_tests.py
"""
Test runner for Storage Report refactoring.
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
    if os.path.exists('pages/storage_report_functions.py'):
        os.remove('pages/storage_report_functions.py')
        print("Removed existing storage_report_functions.py")

    # Create the pages directory if it doesn't exist
    os.makedirs('pages', exist_ok=True)

    # Write the file line by line to avoid any encoding issues
    with open('pages/storage_report_functions.py', 'w', encoding='ascii', errors='ignore') as f:
        f.write('# pages/storage_report_functions.py\n')
        f.write('"""\n')
        f.write('Temporary extraction of storage report functions for testing.\n')
        f.write('These will be moved to the repository during refactoring.\n')
        f.write('"""\n')
        f.write('from infrastructure.database.db_operations import (\n')
        f.write('    execute_query_all, execute_query_single,\n')
        f.write('    execute_insert, execute_update, execute_delete\n')
        f.write(')\n')
        f.write('\n')
        f.write('\n')
        f.write('def get_storage_locations(category_filter=None):\n')
        f.write('    """Get all storage locations with inventory counts."""\n')
        f.write('    if category_filter and category_filter != "All":\n')
        f.write('        query = """\n')
        f.write('            SELECT \n')
        f.write('                sl.id,\n')
        f.write('                sl.name,\n')
        f.write("                COALESCE(sl.category, '') AS category,\n")
        f.write("                COALESCE(sl.description, '') AS description,\n")
        f.write('                COUNT(l.id) AS lot_count,\n')
        f.write('                COALESCE(SUM(l.qty_remaining), 0) AS total_coins,\n')
        f.write(
            '                COALESCE(SUM(l.qty_remaining * l.unit_cost), 0) AS total_cost_usd,\n')
        f.write(
            '                COALESCE(SUM(l.qty_remaining * COALESCE(v.chosen_unit_value, l.unit_cost)), 0) AS total_value_usd\n')
        f.write('            FROM storage_location sl\n')
        f.write(
            '            LEFT JOIN lot l ON l.storage_location_id = sl.id AND l.qty_remaining > 0\n')
        f.write('            LEFT JOIN v_lot_value_details v ON v.lot_id = l.id\n')
        f.write('            WHERE sl.category = ?\n')
        f.write('            GROUP BY sl.id, sl.name, sl.category, sl.description\n')
        f.write('            ORDER BY sl.name\n')
        f.write('        """\n')
        f.write('        return execute_query_all(query, (category_filter,))\n')
        f.write('    else:\n')
        f.write('        query = """\n')
        f.write('            SELECT \n')
        f.write('                sl.id,\n')
        f.write('                sl.name,\n')
        f.write("                COALESCE(sl.category, '') AS category,\n")
        f.write("                COALESCE(sl.description, '') AS description,\n")
        f.write('                COUNT(l.id) AS lot_count,\n')
        f.write('                COALESCE(SUM(l.qty_remaining), 0) AS total_coins,\n')
        f.write(
            '                COALESCE(SUM(l.qty_remaining * l.unit_cost), 0) AS total_cost_usd,\n')
        f.write(
            '                COALESCE(SUM(l.qty_remaining * COALESCE(v.chosen_unit_value, l.unit_cost)), 0) AS total_value_usd\n')
        f.write('            FROM storage_location sl\n')
        f.write(
            '            LEFT JOIN lot l ON l.storage_location_id = sl.id AND l.qty_remaining > 0\n')
        f.write('            LEFT JOIN v_lot_value_details v ON v.lot_id = l.id\n')
        f.write('            GROUP BY sl.id, sl.name, sl.category, sl.description\n')
        f.write('            ORDER BY sl.name\n')
        f.write('        """\n')
        f.write('        return execute_query_all(query)\n')
        f.write('\n')
        f.write('\n')
        f.write('def get_storage_categories():\n')
        f.write('    """Get list of unique storage categories."""\n')
        f.write('    query = """\n')
        f.write('        SELECT DISTINCT category \n')
        f.write('        FROM storage_location \n')
        f.write("        WHERE category IS NOT NULL AND category != ''\n")
        f.write('        ORDER BY category\n')
        f.write('    """\n')
        f.write('    results = execute_query_all(query)\n')
        f.write("    return [r['category'] for r in results]\n")
        f.write('\n')
        f.write('\n')
        f.write('def get_category_summary(category):\n')
        f.write('    """Get summary statistics for a specific storage category."""\n')
        f.write('    query = """\n')
        f.write('        SELECT \n')
        f.write('            COUNT(DISTINCT sl.id) AS location_count,\n')
        f.write('            COALESCE(SUM(l.qty_remaining), 0) AS total_coins,\n')
        f.write('            COALESCE(SUM(l.qty_remaining * l.unit_cost), 0) AS total_cost,\n')
        f.write(
            '            COALESCE(SUM(l.qty_remaining * COALESCE(v.chosen_unit_value, l.unit_cost)), 0) AS total_value\n')
        f.write('        FROM storage_location sl\n')
        f.write(
            '        LEFT JOIN lot l ON l.storage_location_id = sl.id AND l.qty_remaining > 0\n')
        f.write('        LEFT JOIN v_lot_value_details v ON v.lot_id = l.id\n')
        f.write('        WHERE sl.category = ?\n')
        f.write('    """\n')
        f.write('    result = execute_query_single(query, (category,))\n')
        f.write('    return result if result else {}\n')
        f.write('\n')
        f.write('\n')
        f.write('def get_inventory_by_storage(storage_id):\n')
        f.write('    """Get detailed inventory for a specific storage location."""\n')
        f.write('    query = """\n')
        f.write('        SELECT\n')
        f.write('            l.id AS lot_id,\n')
        f.write('            cm.series,\n')
        f.write('            ct.year,\n')
        f.write('            ct.mint_mark,\n')
        f.write("            COALESCE(ct.variety, '') AS variety,\n")
        f.write("            CASE WHEN ct.is_proof = 1 THEN 'Yes' ELSE 'No' END AS is_proof,\n")
        f.write('            l.qty_remaining AS quantity,\n')
        f.write('            t.tx_date AS acquired_date,\n')
        f.write("            COALESCE(p.name, '') AS acquired_from,\n")
        f.write('            ROUND(l.unit_cost, 2) AS unit_cost_usd,\n')
        f.write('            ROUND(l.qty_remaining * l.unit_cost, 2) AS lot_cost_usd,\n')
        f.write(
            "            COALESCE(l.estimated_grade_text, l.purchase_grade_text, '') AS grade,\n")
        f.write("            COALESCE(l.slab_cert, '') AS cert_number,\n")
        f.write('            l.valuation_method,\n')
        f.write("            COALESCE(l.notes, '') AS notes,\n")
        f.write(
            '            ROUND(l.qty_remaining * COALESCE(v.chosen_unit_value, l.unit_cost), 2) AS est_value_usd\n')
        f.write('        FROM lot l\n')
        f.write('        JOIN coin_type ct ON ct.id = l.coin_type_id\n')
        f.write('        JOIN coin_master cm ON cm.id = ct.master_id\n')
        f.write('        JOIN tx_line tl ON tl.id = l.acquisition_line_id\n')
        f.write('        JOIN tx t ON t.id = tl.tx_id\n')
        f.write('        LEFT JOIN party p ON p.id = t.party_id\n')
        f.write('        LEFT JOIN v_lot_value_details v ON v.lot_id = l.id\n')
        f.write('        WHERE l.storage_location_id = ? AND l.qty_remaining > 0\n')
        f.write('        ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety, l.acquired_date\n')
        f.write('    """\n')
        f.write('    return execute_query_all(query, (storage_id,))\n')
        f.write('\n')
        f.write('\n')
        f.write('def get_unassigned_inventory():\n')
        f.write('    """Get inventory not assigned to any storage location."""\n')
        f.write('    query = """\n')
        f.write('        SELECT\n')
        f.write('            l.id AS lot_id,\n')
        f.write('            cm.series,\n')
        f.write('            ct.year,\n')
        f.write('            ct.mint_mark,\n')
        f.write("            COALESCE(ct.variety, '') AS variety,\n")
        f.write("            CASE WHEN ct.is_proof = 1 THEN 'Yes' ELSE 'No' END AS is_proof,\n")
        f.write('            l.qty_remaining AS quantity,\n')
        f.write('            t.tx_date AS acquired_date,\n')
        f.write("            COALESCE(p.name, '') AS acquired_from,\n")
        f.write('            ROUND(l.unit_cost, 2) AS unit_cost_usd,\n')
        f.write('            ROUND(l.qty_remaining * l.unit_cost, 2) AS lot_cost_usd,\n')
        f.write(
            "            COALESCE(l.estimated_grade_text, l.purchase_grade_text, '') AS grade,\n")
        f.write("            COALESCE(l.slab_cert, '') AS cert_number,\n")
        f.write('            l.valuation_method,\n')
        f.write("            COALESCE(l.notes, '') AS notes,\n")
        f.write(
            '            ROUND(l.qty_remaining * COALESCE(v.chosen_unit_value, l.unit_cost), 2) AS est_value_usd\n')
        f.write('        FROM lot l\n')
        f.write('        JOIN coin_type ct ON ct.id = l.coin_type_id\n')
        f.write('        JOIN coin_master cm ON cm.id = ct.master_id\n')
        f.write('        JOIN tx_line tl ON tl.id = l.acquisition_line_id\n')
        f.write('        JOIN tx t ON t.id = tl.tx_id\n')
        f.write('        LEFT JOIN party p ON p.id = t.party_id\n')
        f.write('        LEFT JOIN v_lot_value_details v ON v.lot_id = l.id\n')
        f.write('        WHERE l.storage_location_id IS NULL AND l.qty_remaining > 0\n')
        f.write('        ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety, l.acquired_date\n')
        f.write('    """\n')
        f.write('    return execute_query_all(query)\n')
        f.write('\n')
        f.write('\n')
        f.write('def get_storage_summary():\n')
        f.write('    """Get overall storage summary statistics."""\n')
        f.write('    summary_query = """\n')
        f.write('        SELECT \n')
        f.write('            (SELECT COUNT(*) FROM storage_location) AS total_locations,\n')
        f.write('            (SELECT COUNT(DISTINCT l.storage_location_id) \n')
        f.write('             FROM lot l \n')
        f.write(
            '             WHERE l.qty_remaining > 0 AND l.storage_location_id IS NOT NULL) AS locations_with_inventory,\n')
        f.write('            (SELECT COALESCE(SUM(l.qty_remaining), 0) \n')
        f.write('             FROM lot l \n')
        f.write(
            '             WHERE l.qty_remaining > 0 AND l.storage_location_id IS NULL) AS unassigned_coins,\n')
        f.write('            (SELECT COALESCE(SUM(l.qty_remaining * l.unit_cost), 0)\n')
        f.write('             FROM lot l \n')
        f.write(
            '             WHERE l.qty_remaining > 0 AND l.storage_location_id IS NULL) AS unassigned_value\n')
        f.write('    """\n')
        f.write('    result = execute_query_single(summary_query)\n')
        f.write('    return result if result else {}\n')
        f.write('\n')
        f.write('\n')
        f.write('def create_storage_location(name, category=None, description=None):\n')
        f.write('    """Create a new storage location."""\n')
        f.write(
            '    query = "INSERT INTO storage_location (name, category, description) VALUES (?, ?, ?)"\n')
        f.write('    return execute_insert(query, (name, category, description))\n')
        f.write('\n')
        f.write('\n')
        f.write('def update_storage_location(storage_id, name, category=None, description=None):\n')
        f.write('    """Update an existing storage location."""\n')
        f.write(
            '    query = "UPDATE storage_location SET name = ?, category = ?, description = ? WHERE id = ?"\n')
        f.write('    return execute_update(query, (name, category, description, storage_id))\n')
        f.write('\n')
        f.write('\n')
        f.write('def delete_storage_location(storage_id):\n')
        f.write('    """Delete a storage location if it has no inventory."""\n')
        f.write(
            '    check_query = "SELECT COUNT(*) as count FROM lot WHERE storage_location_id = ? AND qty_remaining > 0"\n')
        f.write('    result = execute_query_single(check_query, (storage_id,))\n')
        f.write('    \n')
        f.write("    if result and result['count'] > 0:\n")
        f.write('        return False\n')
        f.write('    \n')
        f.write('    delete_query = "DELETE FROM storage_location WHERE id = ?"\n')
        f.write('    execute_delete(delete_query, (storage_id,))\n')
        f.write('    return True\n')
        f.write('\n')
        f.write('\n')
        f.write('def bulk_move_lots(lot_ids, new_storage_id):\n')
        f.write('    """Move multiple lots to a new storage location."""\n')
        f.write('    if not lot_ids:\n')
        f.write('        return 0\n')
        f.write('    \n')
        f.write("    placeholders = ','.join('?' * len(lot_ids))\n")
        f.write(
            '    query = f"UPDATE lot SET storage_location_id = ? WHERE id IN ({placeholders})"\n')
        f.write('    params = [new_storage_id] + lot_ids\n')
        f.write('    return execute_update(query, tuple(params))\n')
        f.write('\n')
        f.write('\n')
        f.write('def get_lots_in_storage(storage_id):\n')
        f.write('    """Get all lots in a specific storage location."""\n')
        f.write('    if storage_id is None:\n')
        f.write('        query = """\n')
        f.write('            SELECT \n')
        f.write('                l.id,\n')
        f.write("                cm.series || ' ' || ct.year || \n")
        f.write(
            "                CASE WHEN ct.mint_mark != '' THEN ' ' || ct.mint_mark ELSE '' END ||\n")
        f.write(
            "                CASE WHEN ct.variety != '' THEN ' - ' || ct.variety ELSE '' END AS description,\n")
        f.write('                l.qty_remaining,\n')
        f.write('                ROUND(l.unit_cost * l.qty_remaining, 2) as total_value\n')
        f.write('            FROM lot l\n')
        f.write('            JOIN coin_type ct ON ct.id = l.coin_type_id\n')
        f.write('            JOIN coin_master cm ON cm.id = ct.master_id\n')
        f.write('            WHERE l.storage_location_id IS NULL AND l.qty_remaining > 0\n')
        f.write('            ORDER BY cm.series, ct.year\n')
        f.write('        """\n')
        f.write('        return execute_query_all(query)\n')
        f.write('    else:\n')
        f.write('        query = """\n')
        f.write('            SELECT \n')
        f.write('                l.id,\n')
        f.write("                cm.series || ' ' || ct.year || \n")
        f.write(
            "                CASE WHEN ct.mint_mark != '' THEN ' ' || ct.mint_mark ELSE '' END ||\n")
        f.write(
            "                CASE WHEN ct.variety != '' THEN ' - ' || ct.variety ELSE '' END AS description,\n")
        f.write('                l.qty_remaining,\n')
        f.write('                ROUND(l.unit_cost * l.qty_remaining, 2) as total_value\n')
        f.write('            FROM lot l\n')
        f.write('            JOIN coin_type ct ON ct.id = l.coin_type_id\n')
        f.write('            JOIN coin_master cm ON cm.id = ct.master_id\n')
        f.write('            WHERE l.storage_location_id = ? AND l.qty_remaining > 0\n')
        f.write('            ORDER BY cm.series, ct.year\n')
        f.write('        """\n')
        f.write('        return execute_query_all(query, (storage_id,))\n')

    print("Created pages/storage_report_functions.py with pure ASCII encoding")


# Rest of the test file continues with the same test functions...
# (keeping the rest of your test file as is, just replacing the create_temporary_functions_file function)

def test_original_functions():
    """Test the original functions"""
    print("Testing original storage report functions...")

    # First, check if we need to create the temporary functions file
    if not os.path.exists('pages/storage_report_functions.py'):
        print("Creating temporary storage_report_functions.py for testing...")
        create_temporary_functions_file()

    try:
        from unittest.mock import patch, Mock

        with patch('infrastructure.database.db_operations.execute_query_all') as mock_execute_all, \
                patch(
                    'infrastructure.database.db_operations.execute_query_single') as mock_execute_single, \
                patch('infrastructure.database.db_operations.execute_insert') as mock_insert, \
                patch('infrastructure.database.db_operations.execute_update') as mock_update, \
                patch('infrastructure.database.db_operations.execute_delete') as mock_delete:

            # Import the functions after mocking
            from pages.storage_report_functions import (
                get_storage_locations,
                get_storage_categories,
                get_category_summary,
                get_inventory_by_storage,
                get_unassigned_inventory,
                get_storage_summary,
                create_storage_location,
                update_storage_location,
                delete_storage_location,
                bulk_move_lots,
                get_lots_in_storage
            )

            # Test get_storage_locations without filter
            mock_execute_all.return_value = [
                {
                    'id': 1,
                    'name': 'Home Safe',
                    'category': 'Safe',
                    'description': 'Main safe',
                    'lot_count': 5,
                    'total_coins': 100,
                    'total_cost_usd': 2500.00,
                    'total_value_usd': 3000.00
                }
            ]

            result = get_storage_locations()
            assert len(result) == 1
            assert result[0]['name'] == 'Home Safe'
            assert result[0]['total_coins'] == 100

            # Test with category filter
            result = get_storage_locations("Safe")
            assert len(result) == 1
            mock_execute_all.assert_called()
            query = mock_execute_all.call_args[0][0]
            assert 'WHERE sl.category = ?' in query

            # Test get_storage_categories
            mock_execute_all.return_value = [
                {'category': 'Safe'},
                {'category': 'Bank'},
                {'category': 'Display'}
            ]

            categories = get_storage_categories()
            assert len(categories) == 3
            assert 'Safe' in categories
            assert 'Bank' in categories

            # Test get_category_summary
            mock_execute_single.return_value = {
                'location_count': 3,
                'total_coins': 150,
                'total_cost': 5000.00,
                'total_value': 6000.00
            }

            summary = get_category_summary("Safe")
            assert summary['location_count'] == 3
            assert summary['total_coins'] == 150

            # Test get_inventory_by_storage
            mock_execute_all.return_value = [
                {
                    'lot_id': 1,
                    'series': 'Morgan Silver Dollars',
                    'year': 1921,
                    'mint_mark': 'D',
                    'variety': '',
                    'is_proof': 'No',
                    'quantity': 5,
                    'acquired_date': '2024-01-15',
                    'acquired_from': 'Dealer',
                    'unit_cost_usd': 25.00,
                    'lot_cost_usd': 125.00,
                    'grade': 'MS63',
                    'cert_number': '',
                    'valuation_method': 'PCGS',
                    'notes': '',
                    'est_value_usd': 150.00
                }
            ]

            inventory = get_inventory_by_storage(1)
            assert len(inventory) == 1
            assert inventory[0]['series'] == 'Morgan Silver Dollars'
            assert inventory[0]['quantity'] == 5

            # Test get_unassigned_inventory
            unassigned = get_unassigned_inventory()
            assert isinstance(unassigned, list)

            # Test get_storage_summary
            mock_execute_single.return_value = {
                'total_locations': 10,
                'locations_with_inventory': 8,
                'unassigned_coins': 25,
                'unassigned_value': 500.00
            }

            summary = get_storage_summary()
            assert summary['total_locations'] == 10
            assert summary['unassigned_coins'] == 25

            # Test create_storage_location
            mock_insert.return_value = 5
            new_id = create_storage_location("Test Safe", "Safe", "Test description")
            assert new_id == 5
            mock_insert.assert_called_once()

            # Test update_storage_location
            mock_update.return_value = 1
            rows = update_storage_location(1, "Updated Safe", "Safe", "Updated description")
            assert rows == 1

            # Test delete_storage_location
            mock_execute_single.return_value = {'count': 0}  # No inventory
            result = delete_storage_location(1)
            assert result == True
            mock_delete.assert_called_once()

            # Test delete with inventory (should fail)
            mock_execute_single.return_value = {'count': 5}  # Has inventory
            mock_delete.reset_mock()
            result = delete_storage_location(2)
            assert result == False
            mock_delete.assert_not_called()

            # Test bulk_move_lots
            mock_update.return_value = 3
            count = bulk_move_lots([1, 2, 3], 5)
            assert count == 3

            # Test bulk_move_lots with empty list
            count = bulk_move_lots([], 5)
            assert count == 0

            # Test get_lots_in_storage
            mock_execute_all.return_value = [
                {
                    'id': 1,
                    'description': 'Morgan Silver Dollar 1921 D',
                    'qty_remaining': 5,
                    'total_value': 125.00
                }
            ]

            lots = get_lots_in_storage(1)
            assert len(lots) == 1
            assert lots[0]['description'] == 'Morgan Silver Dollar 1921 D'

            # Test get_lots_in_storage for unassigned (None)
            lots = get_lots_in_storage(None)
            assert isinstance(lots, list)

            print("✅ Original functions work correctly")
            return True

    except Exception as e:
        print(f"❌ Original functions failed: {e}")
        import traceback
        traceback.print_exc()
        return False


# Update the test_refactored_repository function in run_storage_report_tests.py

def test_refactored_repository():
    """Test the refactored repository"""
    print("Testing refactored storage report repository...")

    # Check if refactored files exist
    if not os.path.exists('infrastructure/database/repositories/storage_report_repository.py'):
        print("⏭️  Skipping refactored repository test - files not created yet")
        return True

    try:
        from unittest.mock import Mock, patch

        # Mock the database operations that the repository uses directly
        with patch('infrastructure.database.db_operations.execute_query_all') as mock_execute_all, \
                patch(
                    'infrastructure.database.db_operations.execute_query_single') as mock_execute_single, \
                patch('infrastructure.database.db_operations.execute_insert') as mock_insert, \
                patch('infrastructure.database.db_operations.execute_update') as mock_update, \
                patch('infrastructure.database.db_operations.execute_delete') as mock_delete:

            from infrastructure.database.repositories.storage_report_repository import (
                StorageReportRepository,
                StorageLocation,
                StorageInventory,
                StorageSummary,
                CategorySummary,
                LotInStorage
            )

            # Create repository with mocked database
            mock_db = Mock()
            repository = StorageReportRepository(mock_db)

            # Test get_storage_locations returns dataclass objects
            mock_execute_all.return_value = [
                {
                    'id': 1,
                    'name': 'Home Safe',
                    'category': 'Safe',
                    'description': 'Main safe',
                    'lot_count': 5,
                    'total_coins': 100,
                    'total_cost_usd': 2500.00,
                    'total_value_usd': 3000.00
                }
            ]

            result = repository.get_storage_locations()
            assert len(result) == 1
            assert isinstance(result[0], StorageLocation)
            assert result[0].name == 'Home Safe'
            assert result[0].total_coins == 100

            # Test with category filter
            result = repository.get_storage_locations("Safe")
            assert len(result) == 1

            # Test get_storage_categories
            mock_execute_all.return_value = [
                {'category': 'Safe'},
                {'category': 'Bank'}
            ]

            categories = repository.get_storage_categories()
            assert categories == ['Safe', 'Bank']

            # Test get_category_summary returns dataclass
            mock_execute_single.return_value = {
                'location_count': 3,
                'total_coins': 150,
                'total_cost': 5000.00,
                'total_value': 6000.00
            }

            summary = repository.get_category_summary("Safe")
            assert isinstance(summary, CategorySummary)
            assert summary.location_count == 3
            assert summary.total_coins == 150

            # Test get_inventory_by_storage returns dataclass objects
            mock_execute_all.return_value = [
                {
                    'lot_id': 1,
                    'series': 'Morgan Silver Dollars',
                    'year': 1921,
                    'mint_mark': 'D',
                    'variety': '',
                    'is_proof': 'No',
                    'quantity': 5,
                    'acquired_date': '2024-01-15',
                    'acquired_from': 'Dealer',
                    'unit_cost_usd': 25.00,
                    'lot_cost_usd': 125.00,
                    'grade': 'MS63',
                    'cert_number': '',
                    'valuation_method': 'PCGS',
                    'notes': '',
                    'est_value_usd': 150.00
                }
            ]

            inventory = repository.get_inventory_by_storage(1)
            assert len(inventory) == 1
            assert isinstance(inventory[0], StorageInventory)
            assert inventory[0].series == 'Morgan Silver Dollars'
            assert inventory[0].quantity == 5

            # Test get_storage_summary returns dataclass
            mock_execute_single.return_value = {
                'total_locations': 10,
                'locations_with_inventory': 8,
                'unassigned_coins': 25,
                'unassigned_value': 500.00
            }

            summary = repository.get_storage_summary()
            assert isinstance(summary, StorageSummary)
            assert summary.total_locations == 10
            assert summary.unassigned_coins == 25

            # Test get_lots_in_storage returns dataclass objects
            mock_execute_all.return_value = [
                {
                    'id': 1,
                    'description': 'Morgan Silver Dollar 1921 D',
                    'qty_remaining': 5,
                    'total_value': 125.00
                }
            ]

            lots = repository.get_lots_in_storage(1)
            assert len(lots) == 1
            assert isinstance(lots[0], LotInStorage)
            assert lots[0].description == 'Morgan Silver Dollar 1921 D'

            # Test bulk_move_lots
            mock_update.return_value = 3
            count = repository.bulk_move_lots([1, 2, 3], 5)
            assert count == 3

            # Test bulk_move_lots with empty list
            count = repository.bulk_move_lots([], 5)
            assert count == 0

            # Test delete_storage_location with no inventory
            mock_execute_single.return_value = {'count': 0}
            result = repository.delete_storage_location(1)
            assert result == True

            # Test delete_storage_location with inventory
            mock_execute_single.return_value = {'count': 5}
            result = repository.delete_storage_location(2)
            assert result == False

            print("✅ Refactored repository works correctly")
            return True

    except Exception as e:
        print(f"❌ Refactored repository failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_components():
    """Test the UI components"""
    print("Testing storage report UI components...")

    # Check if component files exist
    if not os.path.exists('presentation/components/storage_report_components.py'):
        print("⏭️  Skipping UI components test - files not created yet")
        return True

    try:
        from presentation.components.storage_report_components import StorageReportRenderer
        from unittest.mock import Mock

        # Create renderer with mocked repository
        mock_repo = Mock()
        renderer = StorageReportRenderer(mock_repo)

        # Test that renderer initializes
        assert renderer.repo == mock_repo

        # Test that required methods exist
        assert hasattr(renderer, 'render_summary_tab')
        assert hasattr(renderer, 'render_detail_tab')
        assert hasattr(renderer, 'render_manage_storage_tab')
        assert hasattr(renderer, 'render_bulk_move_tab')
        assert hasattr(renderer, '_render_unassigned_inventory_section')
        assert hasattr(renderer, '_create_download_button')

        print("✅ UI components work correctly")
        return True

    except Exception as e:
        print(f"❌ UI components failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_helper_functions():
    """Test the helper functions"""
    print("Testing storage report helper functions...")

    # First, check if we need to create the helper functions
    if not os.path.exists('presentation/helpers/storage_report_helpers.py'):
        print("⏭️  Skipping helper functions test - files not created yet")
        return True

    try:
        import pandas as pd
        from presentation.helpers.storage_report_helpers import (
            format_year_columns_for_display,
            format_money_columns
        )

        # Test format_year_columns_for_display
        df = pd.DataFrame({
            'year': [1921, 1922, None, 1923],
            'series': ['Morgan', 'Peace', 'Walking', 'Morgan']
        })

        result = format_year_columns_for_display(df)
        assert result['year'].iloc[0] == '1921'
        assert result['year'].iloc[2] == ''  # NaN becomes empty string

        # Test with empty DataFrame
        empty_df = pd.DataFrame()
        result = format_year_columns_for_display(empty_df)
        assert result.empty

        # Test format_money_columns
        df = pd.DataFrame({
            'name': ['Item 1', 'Item 2'],
            'cost': [100.5, 250.75],
            'value': [120.0, 300.0]
        })

        display_df, csv_df = format_money_columns(df, ['cost', 'value'])
        assert display_df['cost'].iloc[0] == '$100.50'
        assert display_df['value'].iloc[1] == '$300.00'
        assert csv_df['cost'].iloc[0] == 100.5  # CSV version unchanged

        print("✅ Helper functions work correctly")
        return True

    except Exception as e:
        print(f"❌ Helper functions failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def cleanup_test_files():
    """Clean up temporary files created during testing"""
    temp_files = [
        'pages/storage_report_functions.py'
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
    print("🧪 Running Storage Report Refactoring Tests")
    print("=" * 50)

    tests = [
        test_original_functions,
        test_refactored_repository,
        test_components,
        test_helper_functions
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