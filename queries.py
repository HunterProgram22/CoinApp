
# queries.py
from typing import List, Optional, Tuple
from db import get_conn

# ------------------------------------------------------------------
# Normalization helpers
# ------------------------------------------------------------------
NAN_LIKE = {"nan", "none", "-", "—"}

def _norm_text(x: Optional[str]) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    return "" if s.lower() in NAN_LIKE else s

# ------------------------------------------------------------------
# Small sqlite helpers
# ------------------------------------------------------------------
def _fetchone(cx, query, params=()):
    cur = cx.execute(query, params)
    return cur.fetchone()

def _fetchall(cx, query, params=()):
    cur = cx.execute(query, params)
    return cur.fetchall()

# ------------------------------------------------------------------
# Reference data CRUD
# ------------------------------------------------------------------
def upsert_party(name: str, kind: str = None, contact: str = None) -> Optional[int]:
    if not name:
        return None
    with get_conn() as cx:
        row = _fetchone(cx, "SELECT id FROM party WHERE name = ?", (name.strip(),))
        if row:
            return row[0]
        cur = cx.execute("INSERT INTO party(name, kind, contact) VALUES (?,?,?)",
                         (name.strip(), kind, contact))
        return cur.lastrowid

def upsert_storage(name: str, category: str = None, description: str = None) -> Optional[int]:
    if not name:
        return None
    name = name.strip()
    with get_conn() as cx:
        row = _fetchone(cx, "SELECT id FROM storage_location WHERE name = ?", (name,))
        if row:
            return row[0]
        cur = cx.execute(
            "INSERT INTO storage_location(name, category, description) VALUES (?,?,?)",
            (name, category, description),
        )
        return cur.lastrowid

def upsert_coin_master(country: str, denomination: str, series: str,
                       metal: str = None, fineness: float = None, weight_grams: float = None,
                       diameter_mm: float = None, thickness_mm: float = None, edge: str = None,
                       years_start: int = None, years_end: int = None, notes: str = None) -> int:
    country = country.strip()
    denomination = denomination.strip()
    series = series.strip()
    with get_conn() as cx:
        row = _fetchone(cx, "SELECT id FROM coin_master WHERE country=? AND denomination=? AND series=?",
                        (country, denomination, series))
        if row:
            return row[0]
        cur = cx.execute(
            """
            INSERT INTO coin_master(country, denomination, series, metal, fineness, weight_grams,
                                    diameter_mm, thickness_mm, edge, years_start, years_end, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (country, denomination, series, metal, fineness, weight_grams,
             diameter_mm, thickness_mm, edge, years_start, years_end, notes),
        )
        return cur.lastrowid

def upsert_coin_type(master_id: int, year: int, mint_mark: str = None, variety: str = None,
                     mintage: int = None, is_proof: int = 0, designer: str = None,
                     obv_desc: str = None, rev_desc: str = None) -> int:
    mint_mark = _norm_text(mint_mark)
    variety = _norm_text(variety)
    with get_conn() as cx:
        row = _fetchone(cx, """
            SELECT id FROM coin_type
             WHERE master_id=? AND year=? AND mint_mark=? AND variety=?
        """, (master_id, year, mint_mark, variety))
        if row:
            return row[0]
        cur = cx.execute(
            """
            INSERT INTO coin_type(master_id, year, mint_mark, variety, mintage, is_proof, designer, obv_desc, rev_desc)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (master_id, year, mint_mark, variety, mintage, is_proof, designer, obv_desc, rev_desc),
        )
        return cur.lastrowid

def list_coin_types() -> List[dict]:
    with get_conn() as cx:
        rows = _fetchall(cx, """
            SELECT ct.id,
                   cm.series, ct.year,
                   COALESCE(NULLIF(TRIM(ct.mint_mark), ''), '') AS mint_mark,
                   COALESCE(NULLIF(TRIM(ct.variety), ''), '')   AS variety
              FROM coin_type ct
              JOIN coin_master cm ON cm.id = ct.master_id
             ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety
        """)
        return [dict(r) for r in rows]

