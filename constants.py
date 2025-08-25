# constants.py
"""
Shared constants for the Coin Tracker application.
Centralizes all enum-like values to avoid duplication across modules.
"""

# Navigation configuration
NAVIGATION_ITEMS = [
    ("Home.py", "Home", "🏠"),
    ("pages/1_Dashboard.py", "Dashboard", "📊"),
    ("pages/2_Inventory.py", "Inventory", "📦"),
    ("pages/3_Type_Sets.py", "Type Sets", "📚"),
    ("pages/4_Specimens.py", "Specimens", "🏷️"),
    ("pages/5_Transactions.py", "Transactions", "➕"),
    ("pages/6_World_Coins.py", "World Coins", "🌍️"),
    ("pages/7_Coin_Type_Editor.py", "Coin Type Editor", "🧩"),
    ("pages/8_Admin.py", "Admin", "🛠️"),
    ("pages/9_Data_Import.py", "Data Import", "📥"),
    ("pages/10_Bullion.py", "Bullion", "💰"),
    ("pages/11_Coin_Catalog.py", "Coin Catalog", "📚"),
    ("pages/12_DB_Patches.py", "DB Patches", "🧩"),
    ("pages/13_Diagnostics.py", "Diagnostics", "🧪")
]

# App configuration
APP_TITLE = "Coin Tracker"
APP_SUBTITLE = "Inventory • Transactions • Storage • Analytics"


# Asset Categories
ASSET_CATEGORIES = ["COIN", "ROUND", "BAR", "BULLION COIN"]

# Transaction Types
TRANSACTION_TYPES = ["BUY", "SELL", "FEE", "ADJUST", "GIFT_IN", "GIFT_OUT", "TRANSFER"]

# Metals
METALS = ["Ag", "Au", "Pt", "Pd", "Cu", "Ni", "Zn"]

# Currencies
CURRENCIES = ["USD", "CAD", "EUR", "GBP"]

# Lot Status Options
LOT_STATUS = ["OPEN", "CLOSED"]

# Valuation Methods
VALUATION_METHODS = ["AUTO", "MELT_ONLY", "GUIDE_ONLY", "MANUAL"]

# Grade Companies
GRADE_COMPANIES = [
    "PCGS", "NGC", "ANACS", "ICG", "PCI", "SEGS",
    "Raw", "Self-Graded", "Other"
]

# Common Grade Text Values
GRADE_TEXT_VALUES = [
    "P-1", "FR-2", "AG-3", "G-4", "G-6", "VG-8", "VG-10",
    "F-12", "F-15", "VF-20", "VF-25", "VF-30", "VF-35",
    "XF-40", "XF-45", "AU-50", "AU-53", "AU-55", "AU-58",
    "MS-60", "MS-61", "MS-62", "MS-63", "MS-64", "MS-65",
    "MS-66", "MS-67", "MS-68", "MS-69", "MS-70",
    "PF-60", "PF-61", "PF-62", "PF-63", "PF-64", "PF-65",
    "PF-66", "PF-67", "PF-68", "PF-69", "PF-70"
]

# Yahoo Finance Metal Symbols
YAHOO_METAL_SYMBOLS = {
    "Ag": "SI=F",  # Silver
    "Au": "GC=F",  # Gold
    "Pt": "PL=F",  # Platinum
    "Pd": "PA=F"   # Palladium
}

# Storage Location Categories
STORAGE_CATEGORIES = [
    "Safe Deposit Box", "Home Safe", "Bank Vault",
    "Safety Deposit Box", "Personal Collection", "Display Case"
]

# Party Types
PARTY_TYPES = ["Dealer", "Private Seller", "Auction House", "Online Retailer", "Individual"]

# Database Configuration
DEFAULT_CURRENCY = "USD"
TROY_OUNCE_TO_GRAMS = 31.1034768

# UI Configuration
DEFAULT_PAGE_SIZE = 50
MAX_UPLOAD_SIZE_MB = 10

# Date Formats
DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# Validation Rules
MIN_YEAR = 1000
MAX_YEAR = 2100
MIN_PRICE = 0.01
MAX_PRICE = 1000000.00