"""The five risk profiles and the portfolio rules attached to each one.

Each profile has:
- a target volatility: the optimiser may not take more risk than this
- weight limits per asset class, so even the "optimal" portfolio stays sensible
- a loss limit: the largest peak-to-trough fall the client should be ready for.
  It is calibrated so that each profile's worst historical drawdown (2008, 2020,
  2022 stress tests) stays inside it, and it matches the client's maximum acceptable loss.

Every profile holds at least 5% gold. With our conservative return assumption for
gold, pure mean-variance optimisation would hold none. Gold's main value is as a
crisis diversifier, which one average covariance matrix does not capture, so we
keep a small strategic floor as a policy choice.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskProfile:
    level: int                 # 1 (lowest risk) to 5 (highest risk)
    name: str
    target_volatility: float   # annualised, e.g. 0.09 = 9%
    loss_limit: float          # largest fall the client should expect to live with, e.g. 0.25 = -25%
    weight_limits: dict        # asset -> (min weight, max weight)
    description: str


PROFILES = {
    1: RiskProfile(
        level=1,
        name="Conservative",
        target_volatility=0.04,
        loss_limit=0.15,
        weight_limits={"equities": (0.00, 0.20), "bonds": (0.30, 0.80),
                       "cash": (0.10, 0.60), "gold": (0.05, 0.10)},
        description="Protecting capital matters most. Accepts low returns to keep losses small.",
    ),
    2: RiskProfile(
        level=2,
        name="Moderately Conservative",
        target_volatility=0.065,
        loss_limit=0.25,
        weight_limits={"equities": (0.10, 0.40), "bonds": (0.25, 0.70),
                       "cash": (0.05, 0.40), "gold": (0.05, 0.10)},
        description="Mainly wants stability, with some growth. Accepts small, short-lived losses.",
    ),
    3: RiskProfile(
        level=3,
        name="Balanced",
        target_volatility=0.09,
        loss_limit=0.35,
        weight_limits={"equities": (0.30, 0.60), "bonds": (0.15, 0.60),
                       "cash": (0.00, 0.30), "gold": (0.05, 0.15)},
        description="Wants a balance of growth and stability. Accepts moderate ups and downs.",
    ),
    4: RiskProfile(
        level=4,
        name="Moderately Aggressive",
        target_volatility=0.115,
        loss_limit=0.45,
        weight_limits={"equities": (0.45, 0.80), "bonds": (0.05, 0.45),
                       "cash": (0.00, 0.20), "gold": (0.05, 0.15)},
        description="Focused on long-term growth. Accepts sizeable falls along the way.",
    ),
    5: RiskProfile(
        level=5,
        name="Aggressive",
        target_volatility=0.14,
        loss_limit=0.60,
        weight_limits={"equities": (0.60, 0.95), "bonds": (0.00, 0.30),
                       "cash": (0.00, 0.15), "gold": (0.05, 0.15)},
        description="Seeks maximum long-term growth. Accepts large, possibly long-lasting losses.",
    ),
}


def get_profile(level):
    if level not in PROFILES:
        raise ValueError(f"Risk level must be 1-5, got {level}")
    return PROFILES[level]
