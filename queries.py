# queries.py (with specimen support)
from typing import List, Optional, Tuple
from db import get_conn

# ---------- Helpers ----------

def _fetchone(cx, query, params=()):
    cur = cx.execute(query, params)
    return cur.fetchone()

def _fetchall(cx, query, params=()):
    cur = cx.execute(query, params)
    return cur.fetchall()

# ---------- Reference data CRUD ----------

def upsert_party(name: str, kind: str = None, contact: str = None) -> Optional[int]:
    if not name:
        return None
    with get_conn() as cx:
        row = _fetchone(cx, "SELECT id FROM party WHERE name = ?", (name,))
        if row:
            return row[0]
        cur = cx.execute("INSERT INTO party(name, kind, contact) VALUES (?,?,?)", (name, kind, contact))
        return cur.lastrowid

def upsert_storage(name: str, category: str = None, description: str = None) -> Optional[int]:
    if not name:
        return None
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
    mint_mark = (mint_mark or '').strip()
    if mint_mark in ('-','—','None','nan','NaN'):
        mint_mark = ''
    variety = (variety or '').strip()
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
            SELECT ct.id, cm.series, ct.year, ct.mint_mark, COALESCE(ct.variety,'') AS variety
            FROM coin_type ct JOIN coin_master cm ON cm.id=ct.master_id
            ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety
        """)
        return [dict(row) for row in rows]

# ---------- Transactions ----------

def _allocate_buy_costs(lines: List[dict], shipping: float, tax: float, fees: float) -> List[float]:
    alloc_total = float(shipping or 0) + float(tax or 0) + float(fees or 0)
    subtotals = [(l["quantity"] or 0) * (l["unit_price"] or 0.0) for l in lines]
    tx_subtotal = sum(subtotals)
    if alloc_total <= 0 or tx_subtotal <= 0:
        return [0.0 for _ in lines]
    addons = []
    for st, l in zip(subtotals, lines):
        share = alloc_total * (st / tx_subtotal) if tx_subtotal else 0.0
        per_coin = share / l["quantity"] if l["quantity"] else 0.0
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
):
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
):
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

# ---------- Inventory & dashboard queries ----------

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
            JOIN coin_type ct ON ct.id=l.coin_type_id
            JOIN coin_master cm ON cm.id=ct.master_id
            ORDER BY l.acquired_date DESC, l.id DESC
        """)
        return [dict(r) for r in rows]

def inventory_by_type() -> List[dict]:
    with get_conn() as cx:
        rows = _fetchall(cx, "SELECT * FROM v_inventory_by_type ORDER BY series, year")
        return [dict(r) for r in rows]

def inventory_by_series_summary() -> List[dict]:
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
        rows = _fetchall(cx, "SELECT id, name, COALESCE(category,'') AS category FROM storage_location ORDER BY name")
        return [dict(r) for r in rows]

# ---------- NEW: Series codes & specimens ----------

def upsert_series_code(series: str, prefix: str) -> None:
    """Define or update the prefix for a series (e.g., 'Peace' -> 'P', 'Morgan' -> 'M')."""
    series = series.strip()
    prefix = prefix.strip().upper()
    if not series or not prefix:
        raise ValueError("series and prefix are required")
    with get_conn() as cx:
        row = _fetchone(cx, "SELECT series FROM series_code WHERE series=?", (series,))
        if row:
            cx.execute("UPDATE series_code SET prefix=? WHERE series=?", (prefix, series))
        else:
            cx.execute("INSERT INTO series_code(series, prefix) VALUES (?,?)", (series, prefix))

def _get_series_for_type(coin_type_id: int) -> str:
    with get_conn() as cx:
        row = _fetchone(cx, """
            SELECT cm.series
            FROM coin_type ct JOIN coin_master cm ON cm.id = ct.master_id
            WHERE ct.id = ?
        """, (coin_type_id,))
        if not row:
            raise ValueError("Unknown coin_type_id")
        return row["series"]

