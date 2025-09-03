# auth_utils.py
import streamlit as st

def require_auth():
    """Check if user is authenticated, stop page if not"""
    if "authentication_status" not in st.session_state or not st.session_state["authentication_status"]:
        st.error("⚠️ Please login from the Home page")
        st.stop()
