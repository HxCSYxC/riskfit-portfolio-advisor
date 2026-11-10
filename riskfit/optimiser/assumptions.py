"""Expected-return assumptions used by the optimiser.

We do NOT use historical average returns. Over 2007-2026 global equities returned
about 8% a year and gold about 9%, a good period that may not repeat. An optimiser
fed those numbers would pile into whatever did best in the past ("chasing returns").

Instead we use simple, conservative long-term "building block" assumptions,
the way many private banks publish capital market assumptions:

    expected return = cash rate + the extra return (premium) for the risk taken

All figures are annual, nominal, in USD, before fees.
"""

import pandas as pd

CASH_RATE = 0.030             # long-run T-bill yield
BOND_PREMIUM = 0.010          # term + credit premium for investment-grade bonds
EQUITY_RISK_PREMIUM = 0.040   # extra return for holding equities (historically ~4-6%)
EXPECTED_INFLATION = 0.025    # gold has no income; assume it roughly keeps pace with inflation
GOLD_REAL_RETURN = 0.010


def expected_returns(cash_rate=CASH_RATE, bond_premium=BOND_PREMIUM, equity_risk_premium=EQUITY_RISK_PREMIUM,
                     expected_inflation=EXPECTED_INFLATION, gold_real_return=GOLD_REAL_RETURN):
    """Expected returns built from the blocks above. Pass different blocks to test sensitivity."""
    return pd.Series({
        "equities": cash_rate + equity_risk_premium,       # 7.0%
        "bonds": cash_rate + bond_premium,                 # 4.0%
        "cash": cash_rate,                                 # 3.0%
        "gold": expected_inflation + gold_real_return,     # 3.5%
    })


EXPECTED_RETURNS = expected_returns()
