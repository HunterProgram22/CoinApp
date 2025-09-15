# ========== Home.py (Refactored) ==========
"""Main entry point - Minimal responsibility: Wire up dependencies"""
import streamlit as st
from infrastructure.auth.authentication import StreamlitSecretsAuthConfig, AuthenticationService
from presentation.ui_components import AuthenticationUI, NavigationUI
from presentation.app_coordinator import AppCoordinator
from core.constants import APP_TITLE

# Page configuration
st.set_page_config(page_title=APP_TITLE, page_icon="🪙", layout="wide")

# Dependency injection - components are loosely coupled
auth_config = StreamlitSecretsAuthConfig()
auth_service = AuthenticationService(auth_config)
auth_ui = AuthenticationUI()
nav_ui = NavigationUI()

# Create and run the application coordinator
app = AppCoordinator(auth_service, auth_ui, nav_ui)
app.run()
