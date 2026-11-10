"""How much do the recommended weights depend on the return assumptions?

Expected returns are the weakest input of any mean-variance optimiser, so we re-run
the optimiser with each building block moved up or down and compare the weights.

    python -m riskfit.optimiser.sensitivity
"""

import pandas as pd

from riskfit.config import ASSET_ORDER
from riskfit.optimiser.assumptions import expected_returns
from riskfit.optimiser.mean_variance import build_profile_portfolio

# Each case changes one building block. The base case is 4% equity premium, 1% bond premium, 1% gold real return.
CASES = {
    "Base case": {},
    "Equity premium 3% (lower)": {"equity_risk_premium": 0.03},
    "Equity premium 5% (higher)": {"equity_risk_premium": 0.05},
    "Bond premium 0.5% (lower)": {"bond_premium": 0.005},
    "Bond premium 1.5% (higher)": {"bond_premium": 0.015},
    "Gold real return 3% (higher)": {"gold_real_return": 0.03},
}


def assumption_sensitivity(profile, cov, min_cash=0.0, cases=CASES):
    """Weights and expected return of one profile under each set of assumptions."""
    rows = {}
    for name, changes in cases.items():
        mu = expected_returns(**changes)[ASSET_ORDER]
        portfolio = build_profile_portfolio(profile, mu, cov, min_cash)
        rows[name] = {**portfolio.weights.to_dict(), "expected_return": portfolio.expected_return}
    return pd.DataFrame(rows).T


if __name__ == "__main__":
    from riskfit.optimiser.mean_variance import market_inputs
    from riskfit.risk_profile.profiles import PROFILES

    _, cov = market_inputs()
    for profile in PROFILES.values():
        print(f"\n{profile.name}\n{(assumption_sensitivity(profile, cov) * 100).round(1).to_string()}")
