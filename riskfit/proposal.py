"""Pull every step together: questionnaire -> portfolio -> stress tests -> plain-English story.

Both the Streamlit app and the PDF generator use build_proposal(), so they always show the same numbers.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import date

import pandas as pd

from riskfit.config import ANNUAL_FEE, ASSET_ORDER, DEFAULT_EQUITY_STYLE, REBALANCE
from riskfit.data.loader import common_sample, load_prices, to_returns
from riskfit.optimiser.mean_variance import PortfolioResult, build_profile_portfolio, market_inputs
from riskfit.risk_profile.questionnaire import ProfileResult, score_client
from riskfit.stress_test.hypothetical import hypothetical_test
from riskfit.stress_test.scenarios import risk_summary, stress_test, worst_scenario


@dataclass
class Client:
    """A (fictional) client and their questionnaire answers, stored as option numbers."""
    name: str
    age: int
    investment_amount: float           # in the client's currency
    answers: dict                      # tolerance question id -> option index
    horizon: int                       # index into HORIZON_OPTIONS
    max_loss: int                      # index into MAX_LOSS_OPTIONS
    liquidity: int                     # index into LIQUIDITY_OPTIONS
    notes: str = ""
    currency: str = "USD"              # "USD" or "HKD": used for display only (HKD is pegged to USD)
    equity_style: str = DEFAULT_EQUITY_STYLE   # "global" or "hk_tilt"

    @classmethod
    def from_json(cls, path):
        with open(path, encoding="utf-8") as f:
            return cls(**json.load(f))

    def to_json(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)


@dataclass
class Proposal:
    client: Client
    profile: ProfileResult
    portfolio: PortfolioResult
    stress: pd.DataFrame               # one row per historical crisis
    hypothetical: pd.DataFrame         # one row per "what if" shock
    risk: dict                         # full-period risk measures
    asset_returns: pd.DataFrame        # daily asset returns used for the tests (for charts)
    data_start: date
    data_end: date
    annual_fee: float = ANNUAL_FEE
    rebalance: str = REBALANCE
    created: date = field(default_factory=date.today)

    @property
    def expected_return_net(self):
        """Expected return after the assumed yearly fee."""
        return self.portfolio.expected_return - self.annual_fee

    @property
    def typical_range(self):
        """Expected return (after fees) plus/minus one historical volatility: roughly 2 years in 3 fall inside."""
        vol = self.risk["annual_volatility"]
        return self.expected_return_net - vol, self.expected_return_net + vol

    def money(self, amount, round_to=1):
        return format_money(amount, self.client.currency, round_to)

    @property
    def worst(self):
        """(scenario name, row) for the crisis with the deepest fall."""
        return worst_scenario(self.stress)


def format_money(amount, currency="USD", round_to=1):
    """'USD 1,500,000' or '-HKD 471,000'. Use round_to=1000 for estimates, so they don't look falsely precise."""
    amount = round(amount / round_to) * round_to
    sign = "-" if amount < 0 else ""
    return f"{sign}{currency} {abs(amount):,.0f}"


def build_proposal(client, prices=None, annual_fee=ANNUAL_FEE, rebalance=REBALANCE):
    """Score the client, optimise their portfolio and run every test.

    prices: asset-class prices for the client's equity style (loaded from the cache if not given).
    """
    if prices is None:
        prices = load_prices(client.equity_style)
    profile = score_client(client.answers, client.horizon, client.max_loss, client.liquidity)
    mu, cov = market_inputs(prices)
    portfolio = build_profile_portfolio(profile.profile, mu, cov, min_cash=profile.min_cash)

    daily = to_returns(common_sample(prices[ASSET_ORDER]), "D")
    return Proposal(
        client=client,
        profile=profile,
        portfolio=portfolio,
        stress=stress_test(daily, portfolio.weights, rebalance=rebalance, annual_fee=annual_fee),
        hypothetical=hypothetical_test(portfolio.weights),
        risk=risk_summary(daily, portfolio.weights, rebalance=rebalance, annual_fee=annual_fee),
        asset_returns=daily,
        data_start=daily.index[0].date(),
        data_end=daily.index[-1].date(),
        annual_fee=annual_fee,
        rebalance=rebalance,
    )


# What each asset class does in the portfolio, in client language: (short name, purpose).
ASSET_ROLES = {
    "equities": ("shares from around the world", "drive long-term growth (they also cause most of the ups and downs)"),
    "bonds": ("high-quality bonds", "provide income and usually cushion falls in share prices"),
    "cash": ("cash", "keep part of your money stable and available when you need it"),
    "gold": ("gold", "add diversification, as gold has tended to hold its value in financial crises"),
}


def pct(x, signed=False):
    """Whole-number percentage that never shows '-0%'."""
    if round(x * 100) == 0:
        return "0%"
    return f"{x:+.0%}" if signed else f"{x:.0%}"


def explain_allocation(proposal):
    """A few short plain-English paragraphs on why this mix suits the client."""
    p, w = proposal.profile, proposal.portfolio.weights
    name, worst = proposal.worst
    low, high = proposal.typical_range

    paragraphs = [" ".join(p.reasons)]
    if proposal.client.equity_style == "hk_tilt":
        paragraphs[0] += " At your request, 15% of the shares are Hong Kong companies."
    paragraphs.append(
        f"This {p.profile.name} portfolio aims for the best long-term return we can expect while keeping "
        f"the ups and downs within what you told us you can accept. Each part has a job: "
        + "; ".join(f"{w[a]:.0%} in {ASSET_ROLES[a][0]} to {ASSET_ROLES[a][1]}"
                    for a in ASSET_ORDER if w[a] >= 0.005)
        + "."
    )
    paragraphs.append(
        f"After an assumed {proposal.annual_fee:.0%} yearly fee, we expect a return of about "
        f"{proposal.expected_return_net:.1%} a year, "
        f"and in roughly two years out of three the result should fall between {pct(low)} and {pct(high)}. "
        f"In the worst crisis we tested ({name}) this mix fell {-worst.max_drawdown:.0%} at its lowest point, "
        f"which is within the {p.profile.loss_limit:.0%} limit for this profile. "
        "Losses like this are temporary only if you can stay invested, so please keep money you may "
        "need soon outside the portfolio or in its cash part."
    )
    return paragraphs
