# schema_sql.py (canonical, includes numista_url on coin_master)

SCHEMA_SQL = r"""
PRAGMA foreign_keys = ON;

/* ---------- Reference: coin master & types ---------- */
CREATE TABLE IF NOT EXISTS coin_master (
  id              INTEGER PRIMARY KEY,
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
  notes           TEXT,
  asset_category  TEXT NOT NULL DEFAULT 'COIN',
  numista_url     TEXT,
  UNIQUE(country, denomination, series)
);
CREATE INDEX IF NOT EXISTS idx_coin_master_series ON coin_master(series);
CREATE INDEX IF NOT EXISTS idx_coin_master_numista_url ON coin_master(numista_url);

/* (rest of your schema here; unchanged) */
"""