# ------------------------------------------------------------------
# Transactions
# ------------------------------------------------------------------
def _allocate_buy_costs(lines: List[dict], shipping: float, tax: float, fees: float) -> List[float]:
    """
    Proportionally allocate shipping+tax+fees across BUY lines based on line subtotal.
    Each line dict must contain: quantity, unit_price.
    Returns a list of per-coin add-ons to unit_price.
    """
    alloc_total = float(shipping or 0) + float(tax or 0) + float(fees or 0)
    subtotals = [(l.get("quantity") or 0) * (l.get("unit_price") or 0.0) for l in lines]
    tx_subtotal = sum(subtotals)
    if alloc_total <= 0 or tx_subtotal <= 0:
        return [0.0 for _ in lines]
    addons = []
    for st, l in zip(subtotals, lines):
        share = alloc_total * (st / tx_subtotal) if tx_subtotal else 0.0
        per_coin = share / (l.get("quantity") or 1)
        addons.append(per_coin)
    return addons

def create_buy_transaction(
    tx_date: str,
    party_name: str,
    currency: str,
    shipping: float,
    tax: float,
    fees: float,
    notes: str,
    items: List[dict],
) -> bool:
    """
    items: list of dicts with keys:
      coin_type_id, quantity, unit_price,
      purchase_grade_company, purchase_grade_text, purchase_numeric_grade, slab_cert,
      estimated_grade_text, estimated_numeric_grade,
      valuation_method ('AUTO'|'MELT_ONLY'|'GUIDE_ONLY'|'MANUAL'), manual_est_unit_value,
      storage_location_id, lot_notes
    """
    party_id = upsert_party(party_name) if party_name else None
    with get_conn() as cx:
        cur = cx.execute(
            "INSERT INTO tx(tx_date, tx_type, party_id, currency, shipping, tax, fees, notes) VALUES (?,?,?,?,?,?,?,?)",
            (tx_date, 'BUY', party_id, currency or 'USD', shipping or 0.0, tax or 0.0, fees or 0.0, notes),
        )
        tx_id = cur.lastrowid

        addons = _allocate_buy_costs(items, shipping, tax, fees)
        for line, addon in zip(items, addons):
            cur = cx.execute(
                """
                INSERT INTO tx_line(tx_id, coin_type_id, quantity, unit_price, grade_company, grade_text, numeric_grade, slab_cert, condition_notes)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (tx_id, line["coin_type_id"], line["quantity"], line.get("unit_price"),
                 line.get("purchase_grade_company"), line.get("purchase_grade_text"), line.get("purchase_numeric_grade"),
                 line.get("slab_cert"), None),
            )
            line_id = cur.lastrowid

            unit_cost = (line.get("unit_price") or 0.0) + addon
            cx.execute(
                """
                INSERT INTO lot(
                    acquisition_line_id, coin_type_id, acquired_date, qty_acquired, qty_remaining, unit_cost,
                    storage_location_id,
                    purchase_grade_company, purchase_grade_text, purchase_numeric_grade, slab_cert,
                    estimated_grade_text, estimated_numeric_grade,
                    valuation_method, manual_est_unit_value, status, notes
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    line_id, line["coin_type_id"], tx_date, line["quantity"], line["quantity"], unit_cost,
                    line.get("storage_location_id"),
                    line.get("purchase_grade_company"), line.get("purchase_grade_text"), line.get("purchase_numeric_grade"), line.get("slab_cert"),
                    line.get("estimated_grade_text"), line.get("estimated_numeric_grade"),
                    (line.get("valuation_method") or 'AUTO'), line.get("manual_est_unit_value"), 'OPEN', line.get("lot_notes"),
                ),
            )
    return True

