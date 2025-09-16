# infrastructure/database/repositories/coin_catalog_repository.py
"""Coin catalog data repository - Single Responsibility: Data access for coin catalog"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from infrastructure.database.db_operations import execute_query_all


class CoinCatalogDataRepository(ABC):
    """Abstract repository for coin catalog data - Dependency Inversion"""

    @abstractmethod
    def get_distinct_values(
            self,
            column: str,
            table: str = "coin_master",
            filter_column: Optional[str] = None,
            filter_value: Optional[str] = None
    ) -> List[str]:
        pass

    @abstractmethod
    def get_countries_for_coin_types(self) -> List[str]:
        pass

    @abstractmethod
    def get_series_for_country(self, country: str) -> List[str]:
        pass

    @abstractmethod
    def search_coin_masters(
            self,
            country: Optional[str] = None,
            denomination: Optional[str] = None,
            series_search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def search_coin_types(
            self,
            country: Optional[str] = None,
            series: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        pass


class CoinCatalogRepository(CoinCatalogDataRepository):
    """SQLite implementation of coin catalog repository"""

    def __init__(self, db_executor):
        self.db = db_executor

    def get_distinct_values(
            self,
            column: str,
            table: str = "coin_master",
            filter_column: Optional[str] = None,
            filter_value: Optional[str] = None
    ) -> List[str]:
        """Get distinct values from specified table."""
        conditions = []
        params = []

        if filter_column and filter_value:
            conditions.append(f"{filter_column} = ?")
            params.append(filter_value)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
            SELECT DISTINCT {column} AS value
            FROM {table}
            {where_clause}
            ORDER BY value
        """

        results = execute_query_all(query, tuple(params))
        return [r['value'] for r in results if r['value']]  # Filter out None/NULL values

    def get_countries_for_coin_types(self) -> List[str]:
        """Get distinct countries that have coin types."""
        query = """
            SELECT DISTINCT cm.country
            FROM coin_type ct
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE cm.country IS NOT NULL
            ORDER BY cm.country
        """
        results = execute_query_all(query)
        return [r['country'] for r in results]

    def get_series_for_country(self, country: str) -> List[str]:
        """Get distinct series for a specific country."""
        query = """
            SELECT DISTINCT cm.series
            FROM coin_type ct
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE cm.country = ?
            ORDER BY cm.series
        """
        results = execute_query_all(query, (country,))
        return [r['series'] for r in results]

    def search_coin_masters(
            self,
            country: Optional[str] = None,
            denomination: Optional[str] = None,
            series_search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search coin masters with filters."""
        conditions = []
        params = []

        # Require country to be selected
        if country:
            conditions.append("country = ?")
            params.append(country)
        else:
            # Return empty list if no country selected
            return []

        if denomination and denomination != "All":
            conditions.append("denomination = ?")
            params.append(denomination)

        if series_search and series_search.strip():
            conditions.append("LOWER(series) LIKE ?")
            params.append(f"%{series_search.strip().lower()}%")

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
            SELECT 
                id,
                country,
                denomination,
                series,
                years_start,
                years_end,
                metal,
                fineness,
                weight_grams,
                asset_category,
                COALESCE(numista_url, '') AS numista_url,
                COALESCE(ngc_url, '') AS ngc_url,
                COALESCE(pcgs_url, '') AS pcgs_url
            FROM coin_master
            {where_clause}
            ORDER BY country, denomination, series
        """

        return execute_query_all(query, tuple(params))

    def search_coin_types(
            self,
            country: Optional[str] = None,
            series: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search coin types with filters."""
        conditions = []
        params = []

        # Both country and series are required
        if country:
            conditions.append("cm.country = ?")
            params.append(country)

        if series:
            conditions.append("cm.series = ?")
            params.append(series)

        # Return empty if either is missing
        if not country or not series:
            return []

        where_clause = f"WHERE {' AND '.join(conditions)}"

        query = f"""
            SELECT 
                ct.id,
                cm.denomination,
                cm.series,
                ct.year,
                COALESCE(ct.mint_mark, '') AS mint_mark,
                COALESCE(ct.variety, '') AS variety,
                COALESCE(ct.mintage, 0) AS mintage,
                ct.is_proof
            FROM coin_type ct
            JOIN coin_master cm ON cm.id = ct.master_id
            {where_clause}
            ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety
        """

        return execute_query_all(query, tuple(params))
