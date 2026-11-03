"""Expected-return assumptions used by the optimiser.

We do NOT use historical average returns. Over 2007-2026 US equities returned
about 11% a year and gold about 9%, an unusually good period. An optimiser fed
those numbers would pile into whatever did best in the past ("chasing returns").

Instead we use simple, conservative long-term "building block" assumptions,
the way many private banks publish capital market assumptions:

    expected return = cash rate + the extra return (premium) for the risk taken

All figures are annual, nominal, in USD.
"""

import pandas as pd

CASH_RATE = 0.030             # long-run T-bill yield
BOND_PREMIUM = 0.010          # term + credit premium for investment-grade bonds
EQUITY_RISK_PREMIUM = 0.040   # extra return for holding equities (historically ~4-6%)
EXPECTED_INFLATION = 0.025    # gold has no income; assume it roughly keeps pace with inflation
GOLD_REAL_RETURN = 0.010

EXPECTED_RETURNS = pd.Series({
    "equities": CASH_RATE + EQUITY_RISK_PREMIUM,       # 7.0%
    "bonds": CASH_RATE + BOND_PREMIUM,                 # 4.0%
    "cash": CASH_RATE,                                 # 3.0%
    "gold": EXPECTED_INFLATION + GOLD_REAL_RETURN,     # 3.5%
})
