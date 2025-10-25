"""
Migration 001: Replace v_lot_value_details view with cached table

Purpose: Reduce Turso row reads from 200M/month to <1M/month by eliminating
expensive correlated subqueries in the view.

This migration:
1. Drops the existing v_lot_value_details view
2. Creates a lot_value_cache table to store pre-calculated values
3. Creates a compatibility view so existing queries work unchanged
"""

MIGRATION_SQL = """
-- ============================================================
-- Migration 001: Materialize Lot Values
-- ============================================================

-- Step 1: Drop the expensive view
DROP VIEW IF EXISTS v_lot_value_details;

-- Step 2: Create materialized table
CREATE TABLE IF NOT EXISTS lot_value_cache (
    lot_id INTEGER PRIMARY KEY,
    series TEXT NOT NULL,
    year INTEGER,
    mint_mark TEXT DEFAULT '',
    variety TEXT DEFAULT '',
    qty_remaining INTEGER NOT NULL,
    valuation_method TEXT,
    grade_for_pricing TEXT,
    melt_unit_value REAL,
    guide_unit_value REAL,
    chosen_unit_value REAL NOT NULL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (lot_id) REFERENCES lot(id) ON DELETE CASCADE
);

-- Step 3: Create indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_lvc_series ON lot_value_cache(series);
CREATE INDEX IF NOT EXISTS idx_lvc_qty_remaining ON lot_value_cache(qty_remaining);
CREATE INDEX IF NOT EXISTS idx_lvc_last_updated ON lot_value_cache(last_updated);
CREATE INDEX IF NOT EXISTS idx_lvc_valuation_method ON lot_value_cache(valuation_method);

-- Step 4: Create compatibility view (so existing queries work unchanged)
CREATE VIEW IF NOT EXISTS v_lot_value_details AS
SELECT 
    lot_id,
    series,
    year,
    mint_mark,
    variety,
    qty_remaining,
    valuation_method,
    grade_for_pricing,
    melt_unit_value,
    guide_unit_value,
    chosen_unit_value
FROM lot_value_cache;
"""

ROLLBACK_SQL = """
-- Rollback: Drop cache table and recreate original view
DROP VIEW IF EXISTS v_lot_value_details;
DROP TABLE IF EXISTS lot_value_cache;

-- Recreate original expensive view
-- (Copy from your original schema_sql.py if needed to rollback)
"""


def run_migration(conn):
    """
    Run the migration on the given database connection.
    
    Args:
        conn: Database connection (sqlite3.Connection or SQLAlchemy connection)
        
    Returns:
        bool: True if successful
    """
    try:
        # For SQLite connections
        if hasattr(conn, 'executescript'):
            conn.executescript(MIGRATION_SQL)
            conn.commit()
        # For SQLAlchemy connections
        else:
            conn.execute(MIGRATION_SQL)
            
        print("✅ Migration 001 completed successfully")
        print("   - Dropped v_lot_value_details view")
        print("   - Created lot_value_cache table")
        print("   - Created compatibility view")
        return True
        
    except Exception as e:
        print(f"❌ Migration 001 failed: {e}")
        return False


def rollback_migration(conn):
    """
    Rollback the migration (emergency use only).
    
    Args:
        conn: Database connection
        
    Returns:
        bool: True if successful
    """
    try:
        if hasattr(conn, 'executescript'):
            conn.executescript(ROLLBACK_SQL)
            conn.commit()
        else:
            conn.execute(ROLLBACK_SQL)
            
        print("✅ Migration 001 rolled back")
        return True
        
    except Exception as e:
        print(f"❌ Rollback failed: {e}")
        return False


if __name__ == "__main__":
    # Test the migration locally
    import sqlite3
    from pathlib import Path
    
    # Use a test database
    test_db = Path("data/test_migration.sqlite")
    test_db.parent.mkdir(exist_ok=True)
    
    conn = sqlite3.connect(test_db)
    
    print("Running migration test...")
    success = run_migration(conn)
    
    if success:
        print("\n✅ Migration test passed!")
        print(f"   Test database: {test_db}")
        print("   You can inspect it with: sqlite3 data/test_migration.sqlite")
    else:
        print("\n❌ Migration test failed!")
    
    conn.close()
