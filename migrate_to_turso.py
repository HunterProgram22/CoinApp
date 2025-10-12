"""
Data Migration Script: SQLite → Turso
Migrates all data from local SQLite database to Turso cloud database.
"""

import sys
import sqlite3
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, '.')


def export_sqlite_data(sqlite_path: str = "data/coinapp.sqlite"):
    """Export all data from SQLite to JSON."""
    print("=" * 60)
    print("STEP 1: Exporting data from SQLite")
    print("=" * 60)

    if not Path(sqlite_path).exists():
        print(f"❌ SQLite database not found at: {sqlite_path}")
        return None

    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row

    # Define tables in dependency order (parents before children)
    tables = [
        # No dependencies
        'party',
        'storage_location',
        'tag',
        'coin_master',
        'type_set',
        'proof_set_master',

        # Depends on coin_master
        'coin_type',

        # Depends on coin_type
        'guide_price',
        'image',
        'coin_type_tag',
        'type_set_member',
        'proof_set_contents',

        # Depends on party
        'tx',

        # Depends on tx and coin_type
        'tx_line',

        # Depends on tx_line and coin_type
        'lot',

        # Depends on lot and tx_line
        'lot_relief',

        # Depends on lot
        'specimen',

        # Other tables
        'metal_price',
        'fx_rate',
        'series_code',
        'type_set_metadata',
        'proof_set_inventory',
        'proof_set_values',
    ]

    export_data = {}
    total_rows = 0

    for table in tables:
        try:
            cursor = conn.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            export_data[table] = [dict(row) for row in rows]
            row_count = len(export_data[table])
            total_rows += row_count

            if row_count > 0:
                print(f"✓ {table:30s} {row_count:6d} rows")
            else:
                print(f"  {table:30s} {row_count:6d} rows (empty)")
        except sqlite3.OperationalError as e:
            # Table doesn't exist, skip it
            print(f"⚠ {table:30s} (table not found, skipping)")
            export_data[table] = []

    conn.close()

    # Save to file
    export_file = f"turso_migration_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(export_file, 'w') as f:
        json.dump(export_data, f, indent=2, default=str)

    print(f"\n✅ Exported {total_rows:,} total rows to: {export_file}")
    return export_file


def import_to_turso(export_file: str):
    """Import data from JSON to Turso."""
    print("\n" + "=" * 60)
    print("STEP 2: Importing data to Turso")
    print("=" * 60)

    # Load export file
    with open(export_file, 'r') as f:
        data = json.load(f)

    # Set environment to use Turso
    import os
    os.environ['DB_TYPE'] = 'turso'

    # Import after setting env var
    from infrastructure.database.db import get_conn

    print("\nConnecting to Turso...")

    with get_conn() as conn:
        print("✓ Connected to Turso\n")

        total_imported = 0
        errors = []

        # Import in correct order
        for table, rows in data.items():
            if not rows:
                print(f"⏭️  {table:30s} (no data)")
                continue

            try:
                # Get column names from first row
                columns = list(rows[0].keys())
                placeholders = ','.join(['?' for _ in columns])
                insert_sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})"

                # Insert all rows
                for row in rows:
                    values = [row[col] for col in columns]
                    conn.execute(insert_sql, values)

                total_imported += len(rows)
                print(f"✓ {table:30s} {len(rows):6d} rows imported")

            except Exception as e:
                error_msg = f"Error importing {table}: {e}"
                errors.append(error_msg)
                print(f"❌ {table:30s} FAILED: {e}")

        print(f"\n{'=' * 60}")
        print(f"✅ Successfully imported {total_imported:,} rows")

        if errors:
            print(f"⚠️  {len(errors)} table(s) had errors:")
            for error in errors:
                print(f"   • {error}")
        else:
            print("🎉 All tables imported successfully!")


def verify_migration():
    """Verify data was migrated correctly."""
    print("\n" + "=" * 60)
    print("STEP 3: Verifying Migration")
    print("=" * 60)

    import os
    os.environ['DB_TYPE'] = 'turso'

    from infrastructure.database.db import get_conn

    with get_conn() as conn:
        # Check key tables
        checks = [
            ("Coin Masters", "SELECT COUNT(*) as count FROM coin_master"),
            ("Coin Types", "SELECT COUNT(*) as count FROM coin_type"),
            ("Transactions", "SELECT COUNT(*) as count FROM tx"),
            ("Transaction Lines", "SELECT COUNT(*) as count FROM tx_line"),
            ("Lots", "SELECT COUNT(*) as count FROM lot"),
            ("Parties", "SELECT COUNT(*) as count FROM party"),
        ]

        print("\nRecord counts in Turso:")
        for name, query in checks:
            try:
                result = conn.execute(query).fetchone()
                count = result['count'] if result else 0
                print(f"  {name:20s} {count:6d}")
            except Exception as e:
                print(f"  {name:20s} ERROR: {e}")

        # Check portfolio summary
        try:
            result = conn.execute(
                "SELECT total_coins, total_estimated_value_usd FROM v_portfolio_value_summary"
            ).fetchone()

            if result:
                coins = result['total_coins'] or 0
                value = result['total_estimated_value_usd'] or 0
                print(f"\n💰 Portfolio Summary:")
                print(f"   Total Coins: {coins:,}")
                print(f"   Total Value: ${value:,.2f}")
            else:
                print("\n⚠️  Portfolio summary view returned no data")
        except Exception as e:
            print(f"\n⚠️  Could not query portfolio summary: {e}")


def main():
    """Main migration workflow."""
    print("\n" + "🚀" * 30)
    print("COIN TRACKER DATA MIGRATION: SQLite → Turso")
    print("🚀" * 30 + "\n")

    # Confirm user wants to proceed
    print("This will:")
    print("  1. Export all data from your SQLite database")
    print("  2. Import all data into your Turso database")
    print("  3. Verify the migration was successful")
    print("\n⚠️  WARNING: This will ADD data to Turso (not replace)")
    print("   If you already have data in Turso, you may get duplicates!\n")

    response = input("Do you want to proceed? (yes/no): ").strip().lower()

    if response not in ['yes', 'y']:
        print("\n❌ Migration cancelled")
        return

    try:
        # Step 1: Export from SQLite
        export_file = export_sqlite_data()

        if not export_file:
            print("\n❌ Export failed. Migration aborted.")
            return

        # Step 2: Import to Turso
        import_to_turso(export_file)

        # Step 3: Verify
        verify_migration()

        print("\n" + "=" * 60)
        print("🎉 MIGRATION COMPLETE!")
        print("=" * 60)
        print(f"\nBackup file saved: {export_file}")
        print("You can now use your app with Turso!")
        print("\nNext steps:")
        print("  1. Test your app thoroughly")
        print("  2. Keep the backup file safe")
        print("  3. Once confirmed working, you can archive your SQLite file")

    except Exception as e:
        print(f"\n❌ Migration failed with error:")
        print(f"   {e}")
        import traceback
        traceback.print_exc()
        return


if __name__ == "__main__":
    main()
