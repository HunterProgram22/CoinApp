# Home.py
import streamlit as st
from db import init_db
from constants import NAVIGATION_ITEMS, APP_TITLE, APP_SUBTITLE


st.set_page_config(page_title=APP_TITLE,  page_icon="🪙",  layout="wide")
init_db()

st.title(f"🪙{APP_TITLE}")
st.caption(APP_SUBTITLE)

# Render navigation
for page, label, icon in NAVIGATION_ITEMS:
    st.page_link(page, label=label, icon=icon)
