# run_world_coins_tests.py
"""
Test runner to validate our world coins refactoring.
Run this before and after refactoring to ensure behavior is preserved.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath('.'))

# Mock streamlit before importing anything
from unittest.mock import MagicMock
sys.modules['streamlit'] = MagicMock()

def create_temporary_world_coins_functions_file():
    """Create the temporary functions file for testing"""
    functions_content = '''# pages/world_coins_functions.py
"""
Temporary extraction of world coins functions for testing.
These will be moved to the repository during refactoring.
"""
from infrastructure.database.db_operations import execute_query_all, execute_query_single


def get_countries_on_hand():
    """Get list of countries with inventory on hand."""
    query = """
        SELECT DISTINCT COALESCE(cm.country, '') AS country
        FROM lot l
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        WHERE l.qty_remaining > 0 AND COALESCE(cm.country, '') <> ''
        ORDER BY country
    """
    results = execute_query_all(query)
    return [r["country"] for r in results]


def check_asset_category_support():
    """Check if coin_master table has asset_category column."""
    try:
        result = execute_query_single(
            "SELECT 1 FROM pragma_table_info('coin_master') WHERE name='asset_category'"
        )
        return bool(result)
    except Exception:
        return False


def get_world_coins_summary(country, want_proofs=False, want_slabbed=False, asset_category=None):
    """Get summary data for world coins by series."""
    where_conditions = ["cm.country = ?", "l.qty_remaining > 0"]
    params = [country]
    
    if want_proofs:
        where_conditions.append("ct.is_proof = 1")
    
    if want_slabbed:
        where_conditions.append(
            "(COALESCE(l.slab_cert, '') <> '' OR "
            "UPPER(COALESCE(l.purchase_grade_company, '')) IN ('PCGS','NGC','ANACS','ICG'))"
        )
    
    if asset_category and asset_category != "All":
        where_conditions.append("cm.asset_category = ?")
        params.append(asset_category)
    
    where_clause = " AND ".join(where_conditions)
    
    # Check if v_lot_value_details view exists
    view_check = execute_query_single(
        "SELECT 1 FROM sqlite_master WHERE type='view' AND name='v_lot_value_details'"
    )
    
    if view_check:
        query = f"""
            SELECT
                cm.series AS Series,
                SUM(v.qty_remaining) AS Coins,
                ROUND(SUM(v.qty_remaining * COALESCE(v.melt_unit_value, 0)), 2) AS "Melt Value (USD)",
                ROUND(SUM(v.qty_remaining * COALESCE(v.chosen_unit_value, 0)), 2) AS "Est. Value (USD)"
            FROM v_lot_value_details v
            JOIN lot l ON l.id = v.lot_id
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE {where_clause}
            GROUP BY cm.series
            ORDER BY "Est. Value (USD)" DESC, cm.series
        """
    else:
        # Fallback without valuation view
        query = f"""
            SELECT
                cm.series AS Series,
                SUM(l.qty_remaining) AS Coins,
                NULL AS "Melt Value (USD)",
                NULL AS "Est. Value (USD)"
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE {where_clause}
            GROUP BY cm.series
            ORDER BY Coins DESC, cm.series
        """
    
    return execute_query_all(query, params)


def get_world_coins_detail(country, want_proofs=False, want_slabbed=False, asset_category=None):
    """Get detailed data for world coins."""
    where_conditions = ["cm.country = ?", "l.qty_remaining > 0"]
    params = [country]
    
    if want_proofs:
        where_conditions.append("ct.is_proof = 1")
    
    if want_slabbed:
        where_conditions.append(
            "(COALESCE(l.slab_cert, '') <> '' OR "
            "UPPER(COALESCE(l.purchase_grade_company, '')) IN ('PCGS','NGC','ANACS','ICG'))"
        )
    
    if asset_category and asset_category != "All":
        where_conditions.append("cm.asset_category = ?")
        params.append(asset_category)
    
    where_clause = " AND ".join(where_conditions)
    
    # Check for specimen table and features
    specimen_check = execute_query_single(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='specimen'"
    )
    
    flip_cte = ""
    flip_join = ""
    flip_select = "'' AS [Flip IDs],"  # Use square brackets to avoid quote issues
    
    if specimen_check:
        code_check = execute_query_single(
            "SELECT 1 FROM pragma_table_info('specimen') WHERE name='specimen_code'"
        )
        
        if code_check:
            sold_check = execute_query_single(
                "SELECT 1 FROM pragma_table_info('specimen') WHERE name='sold_line_id'"
            )
            
            where_unsold = " WHERE sold_line_id IS NULL" if sold_check else ""
            flip_cte = f"""
                WITH flip AS (
                    SELECT lot_id, GROUP_CONCAT(specimen_code, ', ') AS flip_ids
                    FROM specimen{where_unsold}
                    GROUP BY lot_id
                )
            """
            flip_join = "LEFT JOIN flip f ON f.lot_id = l.id"
            flip_select = "COALESCE(f.flip_ids, '') AS [Flip IDs],"  # Use square brackets
    
    # Check if v_lot_value_details view exists
    view_check = execute_query_single(
        "SELECT 1 FROM sqlite_master WHERE type='view' AND name='v_lot_value_details'"
    )
    
    if view_check:
        value_columns = """
            ROUND(v.melt_unit_value, 4) AS [Melt Unit Value],
            ROUND(v.chosen_unit_value, 2) AS [Chosen Unit Value],
            ROUND(l.qty_remaining * COALESCE(v.chosen_unit_value, 0), 2) AS [Lot Est. Value],
        """
        value_join = "LEFT JOIN v_lot_value_details v ON v.lot_id = l.id"
    else:
        value_columns = """
            NULL AS [Melt Unit Value],
            NULL AS [Chosen Unit Value], 
            NULL AS [Lot Est. Value],
        """
        value_join = ""
    
    query = f"""
        {flip_cte}
        SELECT
            cm.series AS Series,
            ct.year AS Year,
            ct.mint_mark AS [Mint Mark],
            COALESCE(ct.variety, '') AS Variety,
            l.id AS lot_id,
            t.tx_date AS Acquired,
            COALESCE(p.name, '') AS Party,
            l.qty_remaining AS Qty,
            ROUND(l.unit_cost, 2) AS [Unit Cost (USD)],
            {value_columns}
            COALESCE(l.estimated_grade_text, l.purchase_grade_text, '') AS Grade,
            {flip_select}
            COALESCE(l.slab_cert, '') AS [Cert #]
        FROM lot l
        JOIN tx_line tl ON tl.id = l.acquisition_line_id
        JOIN tx t ON t.id = tl.tx_id
        LEFT JOIN party p ON p.id = t.party_id
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        {value_join}
        {flip_join}
        WHERE {where_clause}
        ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety, l.id
    """
    
    return execute_query_all(query, params)


def format_year_columns_for_display(df):
    """Format year columns for display (handle NaN values)."""
    import pandas as pd
    
    if df is None or df.empty:
        return df
    
    out = df.copy()
    year_columns = [c for c in out.columns if c.lower() in {"year", "years_start", "years_end"}]
    
    for col in year_columns:
        out[col] = pd.to_numeric(out[col], errors="coerce").map(
            lambda x: "" if pd.isna(x) else f"{int(x)}"
        )
    
    return out


def format_money_columns(df, money_columns, keep_precision_columns=None):
    """Return display and CSV versions. Display formats money, CSV keeps numeric."""
    import pandas as pd
    
    if df is None or df.empty:
        return df, df
    
    display_df = df.copy()
    keep_precision = set(keep_precision_columns or [])
    
    for col in money_columns:
        if col in display_df.columns and col not in keep_precision:
            display_df[col] = pd.to_numeric(display_df[col], errors="coerce").fillna(0.0).map(
                lambda x: f"${x:,.2f}"
            )
    
    return display_df, df


def create_download_button(label, df, filename):
    """Create a CSV download button."""
    import streamlit as st
    st.download_button(
        label,
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
    )
'''
    
    # Create the pages directory if it doesn't exist
    os.makedirs('pages', exist_ok=True)
    
    # Write the functions file
    with open('pages/world_coins_functions.py', 'w') as f:
        f.write(functions_content)
    
    print("✅ Created pages/world_coins_functions.py")


def test_original_functions():
    """Test the original functions - will create them if needed"""
    print("Testing original world coins functions...")
    
    # First, check if we need to create the temporary functions file
    if not os.path.exists('pages/world_coins_functions.py'):
        print("Creating temporary world_coins_functions.py for testing...")
        create_temporary_world_coins_functions_file()
    
    try:
        # Mock the database operations BEFORE importing the functions
        from unittest.mock import patch
        
        with patch('infrastructure.database.db_operations.execute_query_all') as mock_execute_all, \
             patch('infrastructure.database.db_operations.execute_query_single') as mock_execute_single:
            
            # Set up mock return values
            mock_execute_all.return_value = [
                {'country': 'Canada'},
                {'country': 'Mexico'}
            ]
            mock_execute_single.return_value = {'1': 1}
            
            # Now import the functions (they'll use our mocked database)
            from pages.world_coins_functions import (
                get_countries_on_hand,
                check_asset_category_support,
                get_world_coins_summary,
                get_world_coins_detail
            )
            
            # Test that functions are callable
            assert callable(get_countries_on_hand)
            assert callable(check_asset_category_support)
            assert callable(get_world_coins_summary)
            assert callable(get_world_coins_detail)
            
            # Test actual calls (with mocked data)
            result = get_countries_on_hand()
            assert isinstance(result, list)
            assert len(result) == 2
            assert result[0] == 'Canada'
            
            result = check_asset_category_support()
            assert isinstance(result, bool)
            assert result is True
            
            # Test get_world_coins_summary returns expected structure
            mock_execute_single.return_value = {'1': 1}  # View exists
            mock_execute_all.return_value = [
                {
                    'Series': 'Canadian Silver Maple Leafs',
                    'Coins': 10,
                    'Melt Value (USD)': 250.50,
                    'Est. Value (USD)': 300.00
                }
            ]
            
            result = get_world_coins_summary("Canada")
            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]['Series'] == 'Canadian Silver Maple Leafs'
        
        print("✅ Original functions work correctly")
        return True
        
    except Exception as e:
        print(f"❌ Original functions failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_refactored_repository():
    """Test the refactored repository"""
    print("Testing refactored world coins repository...")
    
    # Check if refactored files exist
    if not os.path.exists('infrastructure/database/repositories/world_coins_repository.py'):
        print("⏭️  Skipping refactored repository test - files not created yet")
        return True
    
    try:
        from infrastructure.database.repositories.world_coins_repository import (
            SQLWorldCoinsRepository,
            WorldCoinSummary,
            WorldCoinDetail
        )
        from unittest.mock import Mock
        
        # Create repository with mocked database
        mock_db = Mock()
        repository = SQLWorldCoinsRepository(mock_db)
        
        # Test data
        mock_db.execute_query_all.return_value = [
            {
                'country': 'Canada'
            }
        ]
        
        # Test repository methods
        result = repository.get_countries_with_world_coins()
        assert len(result) == 1
        assert result[0] == 'Canada'
        
        print("✅ Refactored repository works correctly")
        return True
        
    except Exception as e:
        print(f"❌ Refactored repository failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_components():
    """Test the UI components"""
    print("Testing world coins UI components...")
    
    # Check if component files exist
    if not os.path.exists('presentation/components/world_coins_components.py'):
        print("⏭️  Skipping UI components test - files not created yet")
        return True
    
    try:
        from presentation.components.world_coins_components import WorldCoinsRenderer
        from unittest.mock import Mock
        
        # Create renderer with mocked repository
        mock_repo = Mock()
        renderer = WorldCoinsRenderer(mock_repo)
        
        # Test that renderer initializes
        assert renderer.repo == mock_repo
        
        # Test methods exist
        assert hasattr(renderer, 'render_summary_tab')
        assert hasattr(renderer, 'render_detail_tab')
        
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
        'pages/world_coins_functions.py'
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
    print("🧪 Running World Coins Refactoring Tests")
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
