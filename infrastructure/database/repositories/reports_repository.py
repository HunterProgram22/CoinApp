# infrastructure/database/repositories/reports_repository.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import pandas as pd
from datetime import date
from infrastructure.database.db_operations import execute_query_all, execute_query_single


@dataclass
class CollectionValueSummary:
    total_coins: int
    total_cost: float
    total_estimated_value: float
    unrealized_gain_loss: float
    gain_loss_percent: float


@dataclass
class CategoryValue:
    asset_category: str
    count: int
    cost: float
    melt_value: float
    estimated_value: float
    unrealized_gl: float


@dataclass
class MetalValue:
    metal: str
    count: int
    troy_oz_fine: float
    cost: float
    melt_value: float
    estimated_value: float
    unrealized_gl: float


@dataclass
class TopValuedCoin:
    series: str
    year: int
    mint_mark: Optional[str]
    variety: Optional[str]
    qty_remaining: int
    grade: str
    unit_cost: float
    unit_value: float
    total_value: float
    unrealized_gl: float


@dataclass
class Seller:
    id: int
    name: str
    logical_transaction_count: int
    db_transaction_count: int
    total_coins: int


@dataclass
class SellerSummary:
    unique_transactions: int
    total_coins_purchased: int
    coins_still_held: int
    total_cost_usd: float
    unique_coin_types: int
    total_current_value_usd: float
    unrealized_gain_loss: float
    gain_loss_percent: float
    coins_sold: int


@dataclass
class SellerCoinDetail:
    coin: str
    metal: str
    asset_category: str
    total_purchased: int
    qty_remaining: int
    avg_purchase_price: float
    total_spent: float
    cost_of_remaining: float
    current_value: float
    unrealized_gl: float
    gl_percent: float
    best_grade: str
    first_purchase: str
    last_purchase: str


@dataclass
class SellerTransaction:
    tx_ids: str
    tx_date: str
    line_items: str
    total_quantity: int
    subtotal: float
    shipping: float
    tax: float
    fees: float
    total: float
    notes: str
    db_transaction_count: Optional[int] = None


@dataclass
class SpendingSummary:
    date: date
    party: str
    total_spent_usd: float
    items: str
    lines: int


class ReportsDataRepository(ABC):
    """Abstract repository interface for Reports data access"""

    @abstractmethod
    def get_collection_value_summary(self) -> Optional[CollectionValueSummary]:
        """Get collection value summary"""
        pass

    @abstractmethod
    def get_value_by_category(self) -> List[CategoryValue]:
        """Get value breakdown by asset category"""
        pass

    @abstractmethod
    def get_value_by_metal(self) -> List[MetalValue]:
        """Get value breakdown by metal type"""
        pass

    @abstractmethod
    def get_top_valued_coins(self, limit: int = 20) -> List[TopValuedCoin]:
        """Get top valued coins"""
        pass

    @abstractmethod
    def get_sellers_with_transactions(self) -> List[Seller]:
        """Get sellers with transaction counts"""
        pass

    @abstractmethod
    def get_seller_summary(self, party_id: int, group_by_date: bool = True) -> Optional[
        SellerSummary]:
        """Get seller summary statistics"""
        pass

    @abstractmethod
    def get_seller_detail_by_coin_type(self, party_id: int) -> List[SellerCoinDetail]:
        """Get seller detail by coin type"""
        pass

    @abstractmethod
    def get_seller_transactions(self, party_id: int, group_by_date: bool = True) -> List[
        SellerTransaction]:
        """Get seller transaction history"""
        pass

    @abstractmethod
    def get_spending_summary(self, date_from: Optional[date] = None,
                             date_to: Optional[date] = None) -> pd.DataFrame:
        """Get spending summary (moved from Transactions)"""
        pass

    @abstractmethod
    def get_spending_total(self, date_from: Optional[date] = None,
                           date_to: Optional[date] = None) -> float:
        """Get total spending for date range (moved from Transactions)"""
        pass