def allocate_specimen_code_for_series(series: str) -> str:
    """Return next code like 'P17' for a series, incrementing the sequence."""
    with get_conn() as cx:
        row = _fetchone(cx, "SELECT prefix, next_seq FROM series_code WHERE series=?", (series,))
        if not row:
            # default prefix = first letters of first two words
            words = [w for w in series.replace('/', ' ').split() if w]
            default_prefix = ''.join([w[0] for w in words[:2]]).upper() or 'X'
            cx.execute("INSERT INTO series_code(series, prefix, next_seq) VALUES (?,?,?)",
                       (series, default_prefix, 1))
            prefix, seq = default_prefix, 1
        else:
            prefix, seq = row["prefix"], row["next_seq"]
        code = f"{prefix}{seq}"
        cx.execute("UPDATE series_code SET next_seq = ? WHERE series=?", (seq + 1, series))
        return code

def create_specimen(coin_type_id: int, lot_id: int = None, code: str = None, notes: str = None) -> Tuple[int, str]:
    """Create a specimen (per-coin ID). If code is None, allocate from series prefix/sequence."""
    series = _get_series_for_type(coin_type_id)
    if code is None:
        code = allocate_specimen_code_for_series(series)
    with get_conn() as cx:
        cur = cx.execute(
            "INSERT INTO specimen(code, coin_type_id, lot_id, notes) VALUES (?,?,?,?)",
            (code, coin_type_id, lot_id, notes),
        )
        specimen_id = cur.lastrowid
    return specimen_id, code

def create_specimens_for_lot(lot_id: int, quantity: int, start_code: str = None) -> List[str]:
    """Create 'quantity' specimens for a lot; returns list of codes. If start_code is given, use it for the first and then auto-allocate the rest from the same series."""
    if quantity <= 0:
        return []
    with get_conn() as cx:
        row = _fetchone(cx, "SELECT coin_type_id FROM lot WHERE id=?", (lot_id,))
        if not row:
            raise ValueError("Unknown lot_id")
        coin_type_id = row["coin_type_id"]
    codes = []
    first_code = start_code
    for i in range(quantity):
        code = first_code if (i == 0 and first_code) else None
        _, c = create_specimen(coin_type_id=coin_type_id, lot_id=lot_id, code=code)
        codes.append(c)
    return codes

def get_specimen_by_code(code: str) -> Optional[dict]:
    with get_conn() as cx:
        row = _fetchone(cx, """
            SELECT sp.code,
                   cm.series, ct.year, ct.mint_mark, ct.variety,
                   sp.lot_id, sp.sold_line_id,
                   CASE WHEN sp.sold_line_id IS NULL THEN 'ON_HAND' ELSE 'SOLD' END AS status
            FROM specimen sp
            JOIN coin_type ct ON ct.id = sp.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE sp.code = ?
        """, (code,))
        return dict(row) if row else None

def list_specimens_on_hand(series: str = None) -> List[dict]:
    """List current specimens (not sold). Optional filter by series name."""
    with get_conn() as cx:
        if series:
            rows = _fetchall(cx, """
                SELECT sp.code, cm.series, ct.year, ct.mint_mark, ct.variety, sp.lot_id
                FROM specimen sp
                JOIN coin_type ct ON ct.id = sp.coin_type_id
                JOIN coin_master cm ON cm.id = ct.master_id
                WHERE sp.sold_line_id IS NULL AND cm.series = ?
                ORDER BY sp.code
            """, (series,))
        else:
            rows = _fetchall(cx, """
                SELECT sp.code, cm.series, ct.year, ct.mint_mark, ct.variety, sp.lot_id
                FROM specimen sp
                JOIN coin_type ct ON ct.id = sp.coin_type_id
                JOIN coin_master cm ON cm.id = ct.master_id
                WHERE sp.sold_line_id IS NULL
                ORDER BY cm.series, sp.code
            """)
        return [dict(r) for r in rows]
