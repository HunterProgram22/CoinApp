-- patches/schema_bullion_category.sql
-- Add category to distinguish COIN vs ROUND vs BAR
ALTER TABLE coin_master
  ADD COLUMN asset_category TEXT NOT NULL DEFAULT 'COIN'
  CHECK (asset_category IN ('COIN','ROUND','BAR'));

-- Optional: legal tender flag (1/0). Defaults to NULL (unknown).
ALTER TABLE coin_master
  ADD COLUMN legal_tender INTEGER;

-- Bullion summaries (counts, weights, melt value)
CREATE VIEW IF NOT EXISTS v_inventory_bullion_by_series AS
SELECT
  cm.asset_category AS category,
  cm.metal,
  cm.series,
  ROUND(cm.weight_grams/31.1034768, 4) AS unit_troy_oz,
  ROUND(cm.weight_grams*COALESCE(cm.fineness,0)/31.1034768, 4) AS unit_fine_oz,
  SUM(l.qty_remaining) AS units_on_hand,
  ROUND(SUM(l.qty_remaining * cm.weight_grams/31.1034768), 4) AS gross_oz,
  ROUND(SUM(l.qty_remaining * cm.weight_grams*COALESCE(cm.fineness,0)/31.1034768), 4) AS fine_oz,
  ROUND(SUM(l.qty_remaining * ((cm.weight_grams*COALESCE(cm.fineness,0))/31.1034768) *
           (SELECT price_per_oz_usd FROM v_latest_spot s WHERE s.metal = cm.metal)), 2) AS melt_value_usd
FROM lot l
JOIN coin_type ct ON ct.id = l.coin_type_id
JOIN coin_master cm ON cm.id = ct.master_id
WHERE l.qty_remaining > 0 AND cm.asset_category IN ('ROUND','BAR')
GROUP BY cm.asset_category, cm.metal, cm.series, unit_troy_oz, unit_fine_oz;

CREATE VIEW IF NOT EXISTS v_inventory_bullion_by_category AS
SELECT
  cm.asset_category AS category,
  cm.metal,
  SUM(l.qty_remaining) AS units_on_hand,
  ROUND(SUM(l.qty_remaining * cm.weight_grams/31.1034768), 4) AS gross_oz,
  ROUND(SUM(l.qty_remaining * cm.weight_grams*COALESCE(cm.fineness,0)/31.1034768), 4) AS fine_oz,
  ROUND(SUM(l.qty_remaining * ((cm.weight_grams*COALESCE(cm.fineness,0))/31.1034768) *
           (SELECT price_per_oz_usd FROM v_latest_spot s WHERE s.metal = cm.metal)), 2) AS melt_value_usd
FROM lot l
JOIN coin_type ct ON ct.id = l.coin_type_id
JOIN coin_master cm ON cm.id = ct.master_id
WHERE l.qty_remaining > 0 AND cm.asset_category IN ('ROUND','BAR')
GROUP BY cm.asset_category, cm.metal;