
-- schema_patch_bullion.sql
-- Purpose: add coin_master.asset_category and (re)create bullion inventory views.
-- Safe to run on your existing database without losing data.
-- If the ALTER fails with "duplicate column name", just run the view section.

BEGIN TRANSACTION;

-- 1) Add asset_category to coin_master (default 'COIN').
--    Values recommended: 'COIN','ROUND','BAR'
--    Note: Some SQLite builds don't support IF NOT EXISTS on ADD COLUMN.
--    If this next line errors with 'duplicate column name', skip to section 2.
ALTER TABLE coin_master
  ADD COLUMN asset_category TEXT NOT NULL DEFAULT 'COIN'
  CHECK (asset_category IN ('COIN','ROUND','BAR'));

-- 2) (Re)create bullion views used by the Bullion page & queries.py
DROP VIEW IF EXISTS v_inventory_bullion_by_category;
CREATE VIEW v_inventory_bullion_by_category AS
WITH latest AS (
  SELECT metal, price_per_oz_usd FROM v_latest_spot
)
SELECT
  cm.asset_category AS category,
  cm.metal,
  SUM(l.qty_remaining) AS units_on_hand,
  ROUND(SUM(l.qty_remaining * cm.weight_grams) / 31.1034768, 4) AS gross_oz,
  ROUND(SUM(l.qty_remaining * cm.weight_grams * COALESCE(cm.fineness,0)) / 31.1034768, 4) AS fine_oz,
  ROUND(SUM(l.qty_remaining
       * (cm.weight_grams * COALESCE(cm.fineness,0)) / 31.1034768
       * (SELECT price_per_oz_usd FROM latest WHERE metal = cm.metal)
  ), 2) AS melt_value_usd
FROM lot l
JOIN coin_type ct ON ct.id = l.coin_type_id
JOIN coin_master cm ON cm.id = ct.master_id
WHERE l.qty_remaining > 0
  AND cm.metal IN ('Ag','Au','Pt','Pd')
GROUP BY cm.asset_category, cm.metal;

DROP VIEW IF EXISTS v_inventory_bullion_details;
CREATE VIEW v_inventory_bullion_details AS
WITH latest AS (
  SELECT metal, price_per_oz_usd FROM v_latest_spot
)
SELECT
  l.id AS lot_id,
  cm.asset_category AS category,
  cm.metal,
  cm.series, ct.year, ct.mint_mark, COALESCE(ct.variety,'') AS variety,
  l.qty_remaining,
  ROUND((cm.weight_grams) / 31.1034768, 4) AS gross_oz_per_unit,
  ROUND((cm.weight_grams * COALESCE(cm.fineness,0)) / 31.1034768, 4) AS fine_oz_per_unit,
  ROUND(l.qty_remaining * (cm.weight_grams * COALESCE(cm.fineness,0)) / 31.1034768, 4) AS fine_oz_total,
  ROUND((cm.weight_grams * COALESCE(cm.fineness,0)) / 31.1034768
        * (SELECT price_per_oz_usd FROM latest WHERE metal = cm.metal), 2) AS melt_unit_value_usd,
  ROUND(l.qty_remaining * (cm.weight_grams * COALESCE(cm.fineness,0)) / 31.1034768
        * (SELECT price_per_oz_usd FROM latest WHERE metal = cm.metal), 2) AS melt_total_value_usd
FROM lot l
JOIN coin_type ct ON ct.id = l.coin_type_id
JOIN coin_master cm ON cm.id = ct.master_id
WHERE l.qty_remaining > 0
  AND cm.metal IN ('Ag','Au','Pt','Pd');

COMMIT;