def create_sell_transaction(
    tx_date: str,
    party_name: str,
    currency: str,
    shipping: float,
    tax: float,
    fees: float,
    notes: str,
    items: List[dict],
    method: str = 'FIFO'
) -> bool:
    """
    items: list of dicts with keys: coin_type_id, quantity, unit_price
    method: currently supports 'FIFO' only.
    """
    if method != 'FIFO':
        raise NotImplementedError("Only FIFO is implemented in this starter")

    party_id = upsert_party(party_name) if party_name else None
    with get_conn() as cx:
        cur = cx.execute(
            "INSERT INTO tx(tx_date, tx_type, party_id, currency, shipping, tax, fees, notes) VALUES (?,?,?,?,?,?,?,?)",
            (tx_date, 'SELL', party_id, currency or 'USD', shipping or 0.0, tax or 0.0, fees or 0.0, notes),
        )
        tx_id = cur.lastrowid

        for line in items:
            cur = cx.execute(
                "INSERT INTO tx_line(tx_id, coin_type_id, quantity, unit_price) VALUES (?,?,?,?)",
                (tx_id, line["coin_type_id"], -abs(line["quantity"]), line.get("unit_price")),
            )
            sell_line_id = cur.lastrowid

            # FIFO relieve from oldest OPEN lots
            remaining = abs(line["quantity"])
            lots = _fetchall(cx, """
                SELECT id, qty_remaining FROM lot
                 WHERE coin_type_id=? AND qty_remaining>0
                 ORDER BY acquired_date ASC, id ASC
            """, (line["coin_type_id"],))
            for lot_row in lots:
                if remaining <= 0:
                    break
                lot_id = lot_row["id"]
                avail = lot_row["qty_remaining"]
                take = min(avail, remaining)
                cx.execute(
                    "INSERT INTO lot_relief(lot_id, sell_line_id, quantity, proceeds_per_unit) VALUES (?,?,?,?)",
                    (lot_id, sell_line_id, take, line.get("unit_price")),
                )
                remaining -= take

            if remaining > 0:
                raise ValueError("Not enough inventory to sell the requested quantity")
    return True

# ------------------------------------------------------------------
# Specimen (Flip ID) helpers
# ------------------------------------------------------------------
def _ensure_specimen_tables():
    """Safety: create specimen & series_code tables if schema is older (no-op if already there)."""
    with get_conn() as cx:
        cx.execute("""
        CREATE TABLE IF NOT EXISTS series_code (
            id INTEGER PRIMARY KEY,
            series TEXT NOT NULL UNIQUE,
            prefix TEXT NOT NULL,
            next_seq INTEGER NOT NULL DEFAULT 1
        )""")
        cx.execute("""
        CREATE TABLE IF NOT EXISTS specimen (
            id INTEGER PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,          -- e.g., P1, M23, CB7
            coin_type_id INTEGER NOT NULL REFERENCES coin_type(id),
            lot_id INTEGER REFERENCES lot(id),
            sold_line_id INTEGER REFERENCES tx_line(id),  -- mark when sold
            notes TEXT
        )""")

def upsert_series_code(series: str, prefix: str) -> int:
    _ensure_specimen_tables()
    series = series.strip()
    prefix = prefix.strip().upper()[:3]
    if not series or not prefix:
        raise ValueError("Series and prefix are required.")
    with get_conn() as cx:
        row = _fetchone(cx, "SELECT id FROM series_code WHERE series=?", (series,))
        if row:
            cx.execute("UPDATE series_code SET prefix=? WHERE id=?", (prefix, row["id"]))
            return row["id"]
        cur = cx.execute("INSERT INTO series_code(series, prefix, next_seq) VALUES (?,?,1)", (series, prefix))
        return cur.lastrowid

def _allocate_code(series: str, qty: int) -> List[str]:
    _ensure_specimen_tables()
    series = series.strip()
    with get_conn() as cx:
        sc = _fetchone(cx, "SELECT id, prefix, next_seq FROM series_code WHERE series=?", (series,))
        if not sc:
            raise ValueError(f"No prefix set for series '{series}'. Set it in Specimens page.")
        start = sc["next_seq"]
        codes = [f"{sc['prefix']}{i}" for i in range(start, start + qty)]
        cx.execute("UPDATE series_code SET next_seq = ? WHERE id=?", (start + qty, sc["id"]))
        return codes

def allocate_specimen_code_for_series(series: str) -> str:
    return _allocate_code(series, 1)[0]

