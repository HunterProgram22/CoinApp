# constants.py
"""
Shared constants for the Coin Tracker application.
Centralizes all enum-like values to avoid duplication across modules.
"""

# Navigation configuration
NAVIGATION_ITEMS = [
    ("Home.py", "Home", "🏠"),
    ("pages/05_Dashboard.py", "Dashboard", "📊"),
    ("pages/10_Inventory.py", "Inventory", "📦"),
    ("pages/15_World_Coins.py", "World Coins", "🌍️"),
    ("pages/20_Bullion.py", "Bullion", "💰"),
    ("pages/25_Coin_Registry.py", "Coin Registry", "🏷️"),
    ("pages/30_Proof_Sets.py", "Proof Sets", "🎁"),
    ("pages/32_Coin_Catalog.py", "Coin Catalog", "📚"),
    ("pages/34_Series_Analysis.py", "Series Analysis", "📊"),
    ("pages/35_Type_Sets.py", "Type Sets", "💼"),
    ("pages/40_Storage_Report.py", "Storage Report", "📦"),
    ("pages/45_Transactions.py", "Transactions", "➕"),
    ("pages/48_Admin.py", "Admin", "🛠️"),
    ("pages/50_Data_Import.py", "Data Import", "📥"),
    ("pages/55_Reports.py", "Reports", "📊"),
]


# App configuration
APP_TITLE = "Coin Tracker"
APP_SUBTITLE = "Inventory • Transactions • Storage • Analytics"

# Metal ordering for display
METAL_DISPLAY_ORDER = ["Ag", "Au", "Pt", "Pd"]

# Silver coin specifications (fine troy ounces)
SILVER_COIN_SPECS = {
    "American Silver Eagle (1 oz)": 1.00000,
    "Morgan/Peace Dollar (90%)": 0.77344,  # 26.73g, .900 fine
    "Pre-1965 US Half Dollar (90%)": 0.36169,  # 12.50g, .900 fine
    "Pre-1965 US Quarter (90%)": 0.18084,  # 6.25g, .900 fine
    "Pre-1965 US Dime (90%)": 0.07234,  # 2.50g, .900 fine
    "Pre-1968 Canadian Quarter (80%)": 0.15000,    # 5.83g, .800 fine
    "US Kennedy Half Dollar 1965-1970 (40%)": 0.14792, # 11.50g, .400 fine
    "US War Nickel 1942-1945 (35%)": 0.05626,     # 5.00g, .350 fine
}

# Column configurations for common data types
COLUMN_CONFIGS = {
    "currency": lambda format_str="$%.2f": {
        "format": format_str
    },
    "integer": {
        "format": "%d"
    },
    "percentage": {
        "format": "%.2f"
    },
    "decimal": lambda precision=5: {
        "format": f"%.{precision}f"
    }
}

# Dashboard column mappings
DASHBOARD_COLUMN_RENAMES = {
    "metal": "Metal",
    "price_per_oz_usd": "Price Per Oz. (USD)",
    "series": "Series",
    "coins": "Coins",
    "melt_total_usd": "Melt Value (USD)",
    "numi_total_usd": "Numismatic Value (USD)",
    "cost_total_usd": "Total Cost (USD)",
    "chosen_total_usd": "Est. Value (USD)",
    "unreal_gl_usd": "Unrealized G/L (USD)",
    "unreal_gl_pct": "Unrealized G/L (%)",
}

# Asset Categories
ASSET_CATEGORIES = ["COIN", "ROUND", "BAR", "BULLION COIN", "TOKEN"]

# Transaction Types
TRANSACTION_TYPES = ["BUY", "SELL", "FEE", "ADJUST", "GIFT_IN", "GIFT_OUT", "TRANSFER"]

# Metals (ordered by common usage)
METALS = ["Ag", "Au", "Pt", "Pd", "Cu", "Ni", "Zn"]

# Currencies (ordered by common usage)
CURRENCIES = ["USD", "CAD", "EUR", "GBP"]

# Lot Status Options
LOT_STATUS = ["OPEN", "CLOSED"]

# Valuation Methods
VALUATION_METHODS = ["AUTO", "MELT_ONLY", "GUIDE_ONLY", "MANUAL"]

# Grade Companies (ordered by popularity/recognition)
GRADE_COMPANIES = [
    "PCGS", "NGC", "ANACS", "ICG", "PCI", "SEGS",
    "Raw", "Self-Graded", "Other"
]

# Common Grade Text Values (properly ordered)
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

# Party Types (ordered by common usage)
PARTY_TYPES = ["Dealer", "Online Retailer", "Auction House", "Private Seller", "Individual"]

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

# Export Configuration
CSV_EXPORT_ENCODING = "utf-8"
EXCEL_EXPORT_ENGINE = "openpyxl"

# Error Messages (commonly used)
ERROR_MESSAGES = {
    "INVALID_DATE": "Please enter a valid date in YYYY-MM-DD format",
    "INVALID_PRICE": f"Price must be between ${MIN_PRICE} and ${MAX_PRICE:,.2f}",
    "INVALID_YEAR": f"Year must be between {MIN_YEAR} and {MAX_YEAR}",
    "REQUIRED_FIELD": "This field is required",
    "INSUFFICIENT_INVENTORY": "Not enough inventory available for this transaction",
    "DUPLICATE_RECORD": "A record with these details already exists"
}