# Home.py
import streamlit as st
import streamlit_authenticator as stauth
from db import init_db
from constants import NAVIGATION_ITEMS, APP_TITLE, APP_SUBTITLE

st.set_page_config(page_title=APP_TITLE, page_icon="🪙", layout="wide")


# Create authentication config from secrets
def get_authenticator():
    """Create authenticator from secrets"""
    config = {
        'credentials': {
            'usernames': {
                st.secrets.auth.username: {
                    'email': st.secrets.auth.email,
                    'failed_login_attempts': 0,
                    'logged_in': False,
                    'name': st.secrets.auth.name,
                    'password': st.secrets.auth.password  # hashed password
                }
            }
        },
        'cookie': {
            'expiry_days': st.secrets.cookie.expiry_days,
            'key': st.secrets.cookie.key,
            'name': st.secrets.cookie.name
        }
    }

    # Note: pre-authorized parameter removed in v0.4.2
    authenticator = stauth.Authenticate(
        config['credentials'],
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days']
    )

    return authenticator


# Initialize authenticator
authenticator = get_authenticator()

# Create login widget
authenticator.login()

if st.session_state["authentication_status"] is False:
    st.error('Username/password is incorrect')
elif st.session_state["authentication_status"] is None:
    st.warning('Please enter your username and password')
elif st.session_state["authentication_status"]:
    # User is authenticated
    authenticator.logout(location='sidebar')
    st.sidebar.write(f'Welcome *{st.session_state["name"]}*')

    # Initialize database
    init_db()

    # Your existing app content
    st.title(f"🪙{APP_TITLE}")
    st.caption(APP_SUBTITLE)

    # Render navigation
    for page, label, icon in NAVIGATION_ITEMS:
        st.page_link(page, label=label, icon=icon)
