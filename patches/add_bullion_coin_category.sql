
-- patches/add_bullion_coin_category.sql
-- Treat "Bullion Coin" as bullion alongside "Round" and "Bar" in summary views.
PRAGMA foreign_keys=ON;

DROP VIEW IF EXISTS v_inventory_bullion_by_category;
CREATE VIEW v_inventory_bullion_by_category AS
WITH latest AS (
  SELECT metal, price_per_oz_usd
  FROM v_latest_spot
)
SELECT
  cm.asset_category AS category,
  cm.metal          AS metal,
  SUM(l.qty_remaining) AS units_on_hand,
  ROUND(SUM(l.qty_remaining * (cm.weight_grams/31.1034768)), 6) AS gross_oz,
  ROUND(SUM(l.qty_remaining * ((cm.weight_grams*COALESCE(cm.fineness,0))/31.1034768)), 6) AS fine_oz,
  ROUND(SUM(
    l.qty_remaining *
    ((cm.weight_grams*COALESCE(cm.fineness,0))/31.1034768) *
    (SELECT price_per_oz_usd FROM latest s WHERE s.metal = cm.metal)
  ), 2) AS melt_value_usd
FROM lot l
JOIN coin_type ct ON ct.id = l.coin_type_id
JOIN coin_master cm ON cm.id = ct.master_id
WHERE l.qty_remaining > 0
  AND cm.asset_category IN ('Round','Bar','Bullion Coin')
GROUP BY cm.asset_category, cm.metal;

DROP VIEW IF EXISTS v_inventory_bullion_by_series;
CREATE VIEW v_inventory_bullion_by_series AS
WITH latest AS (
  SELECT metal, price_per_oz_usd
  FROM v_latest_spot
)
SELECT
  cm.asset_category AS category,
  cm.metal          AS metal,
  cm.series         AS series,
  ROUND(cm.weight_grams/31.1034768, 6) AS unit_troy_oz,
  ROUND((cm.weight_grams*COALESCE(cm.fineness,0))/31.1034768, 6) AS unit_fine_oz,
  SUM(l.qty_remaining) AS units_on_hand,
  ROUND(SUM(l.qty_remaining * (cm.weight_grams/31.1034768)), 6) AS gross_oz,
  ROUND(SUM(l.qty_remaining * ((cm.weight_grams*COALESCE(cm.fineness,0))/31.1034768)), 6) AS fine_oz,
  ROUND(SUM(
    l.qty_remaining *
    ((cm.weight_grams*COALESCE(cm.fineness,0))/31.1034768) *
    (SELECT price_per_oz_usd FROM latest s WHERE s.metal = cm.metal)
  ), 2) AS melt_value_usd
FROM lot l
JOIN coin_type ct ON ct.id = l.coin_type_id
JOIN coin_master cm ON cm.id = ct.master_id
WHERE l.qty_remaining > 0
  AND cm.asset_category IN ('Round','Bar','Bullion Coin')
GROUP BY cm.asset_category, cm.metal, cm.series, unit_troy_oz, unit_fine_oz;
