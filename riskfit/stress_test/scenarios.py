"""Historical stress scenarios and the summary tables built from them.

Each scenario replays the portfolio's current weights through a real crisis.
The portfolio is assumed to be rebalanced to its target weights every day,
with no fees or taxes.

Run this file to print the results for the five profiles and save the charts:
    python -m riskfit.stress_test.scenarios
"""

from dataclasses import dataclass

import pandas as pd

from riskfit.stress_test import metrics


@dataclass(frozen=True)
class Scenario:
    key: str
    name: str
    start: str
    end: str
    description: str


SCENARIOS = [
    Scenario(
        key="gfc",
        name="Global Financial Crisis",
        start="2007-10-09",   # S&P 500 peak
        end="2009-03-09",     # S&P 500 bottom
        description="US housing and banking crisis. Stocks fell by about half; "
                    "high-quality bonds and gold held up.",
    ),
    Scenario(
        key="covid",
        name="COVID-19 crash",
        start="2020-02-19",
        end="2020-03-23",
        description="Pandemic lockdowns. The fastest fall in stock market history, "
                    "about one third in five weeks; almost everything fell for a few days.",
    ),
    Scenario(
        key="inflation_2022",
        name="2022 inflation and rate shock",
        start="2022-01-01",
        end="2022-12-31",
        description="Inflation hit a 40-year high and the Fed raised rates fast. "
                    "Stocks AND bonds fell together, so bonds gave no protection.",
    ),
]


def run_scenario(daily_portfolio_returns, scenario):
    """Return, max drawdown and recovery time of a portfolio in one scenario."""
    window = daily_portfolio_returns.loc[scenario.start:scenario.end]
    return {
        "scenario": scenario.name,
        "start": window.index[0].date(),
        "end": window.index[-1].date(),
        "total_return": metrics.total_return(window),
        "max_drawdown": metrics.max_drawdown(window),
        "recovery_days": metrics.recovery_days(daily_portfolio_returns, scenario.start, scenario.end),
    }


def stress_test(asset_returns, weights, scenarios=SCENARIOS):
    """One row per scenario for the given portfolio weights."""
    port = metrics.portfolio_returns(asset_returns, weights)
    return pd.DataFrame([run_scenario(port, s) for s in scenarios]).set_index("scenario")


def risk_summary(asset_returns, weights, level=0.95):
    """Full-period risk measures from daily returns."""
    port = metrics.portfolio_returns(asset_returns, weights)
    return {
        "annual_return": metrics.annualised_return(port),
        "annual_volatility": metrics.annualised_volatility(port),
        "var_95_daily": metrics.historical_var(port, level),
        "es_95_daily": metrics.expected_shortfall(port, level),
        "max_drawdown": metrics.max_drawdown(port),
    }


def worst_scenario(stress_table):
    """The scenario with the deepest drawdown, for the client proposal."""
    name = stress_table["max_drawdown"].idxmin()
    return name, stress_table.loc[name]


def format_recovery(days):
    if days is None or pd.isna(days):
        return "Not yet recovered"
    if days < 45:
        return f"{int(days)} days"
    return f"{days / 30.44:.0f} months"


if __name__ == "__main__":
    from riskfit.config import ASSET_ORDER, PROJECT_ROOT
    from riskfit.data.loader import common_sample, load_prices, to_returns
    from riskfit.optimiser.mean_variance import build_all_profiles, market_inputs
    from riskfit.report.charts import plot_rolling_correlation, plot_scenario_paths
    from riskfit.risk_profile.profiles import PROFILES

    prices = load_prices()
    daily = to_returns(common_sample(prices[ASSET_ORDER]), "D")
    mu, cov = market_inputs(prices)
    portfolios = {PROFILES[lvl].name: p.weights for lvl, p in build_all_profiles(mu, cov).items()}

    tables = {name: stress_test(daily, weights) for name, weights in portfolios.items()}
    order = [s.name for s in SCENARIOS]
    for column, label in [("total_return", "Return over the crisis (%)"),
                          ("max_drawdown", "Maximum drawdown (%)")]:
        table = pd.DataFrame({name: t[column] for name, t in tables.items()}).T[order]
        print(f"\n{label}\n{(table * 100).round(1).to_string()}")
    recovery = pd.DataFrame({name: t["recovery_days"].map(format_recovery) for name, t in tables.items()}).T[order]
    print(f"\nRecovery time (trough back to previous peak)\n{recovery.to_string()}")

    risk = pd.DataFrame({name: risk_summary(daily, w) for name, w in portfolios.items()}).T
    print(f"\nFull-period risk, daily data 2007-2026 (%)\n{(risk * 100).round(2).to_string()}")

    images = PROJECT_ROOT / "docs" / "images"
    plot_scenario_paths(daily, portfolios).savefig(images / "stress_scenarios.png", dpi=200, bbox_inches="tight")
    monthly = to_returns(prices[["equities", "bonds"]].dropna(), "M")
    corr = metrics.rolling_correlation(monthly["equities"], monthly["bonds"], window=36)
    plot_rolling_correlation(corr).savefig(images / "stock_bond_correlation.png", dpi=200, bbox_inches="tight")
    print(f"Saved charts to {images}")
