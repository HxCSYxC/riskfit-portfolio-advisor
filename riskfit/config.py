"""Project-wide settings: which ETFs stand in for each asset class, costs, and data dates."""

from pathlib import Path

# Equities are a fixed blend of regional ETFs, roughly matching a global index
# (MSCI ACWI is about 60% US, 30% other developed markets, 10% emerging markets).
# Global ETFs such as ACWI or VT only start in 2008, too late to test the 2008 crisis;
# these three all have history from 2003.
# The "hk_tilt" style moves 15% of the equity part into Hong Kong shares, for clients
# who want some home-market exposure. EWH is USD-denominated, like everything else here.
EQUITY_STYLES = {
    "global": {
        "label": "Global equities",
        "blend": {"SPY": 0.60, "EFA": 0.30, "EEM": 0.10},
    },
    "hk_tilt": {
        "label": "Global equities (HK tilt)",
        "blend": {"SPY": 0.50, "EFA": 0.25, "EEM": 0.10, "EWH": 0.15},
    },
}
DEFAULT_EQUITY_STYLE = "global"

# The other asset classes use one ETF each. All are USD-denominated.
ASSETS = {
    "bonds": "AGG",     # US investment-grade aggregate bonds (Treasuries + corporates + MBS)
    "cash": "BIL",      # 1-3 month US Treasury bills
    "gold": "GLD",      # Physical gold
}

ASSET_LABELS = {
    "equities": "Global equities",
    "bonds": "Investment-grade bonds",
    "cash": "Cash (T-bills)",
    "gold": "Gold",
}

# The order used everywhere for weight vectors.
ASSET_ORDER = ["equities", "bonds", "cash", "gold"]

# Costs used in the historical tests and the "after fees" expected return.
ANNUAL_FEE = 0.01          # 1% a year, an all-in assumption for advisory and fund costs
REBALANCE = "quarterly"    # back to target weights on the first trading day of each quarter

# The analysis runs in USD. HKD is pegged to USD (7.75-7.85 band), so percentage results
# are the same for an HKD client to within the width of the band (about 1.3%).
CURRENCIES = ["USD", "HKD"]

# Download from 2003 so the rolling stock-bond correlation has a long history.
# The four-asset common sample starts when the youngest ETF (BIL, May 2007) launched.
DATA_START = "2003-01-01"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_FILE = PROJECT_ROOT / "riskfit" / "data" / "cache" / "prices.csv"


def all_tickers():
    """Every ETF the project downloads."""
    tickers = []
    for style in EQUITY_STYLES.values():
        tickers += [t for t in style["blend"] if t not in tickers]
    return tickers + list(ASSETS.values())


def proxy_description(asset, equity_style=DEFAULT_EQUITY_STYLE):
    """The ETF (or ETF blend) behind an asset class, e.g. 'SPY 60% / EFA 30% / EEM 10%'."""
    if asset == "equities":
        blend = EQUITY_STYLES[equity_style]["blend"]
        return " / ".join(f"{ticker} {weight:.0%}" for ticker, weight in blend.items())
    return ASSETS[asset]


def asset_label(asset, equity_style=DEFAULT_EQUITY_STYLE):
    return EQUITY_STYLES[equity_style]["label"] if asset == "equities" else ASSET_LABELS[asset]