class ReportsRepository(ReportsDataRepository):
    """Concrete implementation of Reports data repository"""

    def __init__(self, db_executor):
        self.db = db_executor

    def get_collection_value_summary(self) -> Optional[CollectionValueSummary]:
        """Get collection value summary"""
        import services.report_logic as rl
        summary = rl.get_collection_value_summary()

        if summary and summary.get('total_coins', 0) > 0:
            return CollectionValueSummary(
                total_coins=int(summary.get('total_coins', 0)),
                total_cost=float(summary.get('total_cost', 0)),
                total_estimated_value=float(summary.get('total_estimated_value', 0)),
                unrealized_gain_loss=float(summary.get('unrealized_gain_loss', 0)),
                gain_loss_percent=float(summary.get('gain_loss_percent', 0))
            )
        return None

    def get_value_by_category(self) -> List[CategoryValue]:
        """Get value breakdown by asset category"""
        import services.report_logic as rl
        data = rl.get_value_by_category()

        if data:
            result = []
            for item in data:
                try:
                    # Handle potential key variations
                    # Check for 'asset_category' or 'category' or 'Asset_Category'
                    category_key = None
                    for key in ['asset_category', 'category', 'Asset_Category', 'AssetCategory']:
                        if key in item:
                            category_key = key
                            break

                    if not category_key:
                        # If no category key found, try to use first string key as category
                        # or skip this item
                        print(f"Warning: No asset_category field found in item: {item.keys()}")
                        continue

                    result.append(CategoryValue(
                        asset_category=str(item[category_key]),
                        count=int(item.get('count', 0)),
                        cost=float(item.get('cost', 0)),
                        melt_value=float(item.get('melt_value', 0)),
                        estimated_value=float(item.get('estimated_value', 0)),
                        unrealized_gl=float(item.get('unrealized_gl', 0))
                    ))
                except (KeyError, TypeError, ValueError) as e:
                    print(f"Error processing category value item: {e}")
                    print(f"Item data: {item}")
                    continue

            return result
        return []

    def get_value_by_metal(self) -> List[MetalValue]:
        """Get value breakdown by metal type"""
        import services.report_logic as rl
        data = rl.get_value_by_metal()

        if data:
            result = []
            for item in data:
                try:
                    # Handle potential key variations
                    metal_key = None
                    for key in ['metal', 'Metal', 'metal_type']:
                        if key in item:
                            metal_key = key
                            break

                    if not metal_key:
                        print(f"Warning: No metal field found in item: {item.keys()}")
                        continue

                    # Handle 'coins' vs 'count' field
                    count_value = item.get('count', item.get('coins', 0))

                    result.append(MetalValue(
                        metal=str(item[metal_key]),
                        count=int(count_value),
                        troy_oz_fine=float(item.get('troy_oz_fine', 0) if item.get(
                            'troy_oz_fine') is not None else 0),
                        cost=float(item.get('cost', 0) if item.get('cost') is not None else 0),
                        melt_value=float(
                            item.get('melt_value', 0) if item.get('melt_value') is not None else 0),
                        estimated_value=float(item.get('estimated_value', 0) if item.get(
                            'estimated_value') is not None else 0),
                        unrealized_gl=float(item.get('unrealized_gl', 0) if item.get(
                            'unrealized_gl') is not None else 0)
                    ))
                except (KeyError, TypeError, ValueError) as e:
                    print(f"Error processing metal value item: {e}")
                    print(f"Item data: {item}")
                    continue

            return result
        return []
    def get_top_valued_coins(self, limit: int = 20) -> List[TopValuedCoin]:
        """Get top valued coins"""
        import services.report_logic as rl
        data = rl.get_top_valued_coins(limit)

        if data:
            result = []
            for item in data:
                try:
                    result.append(TopValuedCoin(
                        series=str(item.get('series', '')),
                        year=int(item.get('year', 0)),
                        mint_mark=item.get('mint_mark'),
                        variety=item.get('variety'),
                        qty_remaining=int(item.get('qty_remaining', 0)),
                        grade=str(item.get('grade', '')),
                        unit_cost=float(item.get('unit_cost', 0)),
                        unit_value=float(item.get('unit_value', 0)),
                        total_value=float(item.get('total_value', 0)),
                        unrealized_gl=float(item.get('unrealized_gl', 0))
                    ))
                except (KeyError, TypeError, ValueError) as e:
                    print(f"Error processing top valued coin item: {e}")
                    print(f"Item data: {item}")
                    continue

            return result
        return []

    def get_sellers_with_transactions(self) -> List[Seller]:
        """Get sellers with transaction counts"""
        import services.report_logic as rl
        data = rl.get_sellers_with_transactions()

        if data:
            result = []
            for item in data:
                try:
                    result.append(Seller(
                        id=int(item.get('id', 0)),
                        name=str(item.get('name', '')),
                        logical_transaction_count=int(item.get('logical_transaction_count', 0)),
                        db_transaction_count=int(item.get('db_transaction_count', 0)),
                        total_coins=int(item.get('total_coins', 0))
                    ))
                except (KeyError, TypeError, ValueError) as e:
                    print(f"Error processing seller item: {e}")
                    print(f"Item data: {item}")
                    continue

            return result
        return []

    def get_seller_summary(self, party_id: int, group_by_date: bool = True) -> Optional[
        SellerSummary]:
        """Get seller summary statistics"""
        import services.report_logic as rl
        summary = rl.get_seller_summary(party_id, group_by_date)

        if summary:
            try:
                return SellerSummary(
                    unique_transactions=int(summary.get('unique_transactions', 0)),
                    total_coins_purchased=int(summary.get('total_coins_purchased', 0)),
                    coins_still_held=int(summary.get('coins_still_held', 0)),
                    total_cost_usd=float(summary.get('total_cost_usd', 0)),
                    unique_coin_types=int(summary.get('unique_coin_types', 0)),
                    total_current_value_usd=float(summary.get('total_current_value_usd', 0)),
                    unrealized_gain_loss=float(summary.get('unrealized_gain_loss', 0)),
                    gain_loss_percent=float(summary.get('gain_loss_percent', 0)),
                    coins_sold=int(summary.get('coins_sold', 0))
                )
            except (KeyError, TypeError, ValueError) as e:
                print(f"Error processing seller summary: {e}")
                print(f"Summary data: {summary}")
                return None
        return None

    def get_seller_detail_by_coin_type(self, party_id: int) -> List[SellerCoinDetail]:
        """Get seller detail by coin type"""
        import services.report_logic as rl
        data = rl.get_seller_detail_by_coin_type(party_id)

        if data:
            result = []
            for item in data:
                try:
                    coin_display = f"{item.get('series', '')} {item.get('year', '')}"
                    if item.get('mint_mark'):
                        coin_display += f" {item['mint_mark']}"
                    if item.get('variety'):
                        coin_display += f" • {item['variety']}"

                    cost_remaining = float(item.get('cost_of_remaining', 0))
                    unrealized_gl = float(item.get('unrealized_gl', 0))

                    result.append(SellerCoinDetail(
                        coin=coin_display,
                        metal=str(item.get('metal', '')),
                        asset_category=str(item.get('asset_category', '')),
                        total_purchased=int(item.get('total_purchased', 0)),
                        qty_remaining=int(item.get('qty_remaining', 0)),
                        avg_purchase_price=float(item.get('avg_purchase_price', 0)),
                        total_spent=float(item.get('total_spent', 0)),
                        cost_of_remaining=cost_remaining,
                        current_value=float(item.get('current_value', 0)),
                        unrealized_gl=unrealized_gl,
                        gl_percent=float((unrealized_gl / cost_remaining * 100)
                                         if cost_remaining and cost_remaining > 0 else 0),
                        best_grade=str(item.get('best_grade', '')),
                        first_purchase=str(item.get('first_purchase', '')),
                        last_purchase=str(item.get('last_purchase', ''))
                    ))
                except (KeyError, TypeError, ValueError) as e:
                    print(f"Error processing seller detail item: {e}")
                    print(f"Item data: {item}")
                    continue

            return result
        return []

    def get_seller_transactions(self, party_id: int, group_by_date: bool = True) -> List[
        SellerTransaction]:
        """Get seller transaction history"""
        import services.report_logic as rl
        data = rl.get_seller_transactions(party_id, group_by_date)

        if data:
            result = []
            for item in data:
                try:
                    result.append(SellerTransaction(
                        tx_ids=str(item.get('tx_ids', '')),
                        tx_date=str(item.get('tx_date', '')),
                        line_items=str(item.get('line_items', '')),
                        total_quantity=int(item.get('total_quantity', 0)),
                        subtotal=float(item.get('subtotal', 0)),
                        shipping=float(item.get('shipping', 0)),
                        tax=float(item.get('tax', 0)),
                        fees=float(item.get('fees', 0)),
                        total=float(item.get('total', 0)),
                        notes=str(item.get('notes', '') or ''),
                        db_transaction_count=int(
                            item.get('db_transaction_count', 1)) if group_by_date else None
                    ))
                except (KeyError, TypeError, ValueError) as e:
                    print(f"Error processing seller transaction item: {e}")
                    print(f"Item data: {item}")
                    continue

            return result
        return []

    def get_spending_summary(self, date_from: Optional[date] = None,
                             date_to: Optional[date] = None) -> pd.DataFrame:
        """Get spending summary (moved from Transactions)"""
        # Build query conditions
        conditions = ["t.tx_type = 'BUY'"]
        params = []

        if date_from and date_to:
            conditions.append("DATE(t.tx_date) BETWEEN DATE(?) AND DATE(?)")
            params.extend([date_from.isoformat(), date_to.isoformat()])

        where_clause = f"WHERE {' AND '.join(conditions)}"

        # Query to get all BUY transactions with their line items
        # Join through coin_type and coin_master to get series
        query = f"""
            SELECT 
                t.id as tx_id,
                t.tx_date,
                p.name as party,
                t.shipping,
                t.tax,
                t.fees,
                cm.series,
                tl.quantity,
                tl.unit_price
            FROM tx t
            LEFT JOIN party p ON t.party_id = p.id
            JOIN tx_line tl ON tl.tx_id = t.id
            JOIN coin_type ct ON ct.id = tl.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            {where_clause}
            ORDER BY t.tx_date DESC, t.id
        """

        result = execute_query_all(query, tuple(params))

        if not result:
            return pd.DataFrame()

        # Convert to DataFrame
        df = pd.DataFrame(result)

        if df.empty:
            return pd.DataFrame()

        # Calculate line totals (without fees)
        df["line_total"] = (
                pd.to_numeric(df["unit_price"], errors="coerce").fillna(0.0) *
                pd.to_numeric(df["quantity"], errors="coerce").fillna(0.0)
        )

        # Group by transaction first to handle fees properly
        df["Date"] = pd.to_datetime(df["tx_date"]).dt.date
        df["Series"] = df["series"].fillna("")

        # First, calculate totals per transaction
        tx_totals = df.groupby(["tx_id", "Date", "party"], dropna=False).agg(
            line_subtotal=("line_total", "sum"),
            shipping=("shipping", "first"),  # Get once per transaction
            tax=("tax", "first"),  # Get once per transaction
            fees=("fees", "first"),  # Get once per transaction
            items_list=(
                "Series", lambda s: ", ".join(f"{n}×{k}" for k, n in s.value_counts().items())),
            line_count=("series", "count")
        ).reset_index()

        # Calculate true total with fees added once per transaction
        tx_totals["Total_Spent_USD"] = (
                tx_totals["line_subtotal"] +
                pd.to_numeric(tx_totals["shipping"], errors="coerce").fillna(0.0) +
                pd.to_numeric(tx_totals["tax"], errors="coerce").fillna(0.0) +
                pd.to_numeric(tx_totals["fees"], errors="coerce").fillna(0.0)
        )

        # Now aggregate by Date and Party for final summary
        agg = tx_totals.groupby(["Date", "party"], dropna=False).agg(
            Total_Spent_USD=("Total_Spent_USD", "sum"),
            Items=("items_list", lambda x: ", ".join(x)),
            Lines=("line_count", "sum")
        ).reset_index().rename(columns={"party": "Party"})

        return agg.sort_values(["Date", "Party"], ascending=[False, True])

    def get_spending_total(self, date_from: Optional[date] = None,
                           date_to: Optional[date] = None) -> float:
        """Get total spending for date range (moved from Transactions)"""
        conditions = ["t.tx_type = 'BUY'"]
        params = []

        if date_from and date_to:
            conditions.append("DATE(t.tx_date) BETWEEN DATE(?) AND DATE(?)")
            params.extend([date_from.isoformat(), date_to.isoformat()])

        where_clause = f"WHERE {' AND '.join(conditions)}"

        # Fixed query: Calculate fees per transaction, not per line
        query = f"""
            WITH tx_totals AS (
                SELECT 
                    t.id,
                    SUM(ABS(tl.quantity) * COALESCE(tl.unit_price, 0)) as line_total,
                    MAX(COALESCE(t.shipping, 0)) as shipping,
                    MAX(COALESCE(t.tax, 0)) as tax,
                    MAX(COALESCE(t.fees, 0)) as fees
                FROM tx t
                JOIN tx_line tl ON tl.tx_id = t.id
                {where_clause}
                GROUP BY t.id
            )
            SELECT 
                COALESCE(SUM(line_total + shipping + tax + fees), 0) as total
            FROM tx_totals
        """

        result = execute_query_single(query, tuple(params))
        return float(result['total']) if result and result['total'] else 0.0
