"""Mean-variance optimisation with a volatility target and weight limits.

For each risk profile we solve:

    maximise    expected return            w . mu
    subject to  portfolio volatility       sqrt(w' Sigma w) <= target volatility
                weights add up to 100%     sum(w) = 1
                weight limits per asset    min_i <= w_i <= max_i   (no short selling)

mu    = expected returns (from assumptions.py, not from history)
Sigma = covariance matrix, estimated from monthly returns with Ledoit-Wolf shrinkage
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf

from riskfit.config import ASSET_ORDER
from riskfit.data.loader import common_sample, load_prices, to_returns
from riskfit.optimiser.assumptions import EXPECTED_RETURNS
from riskfit.risk_profile.profiles import PROFILES


@dataclass
class PortfolioResult:
    weights: pd.Series         # asset -> weight, sums to 1
    expected_return: float     # annual
    volatility: float          # annual
    target_volatility: float
    target_met: bool           # False if even the safest allowed mix is riskier than the target


def estimate_covariance(monthly_returns):
    """Annualised covariance matrix with Ledoit-Wolf shrinkage of the correlations.

    The plain sample covariance is noisy: with limited data, some correlations
    look stronger or weaker than they really are, and the optimiser exploits
    those errors. Ledoit-Wolf pulls the sample matrix part of the way towards a
    simple, stable target and picks how far to pull from the data itself.

    We apply it to standardised returns, so only the correlations are shrunk
    (towards zero). Each asset keeps its own measured volatility. Otherwise the
    shrinkage would pull every volatility towards the average and make cash look
    about four times riskier than it really is.
    """
    std = monthly_returns.std()
    standardised = (monthly_returns - monthly_returns.mean()) / std
    shrunk = LedoitWolf().fit(standardised.values).covariance_
    scale = np.sqrt(np.diag(shrunk))
    corr = shrunk / np.outer(scale, scale)
    cov = corr * np.outer(std, std) * 12   # monthly -> annual
    return pd.DataFrame(cov, index=monthly_returns.columns, columns=monthly_returns.columns)


def shrinkage_intensity(monthly_returns):
    """How far (0 = not at all, 1 = fully) Ledoit-Wolf pulls the correlations towards zero."""
    standardised = (monthly_returns - monthly_returns.mean()) / monthly_returns.std()
    return float(LedoitWolf().fit(standardised.values).shrinkage_)


def market_inputs(prices=None):
    """Expected returns and covariance matrix, both ordered as ASSET_ORDER."""
    if prices is None:
        prices = load_prices()
    monthly = to_returns(common_sample(prices[ASSET_ORDER]), "M")
    return EXPECTED_RETURNS[ASSET_ORDER], estimate_covariance(monthly)


def portfolio_stats(weights, mu, cov):
    """Expected return and volatility of a weight vector."""
    w = np.asarray(weights, dtype=float)
    return float(w @ np.asarray(mu)), float(np.sqrt(w @ np.asarray(cov) @ w))


def profile_bounds(profile, min_cash=0.0):
    """Weight limits for a profile, raising the cash floor for liquidity needs."""
    bounds = dict(profile.weight_limits)
    low, high = bounds["cash"]
    low = max(low, min_cash)
    bounds["cash"] = (low, max(high, low))
    return [bounds[asset] for asset in ASSET_ORDER]


def _check_bounds(bounds):
    if sum(low for low, _ in bounds) > 1 + 1e-9 or sum(high for _, high in bounds) < 1 - 1e-9:
        raise ValueError("Weight limits cannot add up to 100%")


def _start_point(bounds):
    """A feasible starting guess: the lower limits, topped up evenly to 100%."""
    low = np.array([b[0] for b in bounds])
    room = np.array([b[1] - b[0] for b in bounds])
    return low + room * (1 - low.sum()) / room.sum()


def min_variance_portfolio(cov, bounds):
    """The least risky portfolio allowed by the weight limits."""
    _check_bounds(bounds)
    sigma = np.asarray(cov)
    result = minimize(
        lambda w: w @ sigma @ w,
        _start_point(bounds),
        method="SLSQP",
        bounds=bounds,
        constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}],
        options={"ftol": 1e-12, "maxiter": 500},
    )
    if not result.success:
        raise RuntimeError(f"Minimum-variance optimisation failed: {result.message}")
    return result.x


def max_return_portfolio(mu, cov, target_vol, bounds):
    """Highest expected return with volatility at or below target_vol."""
    _check_bounds(bounds)
    mu_arr, sigma = np.asarray(mu), np.asarray(cov)

    # If even the safest allowed portfolio breaks the target, return that one and flag it.
    w_min = min_variance_portfolio(cov, bounds)
    if np.sqrt(w_min @ sigma @ w_min) > target_vol:
        weights, target_met = w_min, False
    else:
        result = minimize(
            lambda w: -(w @ mu_arr),
            w_min,
            method="SLSQP",
            bounds=bounds,
            constraints=[
                {"type": "eq", "fun": lambda w: w.sum() - 1},
                {"type": "ineq", "fun": lambda w: target_vol**2 - w @ sigma @ w},
            ],
            options={"ftol": 1e-12, "maxiter": 500},
        )
        if not result.success:
            raise RuntimeError(f"Optimisation failed: {result.message}")
        weights, target_met = result.x, True

    # Clean tiny numerical noise (e.g. -1e-12) so weights are exact and sum to 1.
    weights = np.clip(weights, [b[0] for b in bounds], [b[1] for b in bounds])
    weights = weights / weights.sum()
    expected_return, volatility = portfolio_stats(weights, mu_arr, sigma)
    return PortfolioResult(
        weights=pd.Series(weights, index=list(mu.index) if hasattr(mu, "index") else ASSET_ORDER),
        expected_return=expected_return,
        volatility=volatility,
        target_volatility=target_vol,
        target_met=target_met,
    )


def build_profile_portfolio(profile, mu, cov, min_cash=0.0):
    """The recommended portfolio for one risk profile."""
    return max_return_portfolio(mu, cov, profile.target_volatility, profile_bounds(profile, min_cash))


def build_all_profiles(mu, cov):
    """Recommended portfolio for each of the five profiles (no liquidity needs)."""
    return {level: build_profile_portfolio(profile, mu, cov) for level, profile in PROFILES.items()}
