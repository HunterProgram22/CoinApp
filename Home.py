
# Home.py
import streamlit as st
from db import init_db

st.set_page_config(page_title="Coin Tracker", layout="wide")
init_db()

st.title("🪙 Coin Tracker")
st.caption("Inventory • Transactions • Storage • Analytics")

# Sidebar navigation (custom order)
st.page_link("Home.py", label="Home", icon="🏠")
st.page_link("pages/1_Dashboard.py", label="Dashboard", icon="📊")
st.page_link("pages/2_Inventory.py", label="Inventory", icon="📦")
st.page_link("pages/3_Type_Sets.py", label="Type Sets", icon="📚")
st.page_link("pages/4_Specimens.py", label="Specimens", icon="🏷️")
st.page_link("pages/5_Add_Transaction.py", label="Add Transaction", icon="➕")
st.page_link("pages/6_Settings.py", label="Settings", icon="⚙️")
st.page_link("pages/7_Coin_Type_Editor.py", label="Coin Type Editor", icon="🧩")
st.page_link("pages/8_Admin.py", label="Admin", icon="🛠️")
st.page_link("pages/9_Data_Import.py", label="Data Import", icon="📥")

