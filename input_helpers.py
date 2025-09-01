# input_helpers.py
"""Helper functions for handling numeric inputs in Streamlit (workaround for number_input bug)."""

def safe_float(value: str, default: float = 0.0) -> float:
    """Convert string to float safely."""
    if value is None or value == "" or str(value).strip().lower() in {"nan", "none", "null", "-", "—"}:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value: str, default: int = 0) -> int:
    """Convert string to int safely."""
    if value is None or value == "" or str(value).strip().lower() in {"nan", "none", "null", "-", "—"}:
        return default
    try:
        return int(float(value))  # Handle "1.0" -> 1
    except (ValueError, TypeError):
        return default


def format_float(value: float, decimals: int = 2) -> str:
    """Format float for display in text input."""
    if value is None or value == 0:
        return "0.00" if decimals == 2 else "0.0"
    return f"{value:.{decimals}f}"