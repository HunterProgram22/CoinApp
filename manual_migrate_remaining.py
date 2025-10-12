"""
Manual migration for the 3 remaining tables.
This bypasses the cursor wrapper issues.
"""

import sys
import sqlite3
import os

sys.path.insert(0, '.')

# Set to use Turso
os.environ['DB_TYPE'] = 'turso'

from infrastructure.database.db import get_conn


def migrate_table(sqlite_path: str, table_name: str):
    """Migrate a single table from SQLite to Turso."""

    print(f"\n{'=' * 60}")
    print(f"Migrating: {table_name}")
    print(f"{'=' * 60}")

    # Connect to SQLite and read data
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row

    try:
        rows = sqlite_conn.execute(f"SELECT * FROM {table_name}").fetchall()
        print(f"Found {len(rows)} rows in SQLite")

        if len(rows) == 0:
            print(f"⏭️  No data to migrate")
            return True

        # Get column names
        columns = list(rows[0].keys())
        print(f"Columns: {', '.join(columns)}")

    except sqlite3.OperationalError as e:
        print(f"❌ Error reading from SQLite: {e}")
        return False
    finally:
        sqlite_conn.close()

    # Connect to Turso and insert data
    print(f"\nConnecting to Turso...")

    try:
        with get_conn() as turso_conn:
            print("✓ Connected")

            # Clear existing data (in case of retry)
            try:
                turso_conn.execute(f"DELETE FROM {table_name}")
                print("✓ Cleared any existing data")
            except Exception as e:
                print(f"⚠️  Could not clear table: {e}")

            # Prepare INSERT statement
            placeholders = ','.join(['?' for _ in columns])
            insert_sql = f"INSERT INTO {table_name} ({','.join(columns)}) VALUES ({placeholders})"

            # Insert each row
            success_count = 0
            error_count = 0

            for i, row in enumerate(rows, 1):
                try:
                    values = [row[col] for col in columns]
                    turso_conn.execute(insert_sql, values)
                    success_count += 1

                    # Progress indicator
                    if i % 10 == 0 or i == len(rows):
                        print(f"  Progress: {i}/{len(rows)} rows...", end='\r')

                except Exception as e:
                    error_count += 1
                    print(f"\n❌ Error on row {i}: {e}")
                    print(f"   Values: {values[:3]}..." if len(
                        values) > 3 else f"   Values: {values}")

            print(f"\n\n{'=' * 60}")
            print(f"✅ Successfully migrated {success_count}/{len(rows)} rows")
            if error_count > 0:
                print(f"⚠️  {error_count} rows failed")
            print(f"{'=' * 60}")

            return error_count == 0

    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_table(table_name: str):
    """Verify data was migrated correctly."""
    print(f"\nVerifying {table_name}...")

    try:
        with get_conn() as conn:
            result = conn.execute(f"SELECT COUNT(*) as count FROM {table_name}").fetchone()
            count = result['count'] if result else 0
            print(f"✓ {table_name}: {count} rows in Turso")
            return count
    except Exception as e:
        print(f"❌ Error verifying {table_name}: {e}")
        return 0


def main():
    """Migrate the 3 remaining tables."""

    print("\n" + "🔧" * 30)
    print("MANUAL MIGRATION: Remaining 3 Tables")
    print("🔧" * 30 + "\n")

    sqlite_path = "data/coinapp.sqlite"

    tables = [
        'proof_set_master',
        'type_set_metadata',
        'proof_set_inventory'
    ]

    print(f"SQLite source: {sqlite_path}")
    print(f"Turso target: From secrets.toml\n")

    response = input("Proceed with migration? (yes/no): ").strip().lower()

    if response not in ['yes', 'y']:
        print("\n❌ Migration cancelled")
        return

    results = {}

    # Migrate each table
    for table in tables:
        success = migrate_table(sqlite_path, table)
        results[table] = success

    # Verify all tables
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    for table in tables:
        count = verify_table(table)
        results[table] = (results[table], count)

    # Summary
    print("\n" + "=" * 60)
    print("MIGRATION SUMMARY")
    print("=" * 60)

    all_success = True
    for table, (success, count) in results.items():
        status = "✅" if success and count > 0 else "⚠️" if count > 0 else "❌"
        print(f"{status} {table:30s} {count:6d} rows")
        if not success:
            all_success = False

    if all_success:
        print("\n🎉 All tables migrated successfully!")
    else:
        print("\n⚠️  Some tables had issues. Check errors above.")

    print("\nYou can now test your app with all data migrated.")


if __name__ == "__main__":
    main()
