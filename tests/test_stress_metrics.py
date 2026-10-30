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
    table = stress_test(assets, {"x": 0.5, "y": 0.5}, scenarios=[scenario])
    row = table.loc["Test"]
    n_days = len(dates[(dates >= "2022-01-01") & (dates <= "2022-12-31")])
    assert row.total_return == pytest.approx(0.9995 ** n_days - 1)
    assert row.max_drawdown == pytest.approx(row.total_return)   # steady decline: drawdown = return
    assert row.recovery_days is None or np.isnan(row.recovery_days)
    assert worst_scenario(table)[0] == "Test"


@pytest.mark.parametrize("days, text", [(None, "Not yet recovered"), (20, "20 days"), (365, "12 months")])
def test_format_recovery(days, text):
    assert format_recovery(days) == text


def test_profiles_stay_within_their_loss_limits():
    """Calibration check on real data: each profile's worst crisis drawdown must fit its loss limit."""
    from riskfit.config import ASSET_ORDER
    from riskfit.data.loader import common_sample, load_prices, to_returns
    from riskfit.optimiser.mean_variance import build_all_profiles, market_inputs
    from riskfit.risk_profile.profiles import PROFILES

    try:
        prices = load_prices()
    except Exception:
        pytest.skip("price cache not available")
    daily = to_returns(common_sample(prices[ASSET_ORDER]), "D")
    mu, cov = market_inputs(prices)
    for level, portfolio in build_all_profiles(mu, cov).items():
        worst = stress_test(daily, portfolio.weights, SCENARIOS)["max_drawdown"].min()
        assert -worst <= PROFILES[level].loss_limit
