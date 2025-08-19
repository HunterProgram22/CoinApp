-- schema_typesets_fix.sql
PRAGMA foreign_keys = ON;

-- Core Type Set tables
CREATE TABLE IF NOT EXISTS type_set (
  id          INTEGER PRIMARY KEY,
  name        TEXT NOT NULL UNIQUE,
  description TEXT,
  mode        TEXT NOT NULL CHECK (mode IN ('MANUAL','RULES')),
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS type_set_item (
  set_id       INTEGER NOT NULL REFERENCES type_set(id) ON DELETE CASCADE,
  coin_type_id INTEGER NOT NULL REFERENCES coin_type(id) ON DELETE CASCADE,
  required_qty INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (set_id, coin_type_id)
);

CREATE TABLE IF NOT EXISTS type_set_rule (
  id            INTEGER PRIMARY KEY,
  set_id        INTEGER NOT NULL REFERENCES type_set(id) ON DELETE CASCADE,
  country       TEXT,
  denomination  TEXT,
  series        TEXT,
  is_proof      INTEGER,            -- 0/1
  mint_mark_in  TEXT,               -- CSV like 'S,D,W'
  year_min      INTEGER,
  year_max      INTEGER,
  year_list     TEXT,               -- CSV like '1980,1982,2015,2016'
  variety_like  TEXT
);

-- Base progress view (manual + rule-derived requirements vs inventory on-hand)
CREATE VIEW IF NOT EXISTS v_type_set_progress AS
WITH rule_matches AS (
  SELECT r.set_id, ct.id AS coin_type_id, 1 AS required_qty
  FROM type_set_rule r
  JOIN coin_type ct ON 1=1
  JOIN coin_master cm ON cm.id = ct.master_id
  WHERE (r.country      IS NULL OR cm.country = r.country)
    AND (r.denomination IS NULL OR cm.denomination = r.denomination)
    AND (r.series       IS NULL OR cm.series = r.series)
    AND (r.is_proof     IS NULL OR ct.is_proof = r.is_proof)
    AND (r.mint_mark_in IS NULL OR instr(','||r.mint_mark_in||',', ','||ct.mint_mark||',') > 0)
    AND (r.year_min     IS NULL OR ct.year >= r.year_min)
    AND (r.year_max     IS NULL OR ct.year <= r.year_max)
    AND (r.year_list    IS NULL OR instr(','||r.year_list||',', ','||ct.year||',') > 0)
    AND (r.variety_like IS NULL OR ct.variety LIKE r.variety_like)
),
items AS (
  SELECT set_id, coin_type_id, required_qty FROM type_set_item
  UNION
  SELECT set_id, coin_type_id, required_qty
  FROM rule_matches
  WHERE NOT EXISTS (
    SELECT 1 FROM type_set_item i
      WHERE i.set_id = rule_matches.set_id AND i.coin_type_id = rule_matches.coin_type_id
  )
),
have AS (
  SELECT ct.id AS coin_type_id, SUM(l.qty_remaining) AS qty_on_hand
  FROM lot l
  JOIN coin_type ct ON ct.id = l.coin_type_id
  WHERE l.qty_remaining > 0
  GROUP BY ct.id
)
SELECT
  ts.id            AS set_id,
  ts.name          AS set_name,
  cm.country, cm.denomination, cm.series,
  ct.year, ct.mint_mark, ct.variety, ct.is_proof,
  items.coin_type_id,
  items.required_qty,
  COALESCE(have.qty_on_hand, 0) AS have_qty,
  CASE WHEN COALESCE(have.qty_on_hand,0) >= items.required_qty THEN 1 ELSE 0 END AS is_complete
FROM items
JOIN type_set ts      ON ts.id = items.set_id
JOIN coin_type ct     ON ct.id = items.coin_type_id
JOIN coin_master cm   ON cm.id = ct.master_id
LEFT JOIN have        ON have.coin_type_id = items.coin_type_id;

-- Ensure Specimen table exists for Flip IDs
CREATE TABLE IF NOT EXISTS specimen (
  id INTEGER PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,          -- Flip ID
  coin_type_id INTEGER NOT NULL REFERENCES coin_type(id),
  lot_id INTEGER REFERENCES lot(id),
  sold_line_id INTEGER REFERENCES tx_line(id),
  notes TEXT
);

-- Fulfillment links from set items to specific specimens
CREATE TABLE IF NOT EXISTS type_set_fulfillment (
  id INTEGER PRIMARY KEY,
  set_id INTEGER NOT NULL REFERENCES type_set(id) ON DELETE CASCADE,
  coin_type_id INTEGER NOT NULL REFERENCES coin_type(id) ON DELETE CASCADE,
  specimen_code TEXT NOT NULL REFERENCES specimen(code),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (set_id, coin_type_id, specimen_code),
  UNIQUE (specimen_code)
);

-- Assignment details view
CREATE VIEW IF NOT EXISTS v_type_set_assignments AS
SELECT
  f.set_id,
  f.coin_type_id,
  f.specimen_code,
  s.sold_line_id IS NULL AS on_hand,
  cm.series, ct.year, ct.mint_mark, ct.variety
FROM type_set_fulfillment f
JOIN specimen s   ON s.code = f.specimen_code
JOIN coin_type ct ON ct.id = f.coin_type_id
JOIN coin_master cm ON cm.id = ct.master_id;

-- Augmented progress view with assigned counts + codes
CREATE VIEW IF NOT EXISTS v_type_set_progress_assign AS
WITH base AS (
  SELECT * FROM v_type_set_progress
),
assigns AS (
  SELECT set_id, coin_type_id,
         SUM(CASE WHEN on_hand THEN 1 ELSE 0 END) AS assigned_onhand_qty,
         GROUP_CONCAT(specimen_code, ',') AS assigned_codes_csv
  FROM v_type_set_assignments
  GROUP BY set_id, coin_type_id
)
SELECT
  b.*,
  COALESCE(a.assigned_onhand_qty, 0) AS assigned_onhand_qty,
  COALESCE(a.assigned_codes_csv, '')  AS assigned_codes_csv,
  CASE WHEN COALESCE(a.assigned_onhand_qty,0) >= b.required_qty THEN 1 ELSE 0 END AS is_complete_by_assignment
FROM base b
LEFT JOIN assigns a
  ON a.set_id = b.set_id AND a.coin_type_id = b.coin_type_id;