# schema_sql.py

SCHEMA_SQL = r"""
PRAGMA foreign_keys = ON;

/* ---------- Reference: coin master & types ---------- */
CREATE TABLE IF NOT EXISTS coin_master (
  id              INTEGER PRIMARY KEY,
  country         TEXT NOT NULL,
  denomination    TEXT NOT NULL,                -- e.g., "Half Dollar"
  series          TEXT NOT NULL,                -- e.g., "Kennedy"
  metal           TEXT,                         -- "Ag","Au","CuNi","Pt","Pd"
  fineness        REAL,                         -- e.g., 0.900
  weight_grams    REAL,                         -- per-coin gross weight
  diameter_mm     REAL,
  thickness_mm    REAL,
  edge            TEXT,
  years_start     INTEGER,
  years_end       INTEGER,
  notes           TEXT,
  asset_category  TEXT NOT NULL DEFAULT 'COIN', -- NEW: COIN / ROUND / BAR
  UNIQUE(country, denomination, series)
);
CREATE INDEX IF NOT EXISTS idx_coin_master_series ON coin_master(series);

CREATE TABLE IF NOT EXISTS coin_type (
  id              INTEGER PRIMARY KEY,
  master_id       INTEGER NOT NULL REFERENCES coin_master(id) ON DELETE CASCADE,
  year            INTEGER NOT NULL,
  mint_mark       TEXT DEFAULT '',               -- "P","D","S","W" or ''
  variety         TEXT DEFAULT '',               -- "Type 1", "DDO", etc. ('' when not used)
  mintage         INTEGER,
  is_proof        INTEGER NOT NULL DEFAULT 0,   -- 0/1
  designer        TEXT,
  obv_desc        TEXT,
  rev_desc        TEXT,
  UNIQUE(master_id, year, mint_mark, variety)
);
CREATE INDEX IF NOT EXISTS idx_coin_type_master ON coin_type(master_id);
CREATE INDEX IF NOT EXISTS idx_coin_type_year ON coin_type(year);

/* ---------- Parties & storage ---------- */
CREATE TABLE IF NOT EXISTS party (
  id              INTEGER PRIMARY KEY,
  name            TEXT NOT NULL,                -- dealer, eBay shop, individual
  kind            TEXT,                         -- "Dealer","Show","Marketplace","Person"
  contact         TEXT
);

CREATE TABLE IF NOT EXISTS storage_location (
  id              INTEGER PRIMARY KEY,
  name            TEXT NOT NULL,                -- "Safe A - Tray 2", "Bank Box #12", "Tube #K-1"
  category        TEXT,                         -- "Home Safe","Bank","Album","Tube"
  description     TEXT
);

/* ---------- Transactions & lines ---------- */
CREATE TABLE IF NOT EXISTS tx (
  id              INTEGER PRIMARY KEY,
  tx_date         TEXT NOT NULL,                -- ISO "YYYY-MM-DD"
  tx_type         TEXT NOT NULL CHECK (tx_type IN ('BUY','SELL','FEE','ADJUST','GIFT_IN','GIFT_OUT','TRANSFER')),
  party_id        INTEGER REFERENCES party(id),
  currency        TEXT NOT NULL DEFAULT 'USD',
  shipping        REAL DEFAULT 0,
  tax             REAL DEFAULT 0,
  fees            REAL DEFAULT 0,
  notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_tx_date ON tx(tx_date);

CREATE TABLE IF NOT EXISTS tx_line (
  id              INTEGER PRIMARY KEY,
  tx_id           INTEGER NOT NULL REFERENCES tx(id) ON DELETE CASCADE,
  coin_type_id    INTEGER REFERENCES coin_type(id),
  quantity        INTEGER NOT NULL CHECK (quantity <> 0),
  unit_price      REAL,                         -- in tx currency; per-coin
  grade_company   TEXT,                         -- PCGS/NGC/ANACS/RAW (as purchased)
  grade_text      TEXT,                         -- "MS65","AU50","PR69DCAM" (as purchased)
  numeric_grade   REAL,                         -- optional numeric (e.g., 65.0)
  slab_cert       TEXT,
  condition_notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_tx_line_type ON tx_line(coin_type_id);
CREATE INDEX IF NOT EXISTS idx_tx_line_tx ON tx_line(tx_id);

/* ---------- Inventory lots & relief (precise cost basis) ---------- */
CREATE TABLE IF NOT EXISTS lot (
  id                      INTEGER PRIMARY KEY,
  acquisition_line_id     INTEGER NOT NULL REFERENCES tx_line(id) ON DELETE CASCADE,
  coin_type_id            INTEGER NOT NULL REFERENCES coin_type(id),
  acquired_date           TEXT NOT NULL,            -- copy from tx_date
  qty_acquired            INTEGER NOT NULL CHECK (qty_acquired > 0),
  qty_remaining           INTEGER NOT NULL CHECK (qty_remaining >= 0),
  unit_cost               REAL NOT NULL,            -- per coin, after alloc of shipping/tax/fees
  storage_location_id     INTEGER REFERENCES storage_location(id),

  -- Purchase (as bought) grade snapshot
  purchase_grade_company  TEXT,
  purchase_grade_text     TEXT,
  purchase_numeric_grade  REAL,
  slab_cert               TEXT,

  -- Your current estimate
  estimated_grade_text    TEXT,     -- e.g., "MS64", "AU50"
  estimated_numeric_grade REAL,     -- e.g., 64.0

  -- Per-lot valuation mode
  valuation_method        TEXT NOT NULL DEFAULT 'AUTO'
                           CHECK (valuation_method IN ('AUTO','MELT_ONLY','GUIDE_ONLY','MANUAL')),
  manual_est_unit_value   REAL,     -- used only when valuation_method='MANUAL'

  status                  TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','CLOSED')),
  notes                   TEXT
);
CREATE INDEX IF NOT EXISTS idx_lot_type ON lot(coin_type_id);
CREATE INDEX IF NOT EXISTS idx_lot_storage ON lot(storage_location_id);
CREATE INDEX IF NOT EXISTS idx_lot_status ON lot(status);
CREATE INDEX IF NOT EXISTS idx_lot_date ON lot(acquired_date);

/* Map sells to specific lots (enables FIFO/LIFO/Specific-ID reporting) */
CREATE TABLE IF NOT EXISTS lot_relief (
  id                INTEGER PRIMARY KEY,
  lot_id            INTEGER NOT NULL REFERENCES lot(id) ON DELETE CASCADE,
  sell_line_id      INTEGER NOT NULL REFERENCES tx_line(id) ON DELETE CASCADE,
  quantity          INTEGER NOT NULL CHECK (quantity > 0),
  proceeds_per_unit REAL                         -- optional, lock per-unit proceeds at sale time
);
CREATE INDEX IF NOT EXISTS idx_lot_relief_lot ON lot_relief(lot_id);
CREATE INDEX IF NOT EXISTS idx_lot_relief_sell ON lot_relief(sell_line_id);

/* Triggers to keep lot.qty_remaining accurate */
CREATE TRIGGER IF NOT EXISTS trg_lot_relief_before_insert
BEFORE INSERT ON lot_relief
BEGIN
  SELECT CASE WHEN (SELECT qty_remaining FROM lot WHERE id = NEW.lot_id) < NEW.quantity
              THEN RAISE(ABORT, 'Not enough quantity in lot') END;
END;

CREATE TRIGGER IF NOT EXISTS trg_lot_relief_after_insert
AFTER INSERT ON lot_relief
BEGIN
  UPDATE lot SET qty_remaining = qty_remaining - NEW.quantity,
                 status = CASE WHEN qty_remaining - NEW.quantity = 0 THEN 'CLOSED' ELSE status END
   WHERE id = NEW.lot_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_lot_relief_after_delete
AFTER DELETE ON lot_relief
BEGIN
  UPDATE lot SET qty_remaining = qty_remaining + OLD.quantity,
                 status = 'OPEN'
   WHERE id = OLD.lot_id;
END;

/* ---------- Pricing & valuation ---------- */
CREATE TABLE IF NOT EXISTS metal_price (
  id               INTEGER PRIMARY KEY,
  metal            TEXT NOT NULL,                -- 'Ag','Au','Pt','Pd'
  price_per_oz_usd REAL NOT NULL,
  quoted_at_utc    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_metal_price_time ON metal_price(metal, quoted_at_utc);

/* Optional: FX if you buy in other currencies */
CREATE TABLE IF NOT EXISTS fx_rate (
  id              INTEGER PRIMARY KEY,
  base_ccy        TEXT NOT NULL,                -- 'USD'
  quote_ccy       TEXT NOT NULL,                -- 'CAD','EUR'
  rate            REAL NOT NULL,                -- 1 base -> rate quote
  quoted_at_utc   TEXT NOT NULL
);

/* ---------- Storage movement history (optional) ---------- */
CREATE TABLE IF NOT EXISTS storage_event (
  id               INTEGER PRIMARY KEY,
  lot_id           INTEGER NOT NULL REFERENCES lot(id) ON DELETE CASCADE,
  event_date       TEXT NOT NULL,
  from_location_id INTEGER REFERENCES storage_location(id),
  to_location_id   INTEGER REFERENCES storage_location(id),
  quantity         INTEGER NOT NULL CHECK (quantity > 0),
  note             TEXT
);

/* ---------- Organization (tags/images) ---------- */
CREATE TABLE IF NOT EXISTS tag (
  id              INTEGER PRIMARY KEY,
  name            TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS coin_type_tag (
  coin_type_id    INTEGER NOT NULL REFERENCES coin_type(id) ON DELETE CASCADE,
  tag_id          INTEGER NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
  PRIMARY KEY (coin_type_id, tag_id)
);

CREATE TABLE IF NOT EXISTS image (
  id              INTEGER PRIMARY KEY,
  coin_type_id    INTEGER REFERENCES coin_type(id),
  lot_id          INTEGER REFERENCES lot(id),
  file_path       TEXT NOT NULL,
  caption         TEXT
);

/* ---------- Views ---------- */
/* Latest spot per metal */
CREATE VIEW IF NOT EXISTS v_latest_spot AS
SELECT metal, price_per_oz_usd
FROM metal_price mp
WHERE quoted_at_utc = (
  SELECT MAX(quoted_at_utc) FROM metal_price x WHERE x.metal = mp.metal
);

/* Latest guide price per (type, grade_text) */
CREATE TABLE IF NOT EXISTS guide_price (
  id            INTEGER PRIMARY KEY,
  coin_type_id  INTEGER NOT NULL REFERENCES coin_type(id) ON DELETE CASCADE,
  grade_text    TEXT NOT NULL,          -- "G4","VF20","AU50","MS65","PR69DCAM"
  numeric_grade REAL,
  price_usd     REAL NOT NULL,          -- per coin
  as_of         TEXT NOT NULL,          -- ISO date
  source        TEXT,
  UNIQUE (coin_type_id, grade_text, as_of)
);
CREATE INDEX IF NOT EXISTS idx_guide_price_type_grade ON guide_price(coin_type_id, grade_text, as_of);

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

/* NEW: Bullion inventory by category (ROUND/BAR) */
DROP VIEW IF EXISTS v_inventory_bullion_by_category;
CREATE VIEW v_inventory_bullion_by_category AS
WITH latest AS (
  SELECT metal, price_per_oz_usd FROM v_latest_spot
)
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
WHERE l.qty_remaining > 0 AND COALESCE(cm.asset_category,'COIN') IN ('ROUND','BAR')
GROUP BY COALESCE(cm.asset_category,'COIN'), cm.metal;

/* Per-lot chosen valuation */
CREATE VIEW IF NOT EXISTS v_lot_value_details AS
SELECT
  l.id AS lot_id,
  cm.series, ct.year, ct.mint_mark, ct.variety,
  l.qty_remaining,
  l.valuation_method,
  COALESCE(l.estimated_grade_text, l.purchase_grade_text) AS grade_for_pricing,

  -- melt per coin
  (cm.weight_grams * COALESCE(cm.fineness,0)) / 31.1034768
    * (SELECT price_per_oz_usd FROM v_latest_spot s WHERE s.metal = cm.metal)
    AS melt_unit_value,

  -- guide per coin (match on estimated or purchase grade_text)
  (SELECT g.price_usd
     FROM v_latest_guide g
    WHERE g.coin_type_id = l.coin_type_id
      AND g.grade_text   = COALESCE(l.estimated_grade_text, l.purchase_grade_text)
  ) AS guide_unit_value,

  -- the chosen unit value
  CASE l.valuation_method
    WHEN 'MELT_ONLY'  THEN
      (cm.weight_grams * COALESCE(cm.fineness,0)) / 31.1034768
      * (SELECT price_per_oz_usd FROM v_latest_spot s WHERE s.metal = cm.metal)
    WHEN 'GUIDE_ONLY' THEN
      (SELECT g.price_usd FROM v_latest_guide g
        WHERE g.coin_type_id = l.coin_type_id
          AND g.grade_text   = COALESCE(l.estimated_grade_text, l.purchase_grade_text))
    WHEN 'MANUAL'     THEN l.manual_est_unit_value
    ELSE COALESCE(
      (SELECT g.price_usd FROM v_latest_guide g
        WHERE g.coin_type_id = l.coin_type_id
          AND g.grade_text   = COALESCE(l.estimated_grade_text, l.purchase_grade_text)),
      (cm.weight_grams * COALESCE(cm.fineness,0)) / 31.1034768
      * (SELECT price_per_oz_usd FROM v_latest_spot s WHERE s.metal = cm.metal)
    )
  END AS chosen_unit_value
FROM lot l
JOIN coin_type ct ON ct.id = l.coin_type_id
JOIN coin_master cm ON cm.id = ct.master_id
WHERE l.qty_remaining > 0;

/* Portfolio summary */
CREATE VIEW IF NOT EXISTS v_portfolio_value_summary AS
SELECT
  ROUND(COALESCE(SUM(qty_remaining * chosen_unit_value), 0), 2) AS total_estimated_value_usd,
  COALESCE(SUM(qty_remaining), 0)                     AS total_coins
FROM v_lot_value_details;

/* Realized P/L by sell line */
CREATE VIEW IF NOT EXISTS v_realized_pl AS
SELECT
  tl.id AS sell_line_id,
  t.tx_date,
  cm.series, ct.year, ct.mint_mark, ct.variety,
  SUM(lr.quantity) AS qty_sold,
  SUM(lr.quantity * COALESCE(tl.unit_price,0))                 AS proceeds,
  SUM(lr.quantity * l.unit_cost)                               AS cost_basis,
  SUM(lr.quantity * COALESCE(tl.unit_price,0) - lr.quantity * l.unit_cost) AS realized_pl
FROM tx_line tl
JOIN tx t ON t.id = tl.tx_id AND t.tx_type = 'SELL'
JOIN lot_relief lr ON lr.sell_line_id = tl.id
JOIN lot l ON l.id = lr.lot_id
JOIN coin_type ct ON ct.id = tl.coin_type_id
JOIN coin_master cm ON cm.id = ct.master_id
GROUP BY tl.id;
"""
