# ========== authentication.py ==========
"""Authentication module - Single Responsibility: Handle authentication logic"""
import streamlit as st
import streamlit_authenticator as stauth
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class AuthConfig(ABC):
    """Abstract base for authentication configuration - Dependency Inversion"""

    @abstractmethod
    def get_credentials(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_cookie_config(self) -> Dict[str, Any]:
        pass


class StreamlitSecretsAuthConfig(AuthConfig):
    """Concrete implementation using Streamlit secrets"""

    def get_credentials(self) -> Dict[str, Any]:
        return {
            'usernames': {
                st.secrets.auth.username: {
                    'email': st.secrets.auth.email,
                    'failed_login_attempts': 0,
                    'logged_in': False,
                    'name': st.secrets.auth.name,
                    'password': st.secrets.auth.password
                }
            }
        }

    def get_cookie_config(self) -> Dict[str, Any]:
        return {
            'expiry_days': st.secrets.cookie.expiry_days,
            'key': st.secrets.cookie.key,
            'name': st.secrets.cookie.name
        }


class AuthenticationService:
    """Service to handle authentication - Single Responsibility"""

    def __init__(self, config: AuthConfig):
        self.config = config
        self._authenticator = None

    def get_authenticator(self) -> stauth.Authenticate:
        """Lazy initialization of authenticator"""
        if self._authenticator is None:
            credentials = self.config.get_credentials()
            cookie_config = self.config.get_cookie_config()

            self._authenticator = stauth.Authenticate(
                credentials,
                cookie_config['name'],
                cookie_config['key'],
                cookie_config['expiry_days']
            )
        return self._authenticator

    def login(self) -> Optional[bool]:
        """Handle login and return authentication status"""
        authenticator = self.get_authenticator()
        authenticator.login()
        return st.session_state.get("authentication_status")

    def logout(self, location: str = 'sidebar'):
        """Handle logout"""
        authenticator = self.get_authenticator()
        authenticator.logout(location=location)
