import numpy as np
import pandas as pd
import pytest

from riskfit.stress_test import metrics
from riskfit.stress_test.scenarios import SCENARIOS, Scenario, format_recovery, stress_test, worst_scenario


def series(values, start="2020-01-01"):
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)), dtype=float)


def test_total_return_compounds():
    assert metrics.total_return(series([0.10, -0.10])) == pytest.approx(1.1 * 0.9 - 1)   # -1%, not 0%


def test_max_drawdown_hand_example():
    # 100 -> 120 -> 90 -> 108: worst fall is from 120 to 90 = -25%
    r = series([0.20, -0.25, 0.20])
    assert metrics.max_drawdown(r) == pytest.approx(-0.25)


def test_max_drawdown_counts_a_fall_on_the_first_day():
    assert metrics.max_drawdown(series([-0.10, 0.05])) == pytest.approx(-0.10)


def test_max_drawdown_is_zero_when_only_rising():
    assert metrics.max_drawdown(series([0.01, 0.02, 0.00])) == 0.0


def test_recovery_days_hand_example():
    # Wealth: 1.00 -> 0.90 (Wed 1 Jan) -> 0.80 trough (Thu 2 Jan) -> 0.88 -> 0.968 -> 1.007 (Tue 7 Jan)
    r = series([-0.10, -0.111111, 0.10, 0.10, 0.04, 0.01])
    days = metrics.recovery_days(r, start=r.index[0], end=r.index[2])
    assert days == 5   # calendar days from the trough (2 Jan) to back above 1.00 (7 Jan)


def test_recovery_days_none_if_never_recovered():
    r = series([-0.20, 0.01, 0.01])
    assert metrics.recovery_days(r, r.index[0], r.index[1]) is None


def test_portfolio_returns_is_weighted_sum():
    assets = pd.DataFrame({"a": [0.10, -0.05], "b": [0.00, 0.05]}, index=pd.bdate_range("2020-01-01", periods=2))
    port = metrics.portfolio_returns(assets, {"a": 0.6, "b": 0.4})
    assert port.tolist() == pytest.approx([0.06, -0.01])


def test_var_and_expected_shortfall_on_known_data():
    # Returns -10%, -9%, ..., +9% (20 values). The worst 5% is one day: -10%.
    r = series(np.arange(-10, 10) / 100)
    var = metrics.historical_var(r, 0.95)
    assert -0.10 <= var <= -0.09
    assert metrics.expected_shortfall(r, 0.95) <= var          # ES is at least as bad as VaR
    assert metrics.expected_shortfall(r, 0.95) == pytest.approx(-0.10)


def test_annualised_volatility_scales_with_sqrt_time():
    r = series([0.01, -0.01] * 50)
    assert metrics.annualised_volatility(r) == pytest.approx(r.std() * np.sqrt(252))


def test_rolling_correlation_of_identical_series_is_one():
    a = series(np.random.default_rng(1).normal(size=60))
    corr = metrics.rolling_correlation(a, a, window=36)
    assert len(corr) == 60 - 35
    assert np.allclose(corr, 1.0)


def test_stress_test_uses_scenario_windows():
    dates = pd.bdate_range("2021-12-01", "2023-06-30")
    assets = pd.DataFrame({"x": -0.001, "y": 0.0}, index=dates)
    scenario = Scenario("t", "Test", "2022-01-01", "2022-12-31", "")
    table = stress_test(assets, {"x": 0.5, "y": 0.5}, scenarios=[scenario], rebalance="daily", annual_fee=0.0)
    row = table.loc["Test"]
    n_days = len(dates[(dates >= "2022-01-01") & (dates <= "2022-12-31")])
    assert row.total_return == pytest.approx(0.9995 ** n_days - 1)
    assert row.max_drawdown == pytest.approx(row.total_return)   # steady decline: drawdown = return
    assert row.recovery_days is None or np.isnan(row.recovery_days)
    assert worst_scenario(table)[0] == "Test"


@pytest.mark.parametrize("days, text", [(None, "Not yet recovered"), (20, "20 days"), (365, "12 months")])
def test_format_recovery(days, text):
    assert format_recovery(days) == text


