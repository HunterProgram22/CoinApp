# Home.py
import streamlit as st
import streamlit_authenticator as stauth
from db import init_db
from constants import NAVIGATION_ITEMS, APP_TITLE, APP_SUBTITLE
from auth_config import get_auth_config

st.set_page_config(page_title=APP_TITLE, page_icon="🪙", layout="wide")

# Initialize authentication
auth_config = get_auth_config()
authenticator = stauth.Authenticate(
    auth_config['credentials'],
    auth_config['cookie']['name'],
    auth_config['cookie']['key'],
    auth_config['cookie']['expiry_days']
)

# Login widget
name, authentication_status, username = authenticator.login('Login', 'main')

if authentication_status == False:
    st.error('Username/password is incorrect')
elif authentication_status == None:
    st.warning('Please enter your username and password')
elif authentication_status:
    # User is authenticated - show the app
    authenticator.logout('Logout', 'sidebar')
    st.sidebar.write(f'Welcome *{name}*')

    # Initialize database
    init_db()

    # Your existing app content
    st.title(f"🪙{APP_TITLE}")
    st.caption(APP_SUBTITLE)

    # Render navigation
    for page, label, icon in NAVIGATION_ITEMS:
        st.page_link(page, label=label, icon=icon)