def create_specimens_for_lot(lot_id: int, qty: int, start_code: str = None) -> List[str]:
    _ensure_specimen_tables()
    if qty <= 0:
        return []
    with get_conn() as cx:
        lot = _fetchone(cx, """
            SELECT l.id, l.coin_type_id, cm.series
              FROM lot l
              JOIN coin_type ct ON ct.id = l.coin_type_id
              JOIN coin_master cm ON cm.id = ct.master_id
             WHERE l.id=?
        """, (lot_id,))
        if not lot:
            raise ValueError("Unknown lot_id")
        series = lot["series"]
        coin_type_id = lot["coin_type_id"]

        # Determine codes to create
        codes: List[str] = []
        if start_code:
            # Sequential from a provided starting code prefix+number
            s = start_code.strip().upper()
            # find numeric tail
            import re
            m = re.match(r"([A-Z]+)(\d+)$", s)
            if not m:
                raise ValueError("start_code must look like P101 or CB7 (letters+digits).")
            prefix, n = m.group(1), int(m.group(2))
            codes = [f"{prefix}{n+i}" for i in range(qty)]
        else:
            codes = _allocate_code(series, qty)

        created = []
        for code in codes:
            # skip existing
            exists = _fetchone(cx, "SELECT 1 FROM specimen WHERE code=?", (code,))
            if exists:
                continue
            cx.execute("INSERT INTO specimen(code, coin_type_id, lot_id) VALUES (?,?,?)",
                       (code, coin_type_id, lot_id))
            created.append(code)
        return created

def get_specimen_by_code(code: str) -> Optional[dict]:
    _ensure_specimen_tables()
    code = code.strip().upper()
    with get_conn() as cx:
        row = _fetchone(cx, """
            SELECT s.code, s.notes, s.lot_id, s.sold_line_id,
                   cm.series, ct.year, ct.mint_mark, ct.variety
              FROM specimen s
              JOIN coin_type ct ON ct.id = s.coin_type_id
              JOIN coin_master cm ON cm.id = ct.master_id
             WHERE s.code = ?
        """, (code,))
        return dict(row) if row else None

def list_specimens_on_hand(filter_series: str = None) -> List[dict]:
    _ensure_specimen_tables()
    params: Tuple = tuple()
    where = "WHERE s.sold_line_id IS NULL"
    if filter_series and filter_series.strip():
        where += " AND cm.series LIKE ?"
        params = (f"%{filter_series.strip()}%",)
    with get_conn() as cx:
        rows = _fetchall(cx, f"""
            SELECT s.code, cm.series, ct.year, ct.mint_mark, ct.variety, s.lot_id
              FROM specimen s
              JOIN coin_type ct ON ct.id = s.coin_type_id
              JOIN coin_master cm ON cm.id = ct.master_id
              {where}
             ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety, s.code
        """, params)
        return [dict(r) for r in rows]

# ------------------------------------------------------------------
# Queries for pages
# ------------------------------------------------------------------
def get_portfolio_summary() -> dict:
    with get_conn() as cx:
        row = _fetchone(cx, "SELECT total_estimated_value_usd, total_coins FROM v_portfolio_value_summary")
        if not row:
            return {"total_estimated_value_usd": 0.0, "total_coins": 0}
        total_value = row["total_estimated_value_usd"] if row["total_estimated_value_usd"] is not None else 0.0
        total_coins = row["total_coins"] if row["total_coins"] is not None else 0
        return {"total_estimated_value_usd": total_value, "total_coins": total_coins}

def get_latest_spot() -> List[dict]:
    with get_conn() as cx:
        rows = _fetchall(cx, "SELECT metal, price_per_oz_usd FROM v_latest_spot")
        return [dict(r) for r in rows]

def list_lots() -> List[dict]:
    with get_conn() as cx:
        rows = _fetchall(cx, """
            SELECT l.id, cm.series, ct.year, ct.mint_mark, COALESCE(ct.variety,'') AS variety,
                   l.qty_remaining, l.unit_cost, l.valuation_method,
                   COALESCE(l.estimated_grade_text, l.purchase_grade_text) AS grade,
                   l.manual_est_unit_value
              FROM lot l
              JOIN coin_type ct ON ct.id = l.coin_type_id
              JOIN coin_master cm ON cm.id = ct.master_id
             ORDER BY l.acquired_date DESC, l.id DESC
        """)
        return [dict(r) for r in rows]

def inventory_by_type() -> List[dict]:
    with get_conn() as cx:
        rows = _fetchall(cx, "SELECT * FROM v_inventory_by_type ORDER BY series, year, mint_mark, variety")
        return [dict(r) for r in rows]

