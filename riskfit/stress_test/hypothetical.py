"""Hypothetical "what if" shocks, for risks the 2007-2026 history does not contain.

Each scenario is a one-off fall (or rise) in every asset class at the same time.
The portfolio's loss is simply the weighted sum of the shocks. The shock sizes are
judgement calls, written down here so they can be challenged.
"""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Shock:
    key: str
    name: str
    shocks: dict          # asset -> return, e.g. -0.12 = falls 12%
    description: str


HYPOTHETICAL_SCENARIOS = [
    Shock(
        key="rates_up_2",
        name="Interest rates rise 2%",
        shocks={"equities": -0.10, "bonds": -0.12, "cash": 0.00, "gold": -0.05},
        description="Bonds fall by roughly duration x rate change (about 6 years x 2% = 12%). "
                    "Shares and gold are assumed to fall too, as higher rates lower valuations.",
    ),
    Shock(
        key="stagflation",
        name="Stagflation",
        shocks={"equities": -0.30, "bonds": -0.10, "cash": 0.00, "gold": 0.15},
        description="High inflation with a weak economy, as in the 1970s. Shares and bonds fall "
                    "together; gold rises.",
    ),
    Shock(
        key="severe_recession",
        name="Severe recession",
        shocks={"equities": -0.40, "bonds": 0.05, "cash": 0.00, "gold": 0.00},
        description="A deep downturn where central banks cut rates. Shares fall sharply; "
                    "high-quality bonds rise a little.",
    ),
]


def hypothetical_test(weights, scenarios=HYPOTHETICAL_SCENARIOS):
    """Portfolio return under each hypothetical shock (one row per scenario)."""
    weights = pd.Series(weights, dtype=float)
    rows = [{"scenario": s.name,
             "portfolio_return": float(sum(weights[a] * s.shocks[a] for a in weights.index)),
             "description": s.description} for s in scenarios]
    return pd.DataFrame(rows).set_index("scenario")