def test_quarterly_rebalancing_lets_weights_drift():
    # Asset a doubles on day 1, then both assets gain 10% on day 2 (same quarter, so no rebalance).
    assets = pd.DataFrame({"a": [1.0, 0.10], "b": [0.0, 0.10]}, index=pd.to_datetime(["2020-01-02", "2020-01-03"]))
    drift = metrics.portfolio_returns(assets, {"a": 0.5, "b": 0.5}, rebalance="quarterly")
    assert drift.tolist() == pytest.approx([0.5, 0.10])

    # If only a gains on day 2, the drifted weight of a (1.0 / 1.5 = 2/3) matters:
    assets.iloc[1] = [0.30, 0.0]
    drift = metrics.portfolio_returns(assets, {"a": 0.5, "b": 0.5}, rebalance="quarterly")
    daily = metrics.portfolio_returns(assets, {"a": 0.5, "b": 0.5}, rebalance="daily")
    assert drift.iloc[1] == pytest.approx(0.30 * 2 / 3)
    assert daily.iloc[1] == pytest.approx(0.30 * 0.5)


def test_quarterly_rebalancing_resets_weights_in_a_new_quarter():
    assets = pd.DataFrame({"a": [1.0, 0.30], "b": [0.0, 0.0]}, index=pd.to_datetime(["2020-03-31", "2020-04-01"]))
    port = metrics.portfolio_returns(assets, {"a": 0.5, "b": 0.5}, rebalance="quarterly")
    assert port.iloc[1] == pytest.approx(0.30 * 0.5)       # back at 50/50 on the first day of Q2


def test_annual_fee_is_spread_over_trading_days():
    assets = pd.DataFrame({"a": [0.0] * 252}, index=pd.bdate_range("2021-01-01", periods=252))
    port = metrics.portfolio_returns(assets, {"a": 1.0}, annual_fee=0.01)
    assert port.sum() == pytest.approx(-0.01)
    assert metrics.total_return(port) == pytest.approx(-0.00995, abs=1e-4)


def test_unknown_rebalance_rule_raises():
    assets = pd.DataFrame({"a": [0.0]}, index=pd.bdate_range("2021-01-01", periods=1))
    with pytest.raises(ValueError):
        metrics.portfolio_returns(assets, {"a": 1.0}, rebalance="monthly")


def test_hypothetical_shock_is_weighted_sum():
    from riskfit.stress_test.hypothetical import Shock, hypothetical_test

    shock = Shock("t", "Test", {"equities": -0.30, "bonds": -0.10, "cash": 0.0, "gold": 0.15}, "")
    weights = {"equities": 0.5, "bonds": 0.4, "cash": 0.05, "gold": 0.05}
    table = hypothetical_test(weights, [shock])
    assert table.loc["Test", "portfolio_return"] == pytest.approx(-0.15 - 0.04 + 0.0075)


def test_hypothetical_scenarios_hurt_riskier_profiles_more_in_a_recession():
    from riskfit.stress_test.hypothetical import hypothetical_test

    cautious = hypothetical_test({"equities": 0.2, "bonds": 0.4, "cash": 0.35, "gold": 0.05})
    bold = hypothetical_test({"equities": 0.9, "bonds": 0.05, "cash": 0.0, "gold": 0.05})
    assert bold.loc["Severe recession", "portfolio_return"] < cautious.loc["Severe recession", "portfolio_return"]
    assert len(cautious) == 3


@pytest.mark.parametrize("equity_style", ["global", "hk_tilt"])
def test_profiles_stay_within_their_loss_limits(equity_style):
    """Calibration check on real data: each profile's worst crisis drawdown must fit its loss limit.

    Uses the default costs (1% fee, quarterly rebalancing) and both equity styles.
    """
    from riskfit.config import ASSET_ORDER
    from riskfit.data.loader import common_sample, load_prices, to_returns
    from riskfit.optimiser.mean_variance import build_all_profiles, market_inputs
    from riskfit.risk_profile.profiles import PROFILES

    try:
        prices = load_prices(equity_style)
    except Exception:
        pytest.skip("price cache not available")
    daily = to_returns(common_sample(prices[ASSET_ORDER]), "D")
    mu, cov = market_inputs(prices)
    for level, portfolio in build_all_profiles(mu, cov).items():
        worst = stress_test(daily, portfolio.weights, SCENARIOS)["max_drawdown"].min()
        assert -worst <= PROFILES[level].loss_limit
