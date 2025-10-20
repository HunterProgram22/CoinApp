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
# DASHBOARD QUERIES - Cache aggressively (these are expensive!)
# ============================================================================

@st.cache_data(ttl=600)  # Cache for 10 minutes - dashboard doesn't change often
def get_cached_portfolio_summary(repo_id):
    """Cache portfolio summary - expensive query."""
    from infrastructure.database.database_executor import DatabaseExecutor
    from infrastructure.database.repositories.dashboard_repository import SQLDashboardRepository
    repo = SQLDashboardRepository(DatabaseExecutor())
    return repo.get_portfolio_summary()


@st.cache_data(ttl=600)  # Cache for 10 minutes
def get_cached_series_rollup(repo_id):
    """Cache series rollup - very expensive query."""
    from infrastructure.database.database_executor import DatabaseExecutor
    from infrastructure.database.repositories.dashboard_repository import SQLDashboardRepository
    repo = SQLDashboardRepository(DatabaseExecutor())
    return repo.get_series_rollup()


@st.cache_data(ttl=600)  # Cache for 10 minutes
def get_cached_portfolio_composition(repo_id):
    """Cache portfolio composition - expensive query."""
    from infrastructure.database.database_executor import DatabaseExecutor
    from infrastructure.database.repositories.dashboard_repository import SQLDashboardRepository
    repo = SQLDashboardRepository(DatabaseExecutor())
    return repo.get_portfolio_composition()


@st.cache_data(ttl=600)  # Cache for 10 minutes
def get_cached_top_series_by_value(repo_id, limit=10):
    """Cache top series - expensive query."""
    from infrastructure.database.database_executor import DatabaseExecutor
    from infrastructure.database.repositories.dashboard_repository import SQLDashboardRepository
    repo = SQLDashboardRepository(DatabaseExecutor())
    return repo.get_top_series_by_value(limit)


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


@st.cache_data(ttl=600)  # Cache for 10 minutes - CRITICAL FOR PERFORMANCE
def get_cached_type_set_value_data(repo_id, set_id):
    """Cache type set value data - VERY expensive query that joins v_lot_value_details."""
    from infrastructure.database.database_executor import DatabaseExecutor
    from infrastructure.database.repositories.type_sets_repository import SQLTypeSetsRepository
    repo = SQLTypeSetsRepository(DatabaseExecutor())
    return repo.get_type_set_value_data(set_id)


@st.cache_data(ttl=600)  # Cache for 10 minutes
def get_cached_type_set_summary(repo_id, set_id):
    """Cache type set summary data."""
    from infrastructure.database.database_executor import DatabaseExecutor
    from infrastructure.database.repositories.type_sets_repository import SQLTypeSetsRepository
    repo = SQLTypeSetsRepository(DatabaseExecutor())
    return repo.get_type_set_summary(set_id)


@st.cache_data(ttl=600)  # Cache for 10 minutes
def get_cached_type_set_progress(repo_id, set_id):
    """Cache type set progress data."""
    from infrastructure.database.database_executor import DatabaseExecutor
    from infrastructure.database.repositories.type_sets_repository import SQLTypeSetsRepository
    repo = SQLTypeSetsRepository(DatabaseExecutor())
    return repo.get_type_set_progress(set_id)


# ============================================================================
# CACHE MANAGEMENT
# ============================================================================

def clear_all_caches():
    """Clear all cached queries - use after data modifications."""
    # Transaction caches
    get_cached_coin_types.clear()
    get_cached_storage_locations.clear()
    get_cached_parties.clear()
    # Admin caches
    get_cached_coin_masters.clear()
    get_cached_admin_coin_types.clear()
    get_cached_recent_transactions.clear()
    get_cached_open_lots.clear()
    get_cached_metal_prices.clear()
    # Catalog caches
    get_cached_distinct_values.clear()
    get_cached_all_series.clear()
    # Dashboard caches
    get_cached_portfolio_summary.clear()
    get_cached_series_rollup.clear()
    get_cached_portfolio_composition.clear()
    get_cached_top_series_by_value.clear()
    # Type Sets caches
    get_cached_type_set_value_data.clear()
    get_cached_type_set_summary.clear()
    get_cached_type_set_progress.clear()
    # Clear all
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
    # Also clear dashboard and type sets since portfolio changed
    clear_dashboard_caches()
    clear_type_sets_caches()


def clear_inventory_caches():
    """Clear caches related to inventory - use after inventory changes."""
    get_cached_open_lots.clear()
    # Also clear dashboard and type sets since portfolio changed
    clear_dashboard_caches()
    clear_type_sets_caches()


def clear_dashboard_caches():
    """Clear dashboard caches - call after any transaction/inventory change."""
    get_cached_portfolio_summary.clear()
    get_cached_series_rollup.clear()
    get_cached_portfolio_composition.clear()
    get_cached_top_series_by_value.clear()


def clear_type_sets_caches():
    """Clear type sets caches - call after any transaction/inventory change."""
    get_cached_type_set_value_data.clear()
    get_cached_type_set_summary.clear()
    get_cached_type_set_progress.clear()
