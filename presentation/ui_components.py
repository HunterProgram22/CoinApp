# ========== ui_components.py ==========
"""UI Components module - Single Responsibility: Handle UI rendering"""
import streamlit as st
from typing import List, Tuple


class AuthenticationUI:
    """Handles authentication-related UI - Single Responsibility"""

    @staticmethod
    def show_login_error():
        st.error('Username/password is incorrect')

    @staticmethod
    def show_login_prompt():
        st.warning('Please enter your username and password')

    @staticmethod
    def show_welcome(name: str):
        st.sidebar.write(f'Welcome *{name}*')


class NavigationUI:
    """Handles navigation rendering - Single Responsibility"""

    @staticmethod
    def render_navigation(items: List[Tuple[str, str, str]]):
        for page, label, icon in items:
            st.page_link(page, label=label, icon=icon)

    @staticmethod
    def render_title(title: str, subtitle: str):
        st.title(f"🪙{title}")
        st.caption(subtitle)
