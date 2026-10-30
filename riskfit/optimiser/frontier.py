"""Efficient frontier: the best expected return available for each level of risk.

Run this file to print the five profile portfolios and save the frontier chart:
    python -m riskfit.optimiser.frontier
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from riskfit.config import ASSET_ORDER, PROJECT_ROOT
from riskfit.optimiser.mean_variance import (
    build_all_profiles,
    market_inputs,
    min_variance_portfolio,
    portfolio_stats,
)

LONG_ONLY = [(0.0, 1.0)] * len(ASSET_ORDER)


def efficient_frontier(mu, cov, bounds=LONG_ONLY, n_points=40):
    """Minimum-volatility portfolio for a grid of target returns.

    Returns a DataFrame with columns: expected_return, volatility, and one weight per asset.
    The grid runs from the minimum-variance portfolio up to the highest return the
    weight limits allow.
    """
    mu_arr, sigma = np.asarray(mu), np.asarray(cov)
    w_min = min_variance_portfolio(cov, bounds)
    lowest = float(w_min @ mu_arr)
    highest = _max_possible_return(mu_arr, bounds)

    rows = []
    w_start = w_min
    for target in np.linspace(lowest, highest, n_points):
        result = minimize(
            lambda w: w @ sigma @ w,
            w_start,
            method="SLSQP",
            bounds=bounds,
            constraints=[
                {"type": "eq", "fun": lambda w: w.sum() - 1},
                {"type": "eq", "fun": lambda w, t=target: w @ mu_arr - t},
            ],
            options={"ftol": 1e-12, "maxiter": 500},
        )
        if not result.success:
            continue
        w_start = result.x
        ret, vol = portfolio_stats(result.x, mu_arr, sigma)
        rows.append({"expected_return": ret, "volatility": vol, **dict(zip(mu.index, result.x))})
    return pd.DataFrame(rows)


def _max_possible_return(mu_arr, bounds):
    """Highest return within the limits: fill the best assets first, up to their maximum."""
    weights = np.array([b[0] for b in bounds], dtype=float)
    remaining = 1 - weights.sum()
    for i in np.argsort(-mu_arr):
        add = min(bounds[i][1] - weights[i], remaining)
        weights[i] += add
        remaining -= add
    return float(weights @ mu_arr)


if __name__ == "__main__":
    from riskfit.report.charts import plot_efficient_frontier
    from riskfit.risk_profile.profiles import PROFILES

    mu, cov = market_inputs()
    frontier = efficient_frontier(mu, cov)
    portfolios = build_all_profiles(mu, cov)

    table = pd.DataFrame({
        PROFILES[level].name: {**(p.weights * 100).round(1).to_dict(),
                               "exp. return %": round(p.expected_return * 100, 2),
                               "volatility %": round(p.volatility * 100, 2)}
        for level, p in portfolios.items()
    }).T
    print(table.to_string())

    out = PROJECT_ROOT / "docs" / "images" / "efficient_frontier.png"
    plot_efficient_frontier(frontier, portfolios, mu, cov).savefig(out, dpi=200, bbox_inches="tight")
    print(f"Saved {out}")
