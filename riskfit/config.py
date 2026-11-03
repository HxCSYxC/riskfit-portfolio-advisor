"""Project-wide settings: which ETFs stand in for each asset class, and data dates."""

from pathlib import Path

# Asset class -> ETF ticker used as a proxy. All are USD-denominated.
# HKD is pegged to USD (7.75-7.85 band), so USD results are a fair guide for HK clients.
ASSETS = {
    "equities": "SPY",  # S&P 500. US large-cap proxy for global equities (ACWI/VT only start in 2008)
    "bonds": "AGG",     # US investment-grade aggregate bonds (Treasuries + corporates + MBS)
    "cash": "BIL",      # 1-3 month US Treasury bills
    "gold": "GLD",      # Physical gold
}

ASSET_LABELS = {
    "equities": "Equities (US large-cap)",
    "bonds": "Investment-grade bonds",
    "cash": "Cash (T-bills)",
    "gold": "Gold",
}

# The order used everywhere for weight vectors.
ASSET_ORDER = ["equities", "bonds", "cash", "gold"]

# Download from 2003 so the rolling stock-bond correlation has a long history.
# The four-asset common sample starts when the youngest ETF (BIL, May 2007) launched.
DATA_START = "2003-01-01"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_FILE = PROJECT_ROOT / "riskfit" / "data" / "cache" / "prices.csv"
