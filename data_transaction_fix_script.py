# cleanup_date_discrepancies.py
from infrastructure.database.db_operations import execute_query_all, execute_update


def find_date_discrepancies():
    """Find all lots where acquired_date doesn't match tx_date"""
    query = """
    SELECT 
        t.id as tx_id,
        t.tx_date,
        l.id as lot_id,
        l.acquired_date,
        cm.series,
        ct.year,
        ct.mint_mark
    FROM lot l
    JOIN tx_line tl ON tl.id = l.acquisition_line_id
    JOIN tx t ON t.id = tl.tx_id
    JOIN coin_type ct ON ct.id = l.coin_type_id
    JOIN coin_master cm ON cm.id = ct.master_id
    WHERE l.acquired_date != t.tx_date
    ORDER BY t.tx_date DESC
    """
    return execute_query_all(query)


def fix_date_discrepancies(dry_run=True):
    """Fix all date discrepancies"""
    discrepancies = find_date_discrepancies()

    if not discrepancies:
        print("No discrepancies found!")
        return

    print(f"Found {len(discrepancies)} discrepancies:\n")

    for disc in discrepancies:
        print(f"Lot #{disc['lot_id']}: {disc['series']} {disc['year']} {disc['mint_mark'] or ''}")
        print(f"  Current acquired_date: {disc['acquired_date']}")
        print(f"  Transaction date: {disc['tx_date']}")
        print(f"  Will update to: {disc['tx_date']}\n")

    if dry_run:
        print("DRY RUN - No changes made. Set dry_run=False to apply fixes.")
        return

    # Apply fixes
    for disc in discrepancies:
        execute_update(
            "UPDATE lot SET acquired_date = ? WHERE id = ?",
            (disc['tx_date'], disc['lot_id'])
        )

    print(f"Fixed {len(discrepancies)} lots!")


# Run this:
if __name__ == "__main__":
    # fix_date_discrepancies(dry_run=True)  # First run to preview
    fix_date_discrepancies(dry_run=False)  # Uncomment to actually fix