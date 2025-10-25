# ========== app_coordinator.py ==========
"""Application Coordinator - Orchestrates the application flow"""
import streamlit as st


class AppCoordinator:
    """Coordinates application components - Single Responsibility"""

    def __init__(self,
                 auth_service: 'AuthenticationService',
                 auth_ui: 'AuthenticationUI',
                 nav_ui: 'NavigationUI'):
        self.auth_service = auth_service
        self.auth_ui = auth_ui
        self.nav_ui = nav_ui

    def run(self):
        """Main application flow"""
        auth_status = self.auth_service.login()

        if auth_status is False:
            self.auth_ui.show_login_error()
        elif auth_status is None:
            self.auth_ui.show_login_prompt()
        elif auth_status:
            self._handle_authenticated_user()

    def _handle_authenticated_user(self):
        """Handle authenticated user flow"""
        from infrastructure.database.db import init_db, get_conn
        from infrastructure.database.cache_manager import LotValueCacheManager
        from infrastructure.database.database_executor import DatabaseExecutor
        from core.constants import NAVIGATION_ITEMS, APP_TITLE, APP_SUBTITLE

        # Logout button and welcome message
        self.auth_service.logout(location='sidebar')
        self.auth_ui.show_welcome(st.session_state["name"])

        # Initialize database
        init_db()

        # Initialize cache
        @st.cache_resource
        def init_cache():
            """Initialize lot value cache on app startup"""
            try:
                with get_conn() as conn:
                    executor = DatabaseExecutor()
                    cache_mgr = LotValueCacheManager(executor)

                    if cache_mgr.needs_refresh(max_age_minutes=60):
                        cache_mgr.refresh_cache()
                return True
            except Exception as e:
                st.error(f"Cache initialization failed: {e}")
                return False

        init_cache()

        # Render main content
        self.nav_ui.render_title(APP_TITLE, APP_SUBTITLE)
        self.nav_ui.render_navigation(NAVIGATION_ITEMS)