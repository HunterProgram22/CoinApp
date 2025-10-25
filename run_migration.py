from db import get_conn
from infrastructure.database.migrations.migrate_001_materialize_lot_values import run_migration

with get_conn() as conn:
    success = run_migration(conn)
    if success:
        print("✅ Migration successful!")
    else:
        print("❌ Migration failed!")
