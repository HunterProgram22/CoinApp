# schema_sql.py - PostgreSQL Compatible Version

SCHEMA_SQL = r"""
/* ---------- Reference: coin master & types ---------- */
CREATE TABLE IF NOT EXISTS coin_master (
  id              SERIAL PRIMARY KEY,
  country         TEXT NOT NULL,
  denomination    TEXT NOT NULL,
  series          TEXT NOT NULL,
  metal           TEXT,
  fineness        NUMERIC(10,6),
  weight_grams    NUMERIC(10,3),
  diameter_mm     NUMERIC(10,2),
  thickness_mm    NUMERIC(10,3),
  edge            TEXT,
  years_start     INTEGER,
  years_end       INTEGER,
  asset_category  TEXT NOT NULL DEFAULT 'COIN',
  numista_url     TEXT,
  ngc_url         TEXT,
  pcgs_url        TEXT,
  notes           TEXT,
  UNIQUE(country, denomination, series)
);
CREATE INDEX IF NOT EXISTS idx_coin_master_series ON coin_master(series);
CREATE INDEX IF NOT EXISTS idx_coin_master_numista_url ON coin_master(numista_url);

CREATE TABLE IF NOT EXISTS coin_type (
  id              SERIAL PRIMARY KEY,
  master_id       INTEGER NOT NULL REFERENCES coin_master(id) ON DELETE CASCADE,
  year            INTEGER NOT NULL,
  mint_mark       TEXT DEFAULT '',
  variety         TEXT DEFAULT '',
  mintage         INTEGER,
  is_proof        BOOLEAN NOT NULL DEFAULT FALSE,
  designer        TEXT,
  obv_desc        TEXT,
  rev_desc        TEXT,
  UNIQUE(master_id, year, mint_mark, variety)
);
CREATE INDEX IF NOT EXISTS idx_coin_type_master_id ON coin_type(master_id);
CREATE INDEX IF NOT EXISTS idx_coin_type_year ON coin_type(year);

/* ---------- Parties & storage ---------- */
CREATE TABLE IF NOT EXISTS party (
  id              SERIAL PRIMARY KEY,
  name            TEXT NOT NULL,
  kind            TEXT,
  contact         TEXT
);

CREATE TABLE IF NOT EXISTS storage_location (
  id              SERIAL PRIMARY KEY,
  name            TEXT NOT NULL,
  category        TEXT,
  description     TEXT
);

/* ---------- Transactions & lines ---------- */
CREATE TABLE IF NOT EXISTS tx (
  id              SERIAL PRIMARY KEY,
  tx_date         DATE NOT NULL,
  tx_type         TEXT NOT NULL CHECK (tx_type IN ('BUY','SELL','FEE','ADJUST','GIFT_IN','GIFT_OUT','TRANSFER')),
  party_id        INTEGER REFERENCES party(id) ON DELETE SET NULL,
  currency        TEXT NOT NULL DEFAULT 'USD',
  shipping        NUMERIC(10,2) DEFAULT 0.00,
  tax             NUMERIC(10,2) DEFAULT 0.00,
  fees            NUMERIC(10,2) DEFAULT 0.00,
  notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_tx_date ON tx(tx_date);
CREATE INDEX IF NOT EXISTS idx_tx_party_id ON tx(party_id);

CREATE TABLE IF NOT EXISTS tx_line (
  id              SERIAL PRIMARY KEY,
  tx_id           INTEGER NOT NULL REFERENCES tx(id) ON DELETE CASCADE,
  coin_type_id    INTEGER NOT NULL REFERENCES coin_type(id) ON DELETE RESTRICT,
  quantity        INTEGER NOT NULL CHECK (quantity <> 0),
  unit_price      NUMERIC(10,2),
  grade_company   TEXT,
  grade_text      TEXT,
  numeric_grade   NUMERIC(4,1),
  slab_cert       TEXT,
  condition_notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_tx_line_tx_id ON tx_line(tx_id);
CREATE INDEX IF NOT EXISTS idx_tx_line_coin_type_id ON tx_line(coin_type_id);

/* ---------- Inventory lots & relief ---------- */
CREATE TABLE IF NOT EXISTS lot (
  id                      SERIAL PRIMARY KEY,
  acquisition_line_id     INTEGER NOT NULL REFERENCES tx_line(id) ON DELETE CASCADE,
  coin_type_id            INTEGER NOT NULL REFERENCES coin_type(id) ON DELETE RESTRICT,
  acquired_date           DATE NOT NULL,
  qty_acquired            INTEGER NOT NULL CHECK (qty_acquired > 0),
  qty_remaining           INTEGER NOT NULL CHECK (qty_remaining >= 0),
  unit_cost               NUMERIC(10,2) NOT NULL,
  storage_location_id     INTEGER REFERENCES storage_location(id) ON DELETE SET NULL,

  purchase_grade_company  TEXT,
  purchase_grade_text     TEXT,
  purchase_numeric_grade  NUMERIC(4,1),
  slab_cert               TEXT,

  estimated_grade_text    TEXT,
  estimated_numeric_grade NUMERIC(4,1),

  valuation_method        TEXT NOT NULL DEFAULT 'AUTO'
                           CHECK (valuation_method IN ('AUTO','MELT_ONLY','GUIDE_ONLY','MANUAL')),
  manual_est_unit_value   NUMERIC(10,2),

  status                  TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','CLOSED')),
  notes                   TEXT
);

CREATE INDEX IF NOT EXISTS idx_lot_acquisition_line_id ON lot(acquisition_line_id);
CREATE INDEX IF NOT EXISTS idx_lot_coin_type_id ON lot(coin_type_id);
CREATE INDEX IF NOT EXISTS idx_lot_storage_location_id ON lot(storage_location_id);
CREATE INDEX IF NOT EXISTS idx_lot_status ON lot(status);
CREATE INDEX IF NOT EXISTS idx_lot_acquired_date ON lot(acquired_date);

/* Relief mapping */
CREATE TABLE IF NOT EXISTS lot_relief (
  id                SERIAL PRIMARY KEY,
  lot_id            INTEGER NOT NULL REFERENCES lot(id) ON DELETE CASCADE,
  sell_line_id      INTEGER NOT NULL REFERENCES tx_line(id) ON DELETE CASCADE,
  quantity          INTEGER NOT NULL CHECK (quantity > 0),
  proceeds_per_unit NUMERIC(10,2)
);

CREATE INDEX IF NOT EXISTS idx_lot_relief_lot_id ON lot_relief(lot_id);
CREATE INDEX IF NOT EXISTS idx_lot_relief_sell_line_id ON lot_relief(sell_line_id);

/* ---------- PostgreSQL Functions for Triggers ---------- */
CREATE OR REPLACE FUNCTION check_lot_quantity()
RETURNS TRIGGER AS $$
BEGIN
  IF (SELECT qty_remaining FROM lot WHERE id = NEW.lot_id) < NEW.quantity THEN
    RAISE EXCEPTION 'Insufficient quantity in lot';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION update_lot_after_relief_insert()
RETURNS TRIGGER AS $$
BEGIN
  UPDATE lot 
  SET qty_remaining = qty_remaining - NEW.quantity,
      status = CASE WHEN qty_remaining - NEW.quantity = 0 THEN 'CLOSED' ELSE status END
  WHERE id = NEW.lot_id;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION update_lot_after_relief_delete()
RETURNS TRIGGER AS $$
BEGIN
  UPDATE lot 
  SET qty_remaining = qty_remaining + OLD.quantity,
      status = CASE WHEN qty_remaining + OLD.quantity > 0 THEN 'OPEN' ELSE status END
  WHERE id = OLD.lot_id;
  RETURN OLD;
END;
$$ LANGUAGE plpgsql;

/* PostgreSQL Triggers */
DROP TRIGGER IF EXISTS trg_lot_relief_before_insert ON lot_relief;
CREATE TRIGGER trg_lot_relief_before_insert
  BEFORE INSERT ON lot_relief
  FOR EACH ROW
  EXECUTE FUNCTION check_lot_quantity();

DROP TRIGGER IF EXISTS trg_lot_relief_after_insert ON lot_relief;
CREATE TRIGGER trg_lot_relief_after_insert
  AFTER INSERT ON lot_relief
  FOR EACH ROW
  EXECUTE FUNCTION update_lot_after_relief_insert();

DROP TRIGGER IF EXISTS trg_lot_relief_after_delete ON lot_relief;
CREATE TRIGGER trg_lot_relief_after_delete
  AFTER DELETE ON lot_relief
  FOR EACH ROW
  EXECUTE FUNCTION update_lot_after_relief_delete();

/* ---------- Pricing ---------- */
CREATE TABLE IF NOT EXISTS metal_price (
  id               SERIAL PRIMARY KEY,
  metal            TEXT NOT NULL,
  price_per_oz_usd NUMERIC(10,2) NOT NULL,
  quoted_at_utc    TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_metal_price_metal ON metal_price(metal);
CREATE INDEX IF NOT EXISTS idx_metal_price_time ON metal_price(quoted_at_utc DESC);

CREATE TABLE IF NOT EXISTS fx_rate (
  id              SERIAL PRIMARY KEY,
  base_ccy        TEXT NOT NULL,
  quote_ccy       TEXT NOT NULL,
  rate            NUMERIC(15,6) NOT NULL,
  quoted_at_utc   TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fx_rate_pair ON fx_rate(base_ccy, quote_ccy);
CREATE INDEX IF NOT EXISTS idx_fx_rate_time ON fx_rate(quoted_at_utc DESC);

/* ---------- Org ---------- */
CREATE TABLE IF NOT EXISTS tag (
  id              SERIAL PRIMARY KEY,
  name            TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS coin_type_tag (
  coin_type_id    INTEGER NOT NULL REFERENCES coin_type(id) ON DELETE CASCADE,
  tag_id          INTEGER NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
  PRIMARY KEY (coin_type_id, tag_id)
);

CREATE TABLE IF NOT EXISTS image (
  id              SERIAL PRIMARY KEY,
  coin_type_id    INTEGER REFERENCES coin_type(id) ON DELETE CASCADE,
  lot_id          INTEGER REFERENCES lot(id) ON DELETE CASCADE,
  file_path       TEXT NOT NULL,
  caption         TEXT
);

CREATE INDEX IF NOT EXISTS idx_image_coin_type_id ON image(coin_type_id);
CREATE INDEX IF NOT EXISTS idx_image_lot_id ON image(lot_id);

/* ---------- Guide pricing ---------- */
CREATE TABLE IF NOT EXISTS guide_price (
  id            SERIAL PRIMARY KEY,
  coin_type_id  INTEGER NOT NULL REFERENCES coin_type(id) ON DELETE CASCADE,
  grade_text    TEXT NOT NULL,
  numeric_grade NUMERIC(4,1),
  price_usd     NUMERIC(10,2) NOT NULL,
  as_of         DATE NOT NULL,
  source        TEXT,
  UNIQUE (coin_type_id, grade_text, as_of)
);
CREATE INDEX IF NOT EXISTS idx_guide_price_coin_type_id ON guide_price(coin_type_id);
CREATE INDEX IF NOT EXISTS idx_guide_price_grade ON guide_price(coin_type_id, grade_text);
CREATE INDEX IF NOT EXISTS idx_guide_price_date ON guide_price(as_of DESC);

/* ---------- Views ---------- */

/* Latest spot per metal */
CREATE OR REPLACE VIEW v_latest_spot AS
SELECT metal, price_per_oz_usd
FROM metal_price mp
WHERE quoted_at_utc = (
  SELECT MAX(quoted_at_utc) FROM metal_price x WHERE x.metal = mp.metal
);

/* Latest guide per grade */
CREATE OR REPLACE VIEW v_latest_guide AS
WITH last AS (
  SELECT coin_type_id, grade_text, MAX(as_of) AS max_as_of
  FROM guide_price
  GROUP BY coin_type_id, grade_text
)
SELECT gp.coin_type_id, gp.grade_text, gp.price_usd
FROM guide_price gp
JOIN last ON last.coin_type_id = gp.coin_type_id
         AND last.grade_text  = gp.grade_text
         AND last.max_as_of   = gp.as_of;

/* Inventory summary by type */
CREATE OR REPLACE VIEW v_inventory_by_type AS
SELECT
  ct.id AS coin_type_id,
  cm.series,
  ct.year,
  ct.mint_mark,
  ct.variety,
  SUM(l.qty_remaining) AS coins_on_hand
FROM lot l
JOIN coin_type ct ON ct.id = l.coin_type_id
JOIN coin_master cm ON cm.id = ct.master_id
WHERE l.qty_remaining > 0
GROUP BY ct.id, cm.series, ct.year, ct.mint_mark, ct.variety;

/* Melt valuation by metal */
CREATE OR REPLACE VIEW v_unrealized_melt AS
WITH latest AS (
  SELECT metal, price_per_oz_usd
  FROM v_latest_spot
)
SELECT
  cm.metal,
  SUM(l.qty_remaining) AS coins,
  ROUND(SUM(
    l.qty_remaining
    * (cm.weight_grams * COALESCE(cm.fineness,0))
    / 31.1034768
    * (SELECT price_per_oz_usd FROM latest WHERE metal = cm.metal)
  ), 2) AS melt_value_usd
FROM lot l
JOIN coin_type ct ON ct.id = l.coin_type_id
JOIN coin_master cm ON cm.id = ct.master_id
WHERE l.qty_remaining > 0 AND cm.metal IN ('Ag','Au','Pt','Pd')
GROUP BY cm.metal;

/* Per Lot chosen valuation*/
CREATE OR REPLACE VIEW v_lot_value_details AS
SELECT
  l.id AS lot_id,
  cm.series, ct.year, ct.mint_mark, ct.variety,
  l.qty_remaining,
  l.valuation_method,
  COALESCE(l.estimated_grade_text, l.purchase_grade_text) AS grade_for_pricing,

  (cm.weight_grams * COALESCE(cm.fineness,0)) / 31.1034768
    * (SELECT price_per_oz_usd FROM v_latest_spot s WHERE s.metal = cm.metal) AS melt_unit_value,

  (SELECT g.price_usd
     FROM v_latest_guide g
    WHERE g.coin_type_id = l.coin_type_id
      AND g.grade_text   = COALESCE(l.estimated_grade_text, l.purchase_grade_text)) AS guide_unit_value,

  CASE l.valuation_method
    WHEN 'MELT_ONLY'  THEN (cm.weight_grams * COALESCE(cm.fineness,0)) / 31.1034768
                         * (SELECT price_per_oz_usd FROM v_latest_spot s WHERE s.metal = cm.metal)

    WHEN 'GUIDE_ONLY' THEN (SELECT g.price_usd
                              FROM v_latest_guide g
                             WHERE g.coin_type_id = l.coin_type_id
                               AND g.grade_text   = COALESCE(l.estimated_grade_text, l.purchase_grade_text))

    WHEN 'MANUAL'     THEN l.manual_est_unit_value

    ELSE COALESCE(
      (SELECT g.price_usd
         FROM v_latest_guide g
        WHERE g.coin_type_id = l.coin_type_id
          AND g.grade_text   = COALESCE(l.estimated_grade_text, l.purchase_grade_text)),

      (cm.weight_grams * COALESCE(cm.fineness,0)) / 31.1034768
      * (SELECT price_per_oz_usd FROM v_latest_spot s WHERE s.metal = cm.metal),

      NULLIF(l.manual_est_unit_value, 0),

      NULLIF(l.unit_cost, 0),

      0
    )
  END AS chosen_unit_value

FROM lot l
JOIN coin_type  ct ON ct.id = l.coin_type_id
JOIN coin_master cm ON cm.id = ct.master_id
WHERE l.qty_remaining > 0;

/* Portfolio summary */
CREATE OR REPLACE VIEW v_portfolio_value_summary AS
SELECT
  ROUND(COALESCE(SUM(qty_remaining * chosen_unit_value), 0), 2) AS total_estimated_value_usd,
  COALESCE(SUM(qty_remaining), 0) AS total_coins
FROM v_lot_value_details;

/* Realized P/L by sell line */
CREATE OR REPLACE VIEW v_realized_pl AS
SELECT
  tl.id AS sell_line_id,
  t.tx_date,
  cm.series, ct.year, ct.mint_mark, ct.variety,
  SUM(lr.quantity) AS qty_sold,
  SUM(lr.quantity * COALESCE(tl.unit_price,0)) AS proceeds,
  SUM(lr.quantity * l.unit_cost) AS cost_basis,
  SUM(lr.quantity * COALESCE(tl.unit_price,0) - lr.quantity * l.unit_cost) AS realized_pl
FROM tx_line tl
JOIN tx t ON t.id = tl.tx_id AND t.tx_type = 'SELL'
JOIN lot_relief lr ON lr.sell_line_id = tl.id
JOIN lot l ON l.id = lr.lot_id
JOIN coin_type ct ON ct.id = tl.coin_type_id
JOIN coin_master cm ON cm.id = ct.master_id
GROUP BY tl.id, t.tx_date, cm.series, ct.year, ct.mint_mark, ct.variety;

/* Bullion: by category (ROUND/BAR/BULLION COIN) */
CREATE OR REPLACE VIEW v_inventory_bullion_by_category AS
WITH latest AS (SELECT metal, price_per_oz_usd FROM v_latest_spot)
SELECT
  COALESCE(cm.asset_category,'COIN') AS category,
  cm.metal AS metal,
  SUM(l.qty_remaining) AS units_on_hand,
  SUM(l.qty_remaining * COALESCE(cm.weight_grams,0) / 31.1034768) AS gross_oz,
  SUM(l.qty_remaining * (COALESCE(cm.weight_grams,0) * COALESCE(cm.fineness,0)) / 31.1034768) AS fine_oz,
  ROUND(SUM(
    l.qty_remaining
    * (COALESCE(cm.weight_grams,0) * COALESCE(cm.fineness,0)) / 31.1034768
    * (SELECT price_per_oz_usd FROM latest WHERE metal = cm.metal)
  ), 2) AS melt_value_usd
FROM lot l
JOIN coin_type ct ON ct.id = l.coin_type_id
JOIN coin_master cm ON cm.id = ct.master_id
WHERE l.qty_remaining > 0 AND COALESCE(cm.asset_category,'COIN') IN ('ROUND','BAR','BULLION COIN')
GROUP BY COALESCE(cm.asset_category,'COIN'), cm.metal;

/* Bullion: by series (ROUND/BAR/BULLION COIN) */
CREATE OR REPLACE VIEW v_inventory_bullion_by_series AS
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
WHERE l.qty_remaining > 0 AND COALESCE(cm.asset_category,'COIN') IN ('ROUND','BAR','BULLION COIN')
GROUP BY COALESCE(cm.asset_category,'COIN'), cm.metal, cm.series;
"""