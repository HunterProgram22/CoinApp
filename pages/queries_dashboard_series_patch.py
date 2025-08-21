
# ---- PATCH: Dashboard series rollup ----
from typing import List
from db import get_conn

def dashboard_series_rollup() -> List[dict]:
    """Series-level rollup of on-hand inventory.
    Returns: series, coins, melt_total_usd, numi_total_usd, cost_total_usd, chosen_total_usd
    - melt_total_usd: qty_remaining * melt_unit_value
    - numi_total_usd: qty_remaining * guide_unit_value (if any) or manual value if lot is MANUAL
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
# ---- END PATCH ----
