# schema_sql.py - SQLite Version with NGC/PCGS URLs

SCHEMA_SQL = r"""
PRAGMA foreign_keys = ON;

/* ---------- Reference: coin master & types ---------- */
CREATE TABLE IF NOT EXISTS coin_master (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  country         TEXT NOT NULL,
  denomination    TEXT NOT NULL,
  series          TEXT NOT NULL,
  metal           TEXT,
  fineness        REAL,
  weight_grams    REAL,
  diameter_mm     REAL,
  thickness_mm    REAL,
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
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  master_id       INTEGER NOT NULL REFERENCES coin_master(id) ON DELETE CASCADE,
  year            INTEGER NOT NULL,
  mint_mark       TEXT DEFAULT '',
  variety         TEXT DEFAULT '',
  mintage         INTEGER,
  is_proof        INTEGER NOT NULL DEFAULT 0,
  designer        TEXT,
  obv_desc        TEXT,
  rev_desc        TEXT,
  UNIQUE(master_id, year, mint_mark, variety)
);
CREATE INDEX IF NOT EXISTS idx_coin_type_master_id ON coin_type(master_id);
CREATE INDEX IF NOT EXISTS idx_coin_type_year ON coin_type(year);

/* ---------- Parties & storage ---------- */
CREATE TABLE IF NOT EXISTS party (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  name            TEXT NOT NULL,
  kind            TEXT,
  contact         TEXT
);

CREATE TABLE IF NOT EXISTS storage_location (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  name            TEXT NOT NULL,
  category        TEXT,
  description     TEXT
);

/* ---------- Transactions & lines ---------- */
CREATE TABLE IF NOT EXISTS tx (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  tx_date         TEXT NOT NULL,  -- ISO date format YYYY-MM-DD
  tx_type         TEXT NOT NULL CHECK (tx_type IN ('BUY','SELL','FEE','ADJUST','GIFT_IN','GIFT_OUT','TRANSFER')),
  party_id        INTEGER REFERENCES party(id) ON DELETE SET NULL,
  currency        TEXT NOT NULL DEFAULT 'USD',
  shipping        REAL DEFAULT 0.00,
  tax             REAL DEFAULT 0.00,
  fees            REAL DEFAULT 0.00,
  notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_tx_date ON tx(tx_date);
CREATE INDEX IF NOT EXISTS idx_tx_party_id ON tx(party_id);

CREATE TABLE IF NOT EXISTS tx_line (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  tx_id           INTEGER NOT NULL REFERENCES tx(id) ON DELETE CASCADE,
  coin_type_id    INTEGER NOT NULL REFERENCES coin_type(id) ON DELETE RESTRICT,
  quantity        INTEGER NOT NULL CHECK (quantity <> 0),
  unit_price      REAL,
  grade_company   TEXT,
  grade_text      TEXT,
  numeric_grade   REAL,
  slab_cert       TEXT,
  condition_notes TEXT
);

/* Indexes for foreign keys and common queries */
CREATE INDEX IF NOT EXISTS idx_tx_line_tx_id ON tx_line(tx_id);
CREATE INDEX IF NOT EXISTS idx_tx_line_coin_type_id ON tx_line(coin_type_id);

/* ---------- Inventory lots & relief ---------- */
CREATE TABLE IF NOT EXISTS lot (
  id                      INTEGER PRIMARY KEY AUTOINCREMENT,
  acquisition_line_id     INTEGER NOT NULL REFERENCES tx_line(id) ON DELETE CASCADE,
  coin_type_id            INTEGER NOT NULL REFERENCES coin_type(id) ON DELETE RESTRICT,
  acquired_date           TEXT NOT NULL,  -- ISO date format YYYY-MM-DD
  qty_acquired            INTEGER NOT NULL CHECK (qty_acquired > 0),
  qty_remaining           INTEGER NOT NULL CHECK (qty_remaining >= 0),
  unit_cost               REAL NOT NULL,
  storage_location_id     INTEGER REFERENCES storage_location(id) ON DELETE SET NULL,

  purchase_grade_company  TEXT,
  purchase_grade_text     TEXT,
  purchase_numeric_grade  REAL,
  slab_cert               TEXT,

  estimated_grade_text    TEXT,
  estimated_numeric_grade REAL,

  valuation_method        TEXT NOT NULL DEFAULT 'AUTO'
                           CHECK (valuation_method IN ('AUTO','MELT_ONLY','GUIDE_ONLY','MANUAL')),
  manual_est_unit_value   REAL,

  status                  TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','CLOSED')),
  notes                   TEXT
);

/* Indexes for foreign keys and common queries */
CREATE INDEX IF NOT EXISTS idx_lot_acquisition_line_id ON lot(acquisition_line_id);
CREATE INDEX IF NOT EXISTS idx_lot_coin_type_id ON lot(coin_type_id);
CREATE INDEX IF NOT EXISTS idx_lot_storage_location_id ON lot(storage_location_id);
CREATE INDEX IF NOT EXISTS idx_lot_status ON lot(status);
CREATE INDEX IF NOT EXISTS idx_lot_acquired_date ON lot(acquired_date);

/* Relief mapping */
CREATE TABLE IF NOT EXISTS lot_relief (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  lot_id            INTEGER NOT NULL REFERENCES lot(id) ON DELETE CASCADE,
  sell_line_id      INTEGER NOT NULL REFERENCES tx_line(id) ON DELETE CASCADE,
  quantity          INTEGER NOT NULL CHECK (quantity > 0),
  proceeds_per_unit REAL
);

/* Indexes for foreign keys */
CREATE INDEX IF NOT EXISTS idx_lot_relief_lot_id ON lot_relief(lot_id);
CREATE INDEX IF NOT EXISTS idx_lot_relief_sell_line_id ON lot_relief(sell_line_id);

/* Triggers */
CREATE TRIGGER IF NOT EXISTS trg_lot_relief_before_insert
BEFORE INSERT ON lot_relief
BEGIN
  SELECT CASE 
    WHEN (SELECT qty_remaining FROM lot WHERE id = NEW.lot_id) < NEW.quantity
    THEN RAISE(ABORT, 'Insufficient quantity in lot')
    END;
END;

CREATE TRIGGER IF NOT EXISTS trg_lot_relief_after_insert
AFTER INSERT ON lot_relief
BEGIN
  UPDATE lot 
  SET qty_remaining = qty_remaining - NEW.quantity,
      status = CASE WHEN qty_remaining - NEW.quantity = 0 THEN 'CLOSED' ELSE status END
  WHERE id = NEW.lot_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_lot_relief_after_delete
AFTER DELETE ON lot_relief
BEGIN
  UPDATE lot 
  SET qty_remaining = qty_remaining + OLD.quantity,
      status = CASE WHEN qty_remaining + OLD.quantity > 0 THEN 'OPEN' ELSE status END
  WHERE id = OLD.lot_id;
END;

/* ---------- Pricing ---------- */
CREATE TABLE IF NOT EXISTS metal_price (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  metal            TEXT NOT NULL,                -- 'Ag','Au','Pt','Pd'
  price_per_oz_usd REAL NOT NULL,
  quoted_at_utc    TEXT NOT NULL               -- ISO datetime format
);

CREATE INDEX IF NOT EXISTS idx_metal_price_metal ON metal_price(metal);
CREATE INDEX IF NOT EXISTS idx_metal_price_time ON metal_price(quoted_at_utc DESC);

CREATE TABLE IF NOT EXISTS fx_rate (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  base_ccy        TEXT NOT NULL,
  quote_ccy       TEXT NOT NULL,
  rate            REAL NOT NULL,
  quoted_at_utc   TEXT NOT NULL                -- ISO datetime format
);
CREATE INDEX IF NOT EXISTS idx_fx_rate_pair ON fx_rate(base_ccy, quote_ccy);
CREATE INDEX IF NOT EXISTS idx_fx_rate_time ON fx_rate(quoted_at_utc DESC);

/* ---------- Org ---------- */
CREATE TABLE IF NOT EXISTS tag (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  name            TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS coin_type_tag (
  coin_type_id    INTEGER NOT NULL REFERENCES coin_type(id) ON DELETE CASCADE,
  tag_id          INTEGER NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
  PRIMARY KEY (coin_type_id, tag_id)
);

CREATE TABLE IF NOT EXISTS image (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  coin_type_id    INTEGER REFERENCES coin_type(id) ON DELETE CASCADE,
  lot_id          INTEGER REFERENCES lot(id) ON DELETE CASCADE,
  file_path       TEXT NOT NULL,
  caption         TEXT
);

/* ---------- Specimen Tracking ---------- */
CREATE TABLE IF NOT EXISTS series_code (
    id INTEGER PRIMARY KEY,
    series TEXT NOT NULL UNIQUE,
    prefix TEXT NOT NULL,
    next_seq INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS specimen (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    coin_type_id INTEGER NOT NULL REFERENCES coin_type(id),
    lot_id INTEGER REFERENCES lot(id),
    sold_line_id INTEGER REFERENCES tx_line(id),
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_specimen_code ON specimen(code);
CREATE INDEX IF NOT EXISTS idx_specimen_lot_id ON specimen(lot_id);
CREATE INDEX IF NOT EXISTS idx_specimen_sold_line_id ON specimen(sold_line_id);

/* Indexes for foreign keys */
CREATE INDEX IF NOT EXISTS idx_image_coin_type_id ON image(coin_type_id);
CREATE INDEX IF NOT EXISTS idx_image_lot_id ON image(lot_id);

/* ---------- Guide pricing ---------- */
CREATE TABLE IF NOT EXISTS guide_price (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  coin_type_id  INTEGER NOT NULL REFERENCES coin_type(id) ON DELETE CASCADE,
  grade_text    TEXT NOT NULL,
  numeric_grade REAL,
  price_usd     REAL NOT NULL,
  as_of         TEXT NOT NULL,                -- ISO date format YYYY-MM-DD
  source        TEXT,
  UNIQUE (coin_type_id, grade_text, as_of)
);
CREATE INDEX IF NOT EXISTS idx_guide_price_coin_type_id ON guide_price(coin_type_id);
CREATE INDEX IF NOT EXISTS idx_guide_price_grade ON guide_price(coin_type_id, grade_text);
CREATE INDEX IF NOT EXISTS idx_guide_price_date ON guide_price(as_of DESC);

/* ---------- Type Sets ---------- */
CREATE TABLE IF NOT EXISTS type_set (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS type_set_member (
    set_id INTEGER REFERENCES type_set(id) ON DELETE CASCADE,
    coin_type_id INTEGER REFERENCES coin_type(id) ON DELETE CASCADE,
    PRIMARY KEY (set_id, coin_type_id)
);

CREATE TABLE IF NOT EXISTS type_set_assignment (
    set_id INTEGER REFERENCES type_set(id) ON DELETE CASCADE,
    coin_type_id INTEGER REFERENCES coin_type(id),
    specimen_id INTEGER REFERENCES specimen(id),
    PRIMARY KEY (set_id, specimen_id)
);

/* ---------- Type Set Enhancements ---------- */

-- Store metadata/criteria for type sets
CREATE TABLE IF NOT EXISTS type_set_metadata (
    set_id INTEGER PRIMARY KEY REFERENCES type_set(id) ON DELETE CASCADE,
    grade_company TEXT,                    -- Required grading company (PCGS, NGC, etc)
    min_grade TEXT,                         -- Minimum grade (MS-63, etc)
    max_grade TEXT,                         -- Maximum grade
    min_numeric_grade REAL,                 -- Numeric minimum for easier comparison
    max_numeric_grade REAL,                 -- Numeric maximum for easier comparison
    require_slab INTEGER DEFAULT 0,         -- Must have slab cert
    require_cac INTEGER DEFAULT 0,          -- Must have CAC approval
    proof_only INTEGER DEFAULT 0,           -- Only proof coins
    business_only INTEGER DEFAULT 0,        -- Only business strikes
    include_varieties INTEGER DEFAULT 1,    -- Include varieties in the set
    year_start INTEGER,                     -- Year range start
    year_end INTEGER,                       -- Year range end
    created_date TEXT,                      -- When the set was created
    modified_date TEXT                      -- Last modified
);

-- Index for quick lookups
CREATE INDEX IF NOT EXISTS idx_type_set_metadata_set_id ON type_set_metadata(set_id);


/* ---------- Views ---------- */
/* Estimated Sale Proceeds View */
CREATE VIEW IF NOT EXISTS v_portfolio_sale_proceeds AS
WITH sale_values AS (
    SELECT 
        l.id,
        l.qty_remaining,
        v.chosen_unit_value,
        cm.asset_category,
        l.valuation_method,
        CASE 
            -- Bullion and junk silver: 90% of value
            WHEN cm.asset_category IN ('ROUND', 'BAR', 'BULLION COIN') THEN v.chosen_unit_value * 0.90
            WHEN l.valuation_method = 'MELT_ONLY' THEN v.chosen_unit_value * 0.90
            -- All other coins: 75% of value
            ELSE v.chosen_unit_value * 0.75
        END as sale_proceed_per_unit
    FROM lot l
    JOIN v_lot_value_details v ON v.lot_id = l.id
    JOIN coin_type ct ON ct.id = l.coin_type_id
    JOIN coin_master cm ON cm.id = ct.master_id
    WHERE l.qty_remaining > 0
)
SELECT 
    ROUND(SUM(qty_remaining * sale_proceed_per_unit), 2) as estimated_sale_proceeds
FROM sale_values;


/* Type Set Progress View - tracks which coins you have for each set */
CREATE VIEW IF NOT EXISTS v_type_set_progress AS
SELECT 
    tsm.set_id,
    tsm.coin_type_id,
    cm.series,
    ct.year,
    ct.mint_mark,
    ct.variety,
    COALESCE(SUM(l.qty_remaining), 0) as on_hand
FROM type_set_member tsm
JOIN coin_type ct ON ct.id = tsm.coin_type_id
JOIN coin_master cm ON cm.id = ct.master_id
LEFT JOIN lot l ON l.coin_type_id = tsm.coin_type_id AND l.qty_remaining > 0
GROUP BY tsm.set_id, tsm.coin_type_id, cm.series, ct.year, ct.mint_mark, ct.variety;

/* Latest spot per metal */
CREATE VIEW IF NOT EXISTS v_latest_spot AS
SELECT metal, price_per_oz_usd
FROM metal_price mp
WHERE quoted_at_utc = (
  SELECT MAX(quoted_at_utc) FROM metal_price x WHERE x.metal = mp.metal
);

/* Latest guide per grade */
CREATE VIEW IF NOT EXISTS v_latest_guide AS
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
CREATE VIEW IF NOT EXISTS v_inventory_by_type AS
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
GROUP BY ct.id;

/* Melt valuation by metal */
CREATE VIEW IF NOT EXISTS v_unrealized_melt AS
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
CREATE VIEW IF NOT EXISTS v_lot_value_details AS
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

    ELSE -- AUTO mode: choose the highest value using MAX with UNION
      (SELECT MAX(val) FROM (
        SELECT COALESCE((SELECT g.price_usd
                         FROM v_latest_guide g
                        WHERE g.coin_type_id = l.coin_type_id
                          AND g.grade_text = COALESCE(l.estimated_grade_text, l.purchase_grade_text)), 0) AS val
        UNION ALL
        SELECT COALESCE((cm.weight_grams * COALESCE(cm.fineness,0)) / 31.1034768
                       * (SELECT price_per_oz_usd FROM v_latest_spot s WHERE s.metal = cm.metal), 0) AS val
        UNION ALL
        SELECT COALESCE(l.manual_est_unit_value, 0) AS val
        UNION ALL
        SELECT COALESCE(l.unit_cost, 0) AS val
      ))
  END AS chosen_unit_value

FROM lot l
JOIN coin_type  ct ON ct.id = l.coin_type_id
JOIN coin_master cm ON cm.id = ct.master_id
WHERE l.qty_remaining > 0;


/* Portfolio summary */
CREATE VIEW IF NOT EXISTS v_portfolio_value_summary AS
SELECT
  ROUND(COALESCE(SUM(qty_remaining * chosen_unit_value), 0), 2) AS total_estimated_value_usd,
  COALESCE(SUM(qty_remaining), 0) AS total_coins
FROM v_lot_value_details;

/* Realized P/L by sell line */
CREATE VIEW IF NOT EXISTS v_realized_pl AS
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
GROUP BY tl.id;

/* Bullion: by category (ROUND/BAR/BULLION COIN) */
CREATE VIEW IF NOT EXISTS v_inventory_bullion_by_category AS
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
CREATE VIEW IF NOT EXISTS v_inventory_bullion_by_series AS
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

/* Comprehensive inventory summary view */
CREATE VIEW IF NOT EXISTS v_inventory_summary AS
SELECT 
    cm.country,
    cm.series, 
    cm.metal,
    cm.asset_category,
    ct.is_proof,
    COUNT(DISTINCT l.id) AS lot_count,
    SUM(l.qty_remaining) AS total_coins,
    ROUND(SUM(l.qty_remaining * l.unit_cost), 2) AS total_cost_usd,
    ROUND(SUM(l.qty_remaining * lvd.melt_unit_value), 2) AS total_melt_usd,
    ROUND(SUM(l.qty_remaining * lvd.chosen_unit_value), 2) AS total_est_usd
FROM lot l
JOIN coin_type ct ON ct.id = l.coin_type_id  
JOIN coin_master cm ON cm.id = ct.master_id
JOIN v_lot_value_details lvd ON lvd.lot_id = l.id
WHERE l.qty_remaining > 0
GROUP BY cm.country, cm.series, cm.metal, cm.asset_category, ct.is_proof;

/* Transaction summary view */
CREATE VIEW IF NOT EXISTS v_transaction_summary AS
SELECT 
    t.id,
    t.tx_date,
    t.tx_type,
    COALESCE(p.name, '') AS party_name,
    t.currency,
    COALESCE(t.shipping, 0) + COALESCE(t.tax, 0) + COALESCE(t.fees, 0) AS total_fees,
    COUNT(tl.id) AS line_count,
    SUM(ABS(tl.quantity)) AS total_quantity,
    ROUND(SUM(ABS(tl.quantity) * COALESCE(tl.unit_price, 0)), 2) AS subtotal,
    ROUND(SUM(ABS(tl.quantity) * COALESCE(tl.unit_price, 0)) + 
          COALESCE(t.shipping, 0) + COALESCE(t.tax, 0) + COALESCE(t.fees, 0), 2) AS total
FROM tx t
LEFT JOIN party p ON p.id = t.party_id
LEFT JOIN tx_line tl ON tl.tx_id = t.id
GROUP BY t.id, t.tx_date, t.tx_type, p.name, t.currency, t.shipping, t.tax, t.fees;

/* Country inventory view (for World Coins) */
CREATE VIEW IF NOT EXISTS v_country_inventory AS  
SELECT 
    cm.country,
    cm.series,
    SUM(l.qty_remaining) AS coins_on_hand,
    ROUND(SUM(l.qty_remaining * lvd.melt_unit_value), 2) AS melt_value_usd,
    ROUND(SUM(l.qty_remaining * lvd.chosen_unit_value), 2) AS est_value_usd
FROM lot l
JOIN coin_type ct ON ct.id = l.coin_type_id
JOIN coin_master cm ON cm.id = ct.master_id  
JOIN v_lot_value_details lvd ON lvd.lot_id = l.id
WHERE l.qty_remaining > 0 AND COALESCE(cm.country, '') <> ''
GROUP BY cm.country, cm.series;

/* Junk/Constitutional Silver View */
CREATE VIEW IF NOT EXISTS v_junk_silver AS
SELECT 
    cm.series,
    SUM(l.qty_remaining) as quantity,
    ROUND(SUM(l.qty_remaining * v.melt_unit_value), 2) as total_melt_value,
    ROUND(SUM(l.qty_remaining * (cm.weight_grams * cm.fineness) / 31.1034768), 4) as total_fine_oz
FROM lot l
JOIN coin_type ct ON ct.id = l.coin_type_id
JOIN coin_master cm ON cm.id = ct.master_id
JOIN v_lot_value_details v ON v.lot_id = l.id
WHERE l.valuation_method = 'MELT_ONLY'
    AND l.qty_remaining > 0
    AND cm.metal = 'Ag'
    AND cm.asset_category = 'COIN'
GROUP BY cm.series
ORDER BY total_fine_oz DESC;

/* Junk Silver Detail View */
CREATE VIEW IF NOT EXISTS v_junk_silver_detail AS
SELECT 
    cm.series,
    ct.year,
    ct.mint_mark,
    ct.variety,
    l.qty_remaining as quantity,
    ROUND(v.melt_unit_value, 4) as melt_per_coin,
    ROUND(l.qty_remaining * v.melt_unit_value, 2) as total_melt_value,
    ROUND(l.qty_remaining * (cm.weight_grams * cm.fineness) / 31.1034768, 4) as total_fine_oz
FROM lot l
JOIN coin_type ct ON ct.id = l.coin_type_id
JOIN coin_master cm ON cm.id = ct.master_id
JOIN v_lot_value_details v ON v.lot_id = l.id
WHERE l.valuation_method = 'MELT_ONLY'
    AND l.qty_remaining > 0
    AND cm.metal = 'Ag'
    AND cm.asset_category = 'COIN'
ORDER BY cm.series, ct.year, ct.mint_mark;

/* ---------- Enhanced Type Set Views ---------- */

-- View showing type set progress with ownership details
CREATE VIEW IF NOT EXISTS v_type_set_progress_detailed AS
SELECT 
    tsm.set_id,
    ts.name as set_name,
    tsm.coin_type_id,
    cm.series,
    ct.year,
    ct.mint_mark,
    ct.variety,
    ct.is_proof,
    -- What we have
    COALESCE(owned.qty_on_hand, 0) as qty_on_hand,
    CASE WHEN owned.qty_on_hand > 0 THEN 1 ELSE 0 END as have_any,
    owned.best_grade_company,
    owned.best_grade_text,
    owned.best_numeric_grade,
    owned.has_slab_cert,
    -- Set requirements
    meta.grade_company as required_grade_company,
    meta.min_grade as required_min_grade,
    meta.max_grade as required_max_grade,
    meta.require_slab as requires_slab,
    -- Validation
    CASE 
        WHEN owned.qty_on_hand IS NULL OR owned.qty_on_hand = 0 THEN 0
        WHEN meta.grade_company IS NOT NULL AND owned.best_grade_company != meta.grade_company THEN 0
        WHEN meta.min_numeric_grade IS NOT NULL AND owned.best_numeric_grade < meta.min_numeric_grade THEN 0
        WHEN meta.max_numeric_grade IS NOT NULL AND owned.best_numeric_grade > meta.max_numeric_grade THEN 0
        WHEN meta.require_slab = 1 AND owned.has_slab_cert = 0 THEN 0
        ELSE 1
    END as meets_requirements
FROM type_set_member tsm
JOIN type_set ts ON ts.id = tsm.set_id
JOIN coin_type ct ON ct.id = tsm.coin_type_id
JOIN coin_master cm ON cm.id = ct.master_id
LEFT JOIN type_set_metadata meta ON meta.set_id = tsm.set_id
LEFT JOIN (
    -- Subquery to get best example of each coin type we own
    SELECT 
        l.coin_type_id,
        SUM(l.qty_remaining) as qty_on_hand,
        MAX(l.purchase_grade_company) as best_grade_company,
        MAX(COALESCE(l.estimated_grade_text, l.purchase_grade_text)) as best_grade_text,
        MAX(COALESCE(l.estimated_numeric_grade, l.purchase_numeric_grade)) as best_numeric_grade,
        MAX(CASE WHEN l.slab_cert IS NOT NULL AND l.slab_cert != '' THEN 1 ELSE 0 END) as has_slab_cert
    FROM lot l
    WHERE l.qty_remaining > 0
    GROUP BY l.coin_type_id
) owned ON owned.coin_type_id = tsm.coin_type_id;

-- Summary view for type set completion
CREATE VIEW IF NOT EXISTS v_type_set_summary AS
SELECT 
    ts.id as set_id,
    ts.name,
    ts.description,
    COUNT(DISTINCT tsm.coin_type_id) as total_coins,
    COUNT(DISTINCT CASE WHEN p.qty_on_hand > 0 THEN tsm.coin_type_id END) as coins_owned,
    COUNT(DISTINCT CASE WHEN p.meets_requirements = 1 THEN tsm.coin_type_id END) as coins_meeting_requirements,
    ROUND(
        100.0 * COUNT(DISTINCT CASE WHEN p.qty_on_hand > 0 THEN tsm.coin_type_id END) / 
        NULLIF(COUNT(DISTINCT tsm.coin_type_id), 0), 
        1
    ) as percent_owned,
    ROUND(
        100.0 * COUNT(DISTINCT CASE WHEN p.meets_requirements = 1 THEN tsm.coin_type_id END) / 
        NULLIF(COUNT(DISTINCT tsm.coin_type_id), 0), 
        1
    ) as percent_complete,
    meta.grade_company,
    meta.min_grade,
    meta.max_grade,
    meta.require_slab
FROM type_set ts
LEFT JOIN type_set_member tsm ON tsm.set_id = ts.id
LEFT JOIN v_type_set_progress_detailed p ON p.set_id = ts.id AND p.coin_type_id = tsm.coin_type_id
LEFT JOIN type_set_metadata meta ON meta.set_id = ts.id
GROUP BY ts.id, ts.name, ts.description, 
         meta.grade_company, meta.min_grade, meta.max_grade, meta.require_slab;

-- View to find coins that could be upgraded for a set
CREATE VIEW IF NOT EXISTS v_type_set_upgrade_targets AS
SELECT 
    p.set_id,
    p.set_name,
    p.coin_type_id,
    p.series,
    p.year,
    p.mint_mark,
    p.variety,
    p.qty_on_hand,
    p.best_grade_text as current_grade,
    p.best_numeric_grade as current_numeric,
    p.required_min_grade as target_grade,
    meta.min_numeric_grade as target_numeric,
    CASE 
        WHEN p.qty_on_hand = 0 THEN 'Need to acquire'
        WHEN p.best_grade_company != meta.grade_company THEN 'Wrong grading company'
        WHEN p.best_numeric_grade < meta.min_numeric_grade THEN 'Grade too low'
        WHEN meta.require_slab = 1 AND p.has_slab_cert = 0 THEN 'Needs slabbing'
        ELSE 'Meets requirements'
    END as upgrade_needed
FROM v_type_set_progress_detailed p
JOIN type_set_metadata meta ON meta.set_id = p.set_id
WHERE p.meets_requirements = 0
ORDER BY p.set_id, p.series, p.year, p.mint_mark;

-- View showing best candidates from inventory to fill type set needs
CREATE VIEW IF NOT EXISTS v_type_set_best_candidates AS
SELECT 
    tsm.set_id,
    ts.name as set_name,
    tsm.coin_type_id,
    cm.series,
    ct.year,
    ct.mint_mark,
    ct.variety,
    l.id as lot_id,
    l.qty_remaining,
    l.purchase_grade_company,
    COALESCE(l.estimated_grade_text, l.purchase_grade_text) as grade_text,
    COALESCE(l.estimated_numeric_grade, l.purchase_numeric_grade) as numeric_grade,
    l.slab_cert,
    l.unit_cost,
    meta.grade_company as required_company,
    meta.min_grade as required_min_grade,
    -- Scoring to find best candidate
    CASE 
        WHEN meta.grade_company IS NOT NULL AND l.purchase_grade_company = meta.grade_company THEN 10
        WHEN l.purchase_grade_company IN ('PCGS', 'NGC') THEN 5
        ELSE 0
    END +
    CASE 
        WHEN l.slab_cert IS NOT NULL AND l.slab_cert != '' THEN 5
        ELSE 0
    END +
    COALESCE(l.estimated_numeric_grade, l.purchase_numeric_grade, 0) as match_score
FROM type_set_member tsm
JOIN type_set ts ON ts.id = tsm.set_id
JOIN coin_type ct ON ct.id = tsm.coin_type_id
JOIN coin_master cm ON cm.id = ct.master_id
JOIN lot l ON l.coin_type_id = tsm.coin_type_id AND l.qty_remaining > 0
LEFT JOIN type_set_metadata meta ON meta.set_id = tsm.set_id
ORDER BY tsm.set_id, tsm.coin_type_id, match_score DESC;

"""