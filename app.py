# app.py
import streamlit as st
from db import init_db

st.set_page_config(page_title="Coin Tracker", layout="wide")
init_db()

st.title("🪙 Coin Tracker")
st.caption("Inventory • Transactions • Storage • Analytics")

st.page_link("pages/1_Dashboard.py", label="Dashboard", icon="🏠")
st.page_link("pages/2_Add_Transaction.py", label="Add Transaction", icon="➕")
st.page_link("pages/3_Inventory.py", label="Inventory", icon="📦")
st.page_link("pages/4_Import.py", label="Import from Excel/CSV", icon="📥")
st.page_link("pages/5_Quick_Import_Templates.py", label="Quick Import (Templates)", icon="⚡")
st.page_link("pages/6_Settings.py", label="Settings", icon="⚙️")
st.page_link("pages/7_Specimens.py", label="Speciments (Flip IDs)", icon="🏷️")
st.page_link("pages/8_Admin.py", label="Admin", icon="🛠️")
st.page_link("pages/9_Coin_Type_Editor.py", label="Coin Type & Guide Prices", icon="🧩")
