# schema_sql.py (excerpted ending with corrected bullion-by-series view)
# NOTE: Keep your existing file; replace the final view definition if you like.

SCHEMA_SQL = r"""
-- ... (all your existing tables, triggers, and views) ...

DROP VIEW IF EXISTS v_inventory_bullion_by_series;
CREATE VIEW v_inventory_bullion_by_series AS
WITH latest AS (SELECT metal, price_per_oz_usd FROM v_latest_spot)
SELECT
  COALESCE(cm.asset_category,'COIN') AS category,
  cm.metal AS metal,
  cm.series AS series,
  MAX(COALESCE(cm.weight_grams,0) / 31.1034768) AS unit_troy_oz,
  MAX((COALESCE(cm.weight_grams,0) * COALESCE(cm.fineness,0)) / 31.1034768) AS unit_fine_oz,
  SUM(l.qty_remaining) AS units_on_hand,
  SUM(l.qty_remaining * (COALESCE(cm.weight_grams,0) / 31.1034768)) AS gross_oz,
  SUM(l.qty_remaining * ((COALESCE(cm.weight_grams,0) * COALESCE(cm.fineness,0)) / 31.1034768)) AS fine_oz,
  ROUND(SUM(
    l.qty_remaining
    * ((COALESCE(cm.weight_grams,0) * COALESCE(cm.fineness,0)) / 31.1034768)
    * (SELECT price_per_oz_usd FROM latest WHERE metal = cm.metal)
  ), 2) AS melt_value_usd
FROM lot l
JOIN coin_type ct ON ct.id = l.coin_type_id
JOIN coin_master cm ON cm.id = ct.master_id
WHERE l.qty_remaining > 0 AND COALESCE(cm.asset_category,'COIN') IN ('ROUND','BAR')
GROUP BY COALESCE(cm.asset_category,'COIN'), cm.metal, cm.series;
"""
