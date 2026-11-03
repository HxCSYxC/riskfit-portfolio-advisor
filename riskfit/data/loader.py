"""Download ETF prices from Yahoo Finance, clean them, and cache them in a CSV file.

Usage:
    python -m riskfit.data.loader            # use the cache if it exists, else download
    python -m riskfit.data.loader --refresh  # force a fresh download
"""

import argparse
from pathlib import Path

import pandas as pd

from riskfit.config import ASSETS, CACHE_FILE, DATA_START

# The 2008 stress test starts here, so every ETF must have data by this date.
GFC_START = pd.Timestamp("2007-10-09")


def download_prices(tickers, start=DATA_START, end=None):
    """Download daily adjusted close prices for a list of tickers.

    auto_adjust=True folds dividends and splits into the price, so the
    percentage change of these prices is a total return. This matters a lot
    for bonds and cash, where almost all of the return comes from income.
    """
    import yfinance as yf  # imported here so the rest of the project works offline

    raw = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)
    if raw.empty:
        raise RuntimeError(
            "No data downloaded. Check your internet connection or that Yahoo Finance is reachable."
        )
    prices = raw["Close"]
    if isinstance(prices, pd.Series):  # a single ticker comes back as a Series
        prices = prices.to_frame(tickers[0])
    return prices[tickers]


def clean_prices(prices, max_gap_days=5):
    """Tidy a raw price table.

    - sort dates and drop duplicate dates
    - fill short gaps (e.g. a missing quote on one day) with the last known price
    - drop rows where every ticker is missing
    Long gaps are left as NaN on purpose, so we never invent prices before an ETF existed.
    """
    prices = prices.copy()
    prices.index = pd.to_datetime(prices.index).tz_localize(None)
    prices = prices[~prices.index.duplicated(keep="last")].sort_index()
    prices = prices.ffill(limit=max_gap_days)
    return prices.dropna(how="all")


def save_cache(prices, path=CACHE_FILE):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    prices.to_csv(path, index_label="date", float_format="%.6f")


def read_cache(path=CACHE_FILE):
    return pd.read_csv(path, index_col="date", parse_dates=True)


def load_prices(refresh=False, path=CACHE_FILE):
    """Return cleaned prices with one column per asset class (equities, bonds, cash, gold).

    Reads the local CSV cache when it exists, so the app does not download every run.
    """
    path = Path(path)
    if refresh or not path.exists():
        tickers = list(ASSETS.values())
        prices = clean_prices(download_prices(tickers))
        save_cache(prices, path)
    prices = read_cache(path)
    ticker_to_asset = {ticker: asset for asset, ticker in ASSETS.items()}
    return prices.rename(columns=ticker_to_asset)[list(ASSETS)]


def common_sample(prices):
    """Keep only dates where every asset has a price (needed for covariance estimates)."""
    return prices.dropna(how="any")


def to_returns(prices, freq="D"):
    """Simple returns. freq='D' for daily, 'M' for month-end returns."""
    if freq == "M":
        prices = prices.resample("ME").last()
    elif freq != "D":
        raise ValueError("freq must be 'D' or 'M'")
    return prices.pct_change(fill_method=None).dropna(how="all")


def availability_report(prices):
    """First and last date for each asset, and whether it covers the 2008 crisis."""
    rows = []
    for col in prices.columns:
        series = prices[col].dropna()
        rows.append({
            "asset": col,
            "first_date": series.index.min().date(),
            "last_date": series.index.max().date(),
            "observations": len(series),
            "covers_2008": series.index.min() <= GFC_START,
        })
    return pd.DataFrame(rows).set_index("asset")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download and cache ETF price data.")
    parser.add_argument("--refresh", action="store_true", help="force a fresh download")
    args = parser.parse_args()

    data = load_prices(refresh=args.refresh)
    print(f"Saved to {CACHE_FILE}")
    print(availability_report(data))
