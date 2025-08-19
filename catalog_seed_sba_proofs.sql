
-- catalog_seed_sba_proofs.sql
PRAGMA foreign_keys = ON;

-- Ensure master record for Susan B. Anthony exists
INSERT OR IGNORE INTO coin_master (country, denomination, series)
VALUES ('USA','Dollar','Susan B. Anthony');

-- Insert the six proof types (1979-S T1, 1979-S T2, 1980-S, 1981-S T1, 1981-S T2, 1999-P)
INSERT OR IGNORE INTO coin_type (master_id, year, mint_mark, variety, is_proof)
SELECT id, 1979, 'S', 'Type 1', 1
FROM coin_master WHERE country='USA' AND denomination='Dollar' AND series='Susan B. Anthony';

INSERT OR IGNORE INTO coin_type (master_id, year, mint_mark, variety, is_proof)
SELECT id, 1979, 'S', 'Type 2', 1
FROM coin_master WHERE country='USA' AND denomination='Dollar' AND series='Susan B. Anthony';

INSERT OR IGNORE INTO coin_type (master_id, year, mint_mark, variety, is_proof)
SELECT id, 1980, 'S', '', 1
FROM coin_master WHERE country='USA' AND denomination='Dollar' AND series='Susan B. Anthony';

INSERT OR IGNORE INTO coin_type (master_id, year, mint_mark, variety, is_proof)
SELECT id, 1981, 'S', 'Type 1', 1
FROM coin_master WHERE country='USA' AND denomination='Dollar' AND series='Susan B. Anthony';

INSERT OR IGNORE INTO coin_type (master_id, year, mint_mark, variety, is_proof)
SELECT id, 1981, 'S', 'Type 2', 1
FROM coin_master WHERE country='USA' AND denomination='Dollar' AND series='Susan B. Anthony';

INSERT OR IGNORE INTO coin_type (master_id, year, mint_mark, variety, is_proof)
SELECT id, 1999, 'P', '', 1
FROM coin_master WHERE country='USA' AND denomination='Dollar' AND series='Susan B. Anthony';
