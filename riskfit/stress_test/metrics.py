"""Risk and performance measures for a daily return series.

All functions take simple daily returns (0.01 = +1%) as a pandas Series.
Losses (drawdown, VaR, expected shortfall) are returned as NEGATIVE numbers,
so -0.25 means "a 25% loss".
"""

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def portfolio_returns(asset_returns, weights):
    """Daily returns of a portfolio rebalanced back to its target weights every day.

    asset_returns: DataFrame, one column per asset
    weights: Series or dict, asset -> weight
    """
    weights = pd.Series(weights, dtype=float)
    return asset_returns[weights.index].dropna() @ weights


def wealth_index(returns, start_value=1.0):
    """Value over time of 1 unit invested (includes the starting point)."""
    start = pd.Series([start_value], index=[returns.index[0] - pd.Timedelta(days=1)])
    return pd.concat([start, start_value * (1 + returns).cumprod()])


def total_return(returns):
    return float((1 + returns).prod() - 1)


def drawdown_series(returns):
    """How far below its previous peak the portfolio is on each day (0 or negative)."""
    wealth = wealth_index(returns)
    return wealth / wealth.cummax() - 1


def max_drawdown(returns):
    """Largest peak-to-trough fall."""
    return float(drawdown_series(returns).min())


def recovery_days(returns, start, end):
    """Calendar days from the lowest point of a crisis until the portfolio is back at its pre-crisis peak.

    returns: the FULL daily return history, so we can look beyond the crisis end date
    start, end: the crisis window, which is used to find the trough
    Returns None if the portfolio had not recovered by the end of the data.
    """
    wealth = wealth_index(returns.loc[start:])
    in_window = wealth.loc[:end]
    trough_date = in_window.idxmin()
    peak_before_trough = in_window.loc[:trough_date].max()
    recovered = wealth.loc[trough_date:]
    recovered = recovered[recovered >= peak_before_trough]
    if recovered.empty:
        return None
    return int((recovered.index[0] - trough_date).days)


def annualised_volatility(returns):
    return float(returns.std() * np.sqrt(TRADING_DAYS))


def annualised_return(returns):
    """Compound annual growth rate."""
    years = len(returns) / TRADING_DAYS
    return float((1 + total_return(returns)) ** (1 / years) - 1)


def historical_var(returns, level=0.95):
    """Historical Value at Risk: the daily loss that was exceeded on only (1 - level) of days.

    Example: -0.015 at 95% means that on 95% of days the loss was smaller than 1.5%.
    """
    return float(returns.quantile(1 - level))


def expected_shortfall(returns, level=0.95):
    """Average daily loss on the worst (1 - level) of days, i.e. how bad the bad days are."""
    var = historical_var(returns, level)
    return float(returns[returns <= var].mean())


def rolling_correlation(returns_a, returns_b, window=36):
    """Rolling correlation, e.g. 36 months = 3 years when given monthly returns."""
    return returns_a.rolling(window).corr(returns_b).dropna()
