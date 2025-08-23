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
st.page_link("pages/5_Transactions.py", label="Transactions", icon="➕")
st.page_link("pages/6_World_Coins.py", label="World Coins", icon="🌍️")
st.page_link("pages/7_Coin_Type_Editor.py", label="Coin Type Editor", icon="🧩")
st.page_link("pages/8_Admin.py", label="Admin", icon="🛠️")
st.page_link("pages/9_Data_Import.py", label="Data Import", icon="📥")
st.page_link("pages/10_Bullion.py", label="Bullion", icon="💰")
st.page_link("pages/11_Coin_Catalog.py", label="Coin Catalog", icon="📚")
st.page_link("pages/12_DB_Patches.py", label="DB Patches", icon="🧩")
st.page_link("pages/13_Diagnostics.py", label="Diagnostics Catalog", icon="🧪")
