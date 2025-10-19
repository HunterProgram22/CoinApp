# infrastructure/database/cached_queries.py
"""Cached database queries to improve performance with remote databases like Turso."""
import streamlit as st


# ============================================================================
# TRANSACTION QUERIES
# ============================================================================

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_cached_coin_types(repo_id):
    """Cache coin types to avoid repeated queries."""
    from infrastructure.database.database_executor import DatabaseExecutor
    from infrastructure.database.repositories.transaction_repository import TransactionRepository
    repo = TransactionRepository(DatabaseExecutor())
    return repo.get_all_coin_types()


@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_cached_storage_locations(repo_id):
    """Cache storage locations to avoid repeated queries."""
    from infrastructure.database.database_executor import DatabaseExecutor
    from infrastructure.database.repositories.transaction_repository import TransactionRepository
    repo = TransactionRepository(DatabaseExecutor())
    return repo.get_storage_locations()


@st.cache_data(ttl=60)  # Cache for 1 minute (shorter since this might change frequently)
def get_cached_parties(repo_id):
    """Cache parties list to avoid repeated queries."""
    from infrastructure.database.database_executor import DatabaseExecutor
    from infrastructure.database.repositories.transaction_repository import TransactionRepository
    repo = TransactionRepository(DatabaseExecutor())
    return repo.get_parties()


# ============================================================================
# ADMIN QUERIES
# ============================================================================

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_cached_coin_masters(repo_id):
    """Cache coin masters to avoid repeated queries."""
    from infrastructure.database.database_executor import DatabaseExecutor
    from infrastructure.database.repositories.admin_repository import AdminRepository
    repo = AdminRepository(DatabaseExecutor())
    return repo.get_coin_masters()


@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_cached_admin_coin_types(repo_id):
    """Cache coin types for admin to avoid repeated queries."""
    from infrastructure.database.database_executor import DatabaseExecutor
    from infrastructure.database.repositories.admin_repository import AdminRepository
    repo = AdminRepository(DatabaseExecutor())
    return repo.get_coin_types()


@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_cached_recent_transactions(repo_id, limit=100):
    """Cache recent transactions to avoid repeated queries."""
    from infrastructure.database.database_executor import DatabaseExecutor
    from infrastructure.database.repositories.admin_repository import AdminRepository
    repo = AdminRepository(DatabaseExecutor())
    return repo.get_recent_transactions(limit)


@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_cached_open_lots(repo_id):
    """Cache open lots to avoid repeated queries."""
    from infrastructure.database.database_executor import DatabaseExecutor
    from infrastructure.database.repositories.admin_repository import AdminRepository
    repo = AdminRepository(DatabaseExecutor())
    return repo.get_open_lots()


@st.cache_data(ttl=120)  # Cache for 2 minutes
def get_cached_metal_prices(repo_id):
    """Cache latest metal prices."""
    from infrastructure.database.database_executor import DatabaseExecutor
    from infrastructure.database.repositories.admin_repository import AdminRepository
    repo = AdminRepository(DatabaseExecutor())
    return repo.get_latest_metal_prices()


# ============================================================================
# CATALOG QUERIES
# ============================================================================

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_cached_distinct_values(repo_id, field, table="coin_master", filter_field=None, filter_value=None):
    """Cache distinct values for dropdowns."""
    from infrastructure.database.database_executor import DatabaseExecutor
    from infrastructure.database.repositories.coin_catalog_repository import CoinCatalogRepository
    repo = CoinCatalogRepository(DatabaseExecutor())
    return repo.get_distinct_values(field, table, filter_field, filter_value)


# ============================================================================
# TYPE SETS QUERIES
# ============================================================================

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_cached_all_series(repo_id):
    """Cache all series list to avoid repeated queries."""
    from infrastructure.database.database_executor import DatabaseExecutor
    from infrastructure.database.repositories.type_sets_repository import SQLTypeSetsRepository
    repo = SQLTypeSetsRepository(DatabaseExecutor())
    return repo.get_all_series()


# ============================================================================
# CACHE MANAGEMENT
# ============================================================================

def clear_all_caches():
    """Clear all cached queries - use after data modifications."""
    get_cached_coin_types.clear()
    get_cached_storage_locations.clear()
    get_cached_parties.clear()
    get_cached_coin_masters.clear()
    get_cached_admin_coin_types.clear()
    get_cached_recent_transactions.clear()
    get_cached_open_lots.clear()
    get_cached_metal_prices.clear()
    get_cached_distinct_values.clear()
    get_cached_all_series.clear()
    st.cache_data.clear()


def clear_coin_caches():
    """Clear caches related to coins/types - use after adding/editing masters or types."""
    get_cached_coin_types.clear()
    get_cached_coin_masters.clear()
    get_cached_admin_coin_types.clear()
    get_cached_all_series.clear()  # Series list might change when adding masters


def clear_transaction_caches():
    """Clear caches related to transactions - use after adding transactions."""
    get_cached_parties.clear()
    get_cached_recent_transactions.clear()


def clear_inventory_caches():
    """Clear caches related to inventory - use after inventory changes."""
    get_cached_open_lots.clear()