def inventory_by_series_summary() -> List[dict]:
    """Series-level summary: coins & estimated value across all years/mints."""
    with get_conn() as cx:
        rows = _fetchall(cx, """
            SELECT
              series,
              SUM(qty_remaining)                AS coins,
              ROUND(SUM(qty_remaining * COALESCE(chosen_unit_value,0)), 2) AS est_value_usd
              FROM v_lot_value_details
             GROUP BY series
             ORDER BY est_value_usd DESC, series
        """)
        return [dict(r) for r in rows]

def list_storage_locations() -> List[dict]:
    with get_conn() as cx:
        rows = _fetchall(cx, "SELECT id, name, COALESCE(category,'') AS category, COALESCE(description,'') AS description FROM storage_location ORDER BY name")
        return [dict(r) for r in rows]

def search_transactions(date_from: Optional[str] = None,
                        date_to: Optional[str] = None,
                        tx_types: Optional[list] = None,
                        party_query: Optional[str] = None,
                        limit: int = 25,
                        offset: int = 0) -> List[dict]:
    """Return tx headers with optional filters. Dates are ISO 'YYYY-MM-DD'."""
    where = []
    params = []
    if date_from:
        where.append("t.tx_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("t.tx_date <= ?")
        params.append(date_to)
    if tx_types:
        qs = ",".join(["?"] * len(tx_types))
        where.append(f"t.tx_type IN ({qs})")
        params.extend(tx_types)
    if party_query:
        where.append("COALESCE(p.name, '') LIKE ?")
        params.append(f"%{party_query}%")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"""
        SELECT
          t.id, t.tx_date, t.tx_type,
          p.name AS party,
          t.currency, t.shipping, t.tax, t.fees, t.notes
        FROM tx t
        LEFT JOIN party p ON p.id = t.party_id
        {where_sql}
        ORDER BY t.tx_date DESC, t.id DESC
        LIMIT ? OFFSET ?
    """
    params.extend([int(limit), int(offset)])
    with get_conn() as cx:
        rows = cx.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

def get_tx_lines(tx_id: int) -> List[dict]:
    with get_conn() as cx:
        rows = cx.execute("""
            SELECT
              tl.id AS line_id,
              cm.series, ct.year, ct.mint_mark, COALESCE(ct.variety,'') AS variety,
              ABS(tl.quantity) AS quantity, tl.unit_price,
              tl.grade_company, tl.grade_text, tl.numeric_grade, tl.slab_cert
            FROM tx_line tl
            LEFT JOIN coin_type ct ON ct.id = tl.coin_type_id
            LEFT JOIN coin_master cm ON cm.id = ct.master_id
            WHERE tl.tx_id = ?
            ORDER BY tl.id
        """, (tx_id,)).fetchall()
        return [dict(r) for r in rows]

def spending_log(date_from: Optional[str] = None,
                 date_to: Optional[str] = None,
                 party_query: Optional[str] = None,
                 limit: int = 25,
                 offset: int = 0) -> List[dict]:
    """Return total BUY spending grouped by (tx_date, party).
    spent_usd = sum(line quantity * unit_price) + shipping + tax + fees, summed across all BUY tx per group.
    Dates are ISO 'YYYY-MM-DD'. Currency handling assumes USD."""
    where = ["t.tx_type = 'BUY'"]
    params = []
    if date_from:
        where.append("t.tx_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("t.tx_date <= ?")
        params.append(date_to)
    if party_query:
        where.append("COALESCE(p.name,'') LIKE ?")
        params.append(f"%{party_query}%")
    where_sql = "WHERE " + " AND ".join(where)

    sql = f"""
        WITH buys AS (
          SELECT t.id, t.tx_date, COALESCE(p.name,'') AS party,
                 COALESCE(t.shipping,0) AS shipping, COALESCE(t.tax,0) AS tax, COALESCE(t.fees,0) AS fees
          FROM tx t
          LEFT JOIN party p ON p.id = t.party_id
          {where_sql}
        ),
        line_sub AS (
          SELECT tl.tx_id, SUM(ABS(tl.quantity) * COALESCE(tl.unit_price,0)) AS line_subtotal
          FROM tx_line tl
          JOIN tx t2 ON t2.id = tl.tx_id AND t2.tx_type = 'BUY'
          GROUP BY tl.tx_id
        )
        SELECT b.tx_date, b.party,
               ROUND(SUM(COALESCE(ls.line_subtotal,0) + b.shipping + b.tax + b.fees), 2) AS spent_usd
        FROM buys b
        LEFT JOIN line_sub ls ON ls.tx_id = b.id
        GROUP BY b.tx_date, b.party
        ORDER BY b.tx_date DESC, b.party
        LIMIT ? OFFSET ?
    """
    params.extend([int(limit), int(offset)])
    with get_conn() as cx:
        rows = cx.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

def spending_log_items(tx_date: str, party: Optional[str]) -> List[dict]:
    """Return list of {series, qty} for all BUY lines on a given date+party."""
    where = ["t.tx_type = 'BUY'", "t.tx_date = ?"]
    params = [tx_date]
    if party is None or party == '':
        where.append("COALESCE(p.name,'') = ''")
    else:
        where.append("COALESCE(p.name,'') = ?")
        params.append(party)
    where_sql = "WHERE " + " AND ".join(where)
    sql = f"""
        SELECT cm.series, SUM(ABS(tl.quantity)) AS qty
        FROM tx t
        LEFT JOIN party p ON p.id = t.party_id
        JOIN tx_line tl ON tl.tx_id = t.id
        JOIN coin_type ct ON ct.id = tl.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        {where_sql}
        GROUP BY cm.series
        ORDER BY cm.series
    """
    with get_conn() as cx:
        rows = cx.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

def list_series_for_filter(only_on_hand: bool = True) -> List[str]:
    """Distinct coin series, optionally restricted to those with coins on hand."""
    with get_conn() as cx:
        if only_on_hand:
            rows = cx.execute("""
                SELECT DISTINCT cm.series
                FROM coin_master cm
                JOIN coin_type ct ON ct.master_id = cm.id
                JOIN lot l ON l.coin_type_id = ct.id
                WHERE l.qty_remaining > 0
                ORDER BY cm.series
            """).fetchall()
        else:
            rows = cx.execute("""
                SELECT DISTINCT series FROM coin_master ORDER BY series
            """).fetchall()
        return [r[0] for r in rows]

def inventory_details_by_series(series: str) -> List[dict]:
    """Per-lot detail rows for a given series.
    Columns returned:
      acquired_date, series, year, mint_mark, variety, qty_remaining,
      party, unit_cost_usd, melt_unit_usd, melt_total_usd, grade, flip_ids
    Notes:
      - Flip IDs are aggregated per-lot from a 'specimen' table if present
        with columns (lot_id, specimen_code, sold_line_id).
      - Melt uses v_latest_spot based on coin_master.metal, fineness, weight_grams.
    """
    if not series:
        return []
    with get_conn() as cx:
        # detect whether a 'specimen' table with 'specimen_code' exists
        has_specimen = bool(cx.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='specimen'"
        ).fetchone())
        has_specimen_code = False
        if has_specimen:
            try:
                cx.execute("SELECT specimen_code FROM specimen LIMIT 1")
                has_specimen_code = True
            except Exception:
                has_specimen_code = False

        flip_sql = """
            LEFT JOIN (
              SELECT lot_id, GROUP_CONCAT(specimen_code, ', ') AS flip_ids, COUNT(*) AS flip_count
              FROM specimen
              WHERE sold_line_id IS NULL
              GROUP BY lot_id
            ) sp ON sp.lot_id = l.id
        """ if has_specimen and has_specimen_code else ""

        sql = f"""
            WITH melt AS (
              SELECT metal, price_per_oz_usd FROM v_latest_spot
            )
            SELECT
              l.acquired_date,
              cm.series,
              ct.year,
              ct.mint_mark,
              COALESCE(ct.variety,'') AS variety,
              l.qty_remaining,
              COALESCE(p.name,'') AS party,
              ROUND(l.unit_cost, 2) AS unit_cost_usd,
              -- per-coin melt
              ROUND(
                (cm.weight_grams * COALESCE(cm.fineness,0)) / 31.1034768
                * (SELECT price_per_oz_usd FROM melt WHERE metal = cm.metal),
              2) AS melt_unit_usd,
              -- total melt for remaining qty
              ROUND(
                l.qty_remaining * (cm.weight_grams * COALESCE(cm.fineness,0)) / 31.1034768
                * (SELECT price_per_oz_usd FROM melt WHERE metal = cm.metal),
              2) AS melt_total_usd,
              COALESCE(l.estimated_grade_text, l.purchase_grade_text) AS grade
              {', sp.flip_ids' if (has_specimen and has_specimen_code) else ''}
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            JOIN tx_line tl ON tl.id = l.acquisition_line_id
            JOIN tx t ON t.id = tl.tx_id
            LEFT JOIN party p ON p.id = t.party_id
            {flip_sql}
            WHERE l.qty_remaining > 0 AND cm.series = ?
            ORDER BY ct.year, ct.mint_mark, ct.variety, l.acquired_date
        """
        rows = cx.execute(sql, (series,)).fetchall()
        return [dict(r) for r in rows]

def dashboard_series_rollup() -> List[dict]:
    """Series-level rollup of on-hand inventory.
    Returns: series, coins, melt_total_usd, numi_total_usd, cost_total_usd, chosen_total_usd
    - melt_total_usd: qty_remaining * melt_unit_value
    - numi_total_usd: qty_remaining * guide_unit_value (if any) or manual value if lot is MANUAL; otherwise NULL (ignored in SUM)
    - cost_total_usd: qty_remaining * unit_cost
    - chosen_total_usd: qty_remaining * chosen_unit_value (AUTO/MELT_ONLY/GUIDE_ONLY/MANUAL)
    """
    sql = """
        SELECT
          cm.series AS series,
          SUM(l.qty_remaining) AS coins,
          ROUND(SUM(l.qty_remaining * v.melt_unit_value), 2) AS melt_total_usd,
          ROUND(SUM(
            l.qty_remaining * COALESCE(
              v.guide_unit_value,
              CASE WHEN l.valuation_method = 'MANUAL' THEN l.manual_est_unit_value END
            )
          ), 2) AS numi_total_usd,
          ROUND(SUM(l.qty_remaining * l.unit_cost), 2) AS cost_total_usd,
          ROUND(SUM(l.qty_remaining * v.chosen_unit_value), 2) AS chosen_total_usd
        FROM v_lot_value_details v
        JOIN lot l        ON l.id = v.lot_id
        JOIN coin_type ct ON ct.id = l.coin_type_id
        JOIN coin_master cm ON cm.id = ct.master_id
        GROUP BY cm.series
        ORDER BY chosen_total_usd DESC, cm.series
    """
    with get_conn() as cx:
        rows = cx.execute(sql).fetchall()
        return [dict(r) for r in rows]

def inventory_details_proof() -> List[dict]:
    """Per-lot details for all on-hand PROOF coins (coin_type.is_proof=1)."""
    with get_conn() as cx:
        # Optional specimen join (flip IDs) if table/column exist
        has_specimen = bool(cx.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='specimen'").fetchone())
        has_specimen_code = False
        if has_specimen:
            try:
                cx.execute("SELECT specimen_code FROM specimen LIMIT 1")
                has_specimen_code = True
            except Exception:
                has_specimen_code = False
        flip_sql = """
            LEFT JOIN (
              SELECT lot_id, GROUP_CONCAT(specimen_code, ', ') AS flip_ids, COUNT(*) AS flip_count
              FROM specimen
              WHERE sold_line_id IS NULL
              GROUP BY lot_id
            ) sp ON sp.lot_id = l.id
        """ if (has_specimen and has_specimen_code) else ""

        sql = f"""
            WITH melt AS (SELECT metal, price_per_oz_usd FROM v_latest_spot)
            SELECT
              l.acquired_date,
              cm.series,
              ct.year,
              ct.mint_mark,
              COALESCE(ct.variety,'') AS variety,
              l.qty_remaining,
              COALESCE(p.name,'') AS party,
              ROUND(l.unit_cost, 2) AS unit_cost_usd,
              ROUND((cm.weight_grams * COALESCE(cm.fineness,0)) / 31.1034768
                    * (SELECT price_per_oz_usd FROM melt WHERE metal = cm.metal), 2) AS melt_unit_usd,
              ROUND(l.qty_remaining * (cm.weight_grams * COALESCE(cm.fineness,0)) / 31.1034768
                    * (SELECT price_per_oz_usd FROM melt WHERE metal = cm.metal), 2) AS melt_total_usd,
              COALESCE(l.estimated_grade_text, l.purchase_grade_text) AS grade
              {', sp.flip_ids' if (has_specimen and has_specimen_code) else ''},
              ct.is_proof
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            JOIN tx_line tl ON tl.id = l.acquisition_line_id
            JOIN tx t ON t.id = tl.tx_id
            LEFT JOIN party p ON p.id = t.party_id
            {flip_sql}
            WHERE l.qty_remaining > 0 AND ct.is_proof = 1
            ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety, l.acquired_date
        """
        rows = cx.execute(sql).fetchall()
        return [dict(r) for r in rows]

def inventory_details_slabbed() -> List[dict]:
    """Per-lot details for all on-hand coins with a slab certificate number."""
    with get_conn() as cx:
        # Optional specimen join (flip IDs)
        has_specimen = bool(cx.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='specimen'").fetchone())
        has_specimen_code = False
        if has_specimen:
            try:
                cx.execute("SELECT specimen_code FROM specimen LIMIT 1")
                has_specimen_code = True
            except Exception:
                has_specimen_code = False
        flip_sql = """
            LEFT JOIN (
              SELECT lot_id, GROUP_CONCAT(specimen_code, ', ') AS flip_ids, COUNT(*) AS flip_count
              FROM specimen
              WHERE sold_line_id IS NULL
              GROUP BY lot_id
            ) sp ON sp.lot_id = l.id
        """ if (has_specimen and has_specimen_code) else ""

        sql = f"""
            WITH melt AS (SELECT metal, price_per_oz_usd FROM v_latest_spot)
            SELECT
              l.acquired_date,
              cm.series,
              ct.year,
              ct.mint_mark,
              COALESCE(ct.variety,'') AS variety,
              l.qty_remaining,
              COALESCE(p.name,'') AS party,
              ROUND(l.unit_cost, 2) AS unit_cost_usd,
              ROUND((cm.weight_grams * COALESCE(cm.fineness,0)) / 31.1034768
                    * (SELECT price_per_oz_usd FROM melt WHERE metal = cm.metal), 2) AS melt_unit_usd,
              ROUND(l.qty_remaining * (cm.weight_grams * COALESCE(cm.fineness,0)) / 31.1034768
                    * (SELECT price_per_oz_usd FROM melt WHERE metal = cm.metal), 2) AS melt_total_usd,
              COALESCE(l.estimated_grade_text, l.purchase_grade_text) AS grade,
              l.slab_cert
              {', sp.flip_ids' if (has_specimen and has_specimen_code) else ''}
            FROM lot l
            JOIN coin_type ct ON ct.id = l.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            JOIN tx_line tl ON tl.id = l.acquisition_line_id
            JOIN tx t ON t.id = tl.tx_id
            LEFT JOIN party p ON p.id = t.party_id
            {flip_sql}
            WHERE l.qty_remaining > 0
              AND l.slab_cert IS NOT NULL
              AND TRIM(l.slab_cert) <> ''
            ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety, l.acquired_date
        """
        rows = cx.execute(sql).fetchall()
        return [dict(r) for r in rows]

def bullion_by_category():
    """Summary of bullion (ROUND/BAR) totals by category & metal."""
    with get_conn() as cx:
        rows = cx.execute("""
            SELECT category, metal, units_on_hand, gross_oz, fine_oz, melt_value_usd
            FROM v_inventory_bullion_by_category
            ORDER BY category, metal
        """).fetchall()
        return [dict(r) for r in rows]

def bullion_by_series():
    """Summary of bullion (ROUND/BAR) totals by series (product), including unit oz and fine oz."""
    with get_conn() as cx:
        rows = cx.execute("""
            SELECT category, metal, series, unit_troy_oz, unit_fine_oz, units_on_hand, gross_oz, fine_oz, melt_value_usd
            FROM v_inventory_bullion_by_series
            ORDER BY category, metal, series
        """).fetchall()
        return [dict(r) for r in rows]

