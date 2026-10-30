import numpy as np
import pandas as pd
import pytest

from riskfit.optimiser.frontier import efficient_frontier
from riskfit.optimiser.mean_variance import (
    build_all_profiles,
    build_profile_portfolio,
    estimate_covariance,
    market_inputs,
    max_return_portfolio,
    min_variance_portfolio,
    portfolio_stats,
    profile_bounds,
)
from riskfit.risk_profile.profiles import PROFILES

ASSETS = ["equities", "bonds", "cash", "gold"]
TOL = 1e-6


@pytest.fixture
def toy_inputs():
    """Small, hand-made inputs so the tests do not depend on market data."""
    mu = pd.Series([0.07, 0.04, 0.03, 0.035], index=ASSETS)
    vols = np.array([0.16, 0.05, 0.005, 0.17])
    corr = np.array([
        [1.0, 0.2, 0.0, 0.1],
        [0.2, 1.0, 0.0, 0.3],
        [0.0, 0.0, 1.0, 0.1],
        [0.1, 0.3, 0.1, 1.0],
    ])
    cov = pd.DataFrame(corr * np.outer(vols, vols), index=ASSETS, columns=ASSETS)
    return mu, cov


def assert_valid_weights(weights, bounds):
    assert weights.sum() == pytest.approx(1.0, abs=TOL)
    for w, (low, high) in zip(weights, bounds):
        assert low - TOL <= w <= high + TOL


@pytest.mark.parametrize("level", list(PROFILES))
def test_profile_weights_sum_to_one_and_respect_limits(toy_inputs, level):
    mu, cov = toy_inputs
    profile = PROFILES[level]
    result = build_profile_portfolio(profile, mu, cov)
    assert_valid_weights(result.weights, profile_bounds(profile))


@pytest.mark.parametrize("level", list(PROFILES))
def test_volatility_target_is_respected(toy_inputs, level):
    mu, cov = toy_inputs
    result = build_profile_portfolio(PROFILES[level], mu, cov)
    assert result.target_met
    assert result.volatility <= PROFILES[level].target_volatility + TOL


@pytest.mark.parametrize("min_cash", [0.10, 0.20])
@pytest.mark.parametrize("level", list(PROFILES))
def test_liquidity_needs_raise_cash(toy_inputs, level, min_cash):
    mu, cov = toy_inputs
    result = build_profile_portfolio(PROFILES[level], mu, cov, min_cash=min_cash)
    assert result.weights["cash"] >= min_cash - TOL
    assert result.weights.sum() == pytest.approx(1.0, abs=TOL)


def test_profile_bounds_lift_cash_cap_when_needed():
    # Aggressive allows at most 15% cash; a 20% liquidity need must still fit.
    bounds = profile_bounds(PROFILES[5], min_cash=0.20)
    assert bounds[ASSETS.index("cash")] == (0.20, 0.20)


def test_higher_profiles_take_more_risk_and_expect_more_return(toy_inputs):
    mu, cov = toy_inputs
    results = build_all_profiles(mu, cov)
    vols = [results[level].volatility for level in sorted(results)]
    rets = [results[level].expected_return for level in sorted(results)]
    assert vols == sorted(vols)
    assert rets == sorted(rets)


def test_unreachable_target_falls_back_to_min_variance(toy_inputs):
    mu, cov = toy_inputs
    bounds = [(0.5, 1.0), (0.0, 0.5), (0.0, 0.5), (0.0, 0.5)]   # at least 50% equities
    result = max_return_portfolio(mu, cov, target_vol=0.01, bounds=bounds)
    assert not result.target_met
    np.testing.assert_allclose(result.weights.values, min_variance_portfolio(cov, bounds), atol=1e-6)


def test_impossible_bounds_raise(toy_inputs):
    mu, cov = toy_inputs
    with pytest.raises(ValueError):
        max_return_portfolio(mu, cov, 0.10, [(0.4, 1.0)] * 4)   # minimums add up to 160%


def test_portfolio_stats_matches_hand_calculation(toy_inputs):
    mu, cov = toy_inputs
    w = np.array([0.5, 0.5, 0.0, 0.0])
    ret, vol = portfolio_stats(w, mu, cov)
    # 0.5*7% + 0.5*4% ; var = 0.25*0.16^2 + 0.25*0.05^2 + 2*0.25*0.2*0.16*0.05
    assert ret == pytest.approx(0.055)
    assert vol == pytest.approx(np.sqrt(0.25 * 0.0256 + 0.25 * 0.0025 + 2 * 0.25 * 0.2 * 0.16 * 0.05))


def test_covariance_keeps_volatilities_and_shrinks_correlation():
    rng = np.random.default_rng(0)
    returns = pd.DataFrame(rng.normal(size=(120, 2)) * [0.04, 0.01], columns=["a", "b"])
    returns["b"] += 0.2 * returns["a"]          # build in some correlation
    cov = estimate_covariance(returns)
    sample_vol = returns.std() * np.sqrt(12)
    np.testing.assert_allclose(np.sqrt(np.diag(cov)), sample_vol, rtol=1e-10)
    shrunk_corr = cov.iloc[0, 1] / np.sqrt(cov.iloc[0, 0] * cov.iloc[1, 1])
    assert 0 < shrunk_corr < returns.corr().iloc[0, 1]


def test_frontier_is_increasing_and_valid(toy_inputs):
    mu, cov = toy_inputs
    frontier = efficient_frontier(mu, cov, n_points=15)
    assert len(frontier) == 15
    assert frontier["expected_return"].is_monotonic_increasing
    assert frontier["volatility"].is_monotonic_increasing
    np.testing.assert_allclose(frontier[ASSETS].sum(axis=1), 1.0, atol=TOL)
    assert (frontier[ASSETS] >= -TOL).all().all()


def test_profiles_on_real_data_are_valid():
    """End-to-end check on the cached market data (skipped if the cache is missing)."""
    try:
        mu, cov = market_inputs()
    except Exception:
        pytest.skip("price cache not available")
    for level, result in build_all_profiles(mu, cov).items():
        assert_valid_weights(result.weights, profile_bounds(PROFILES[level]))
        assert result.target_met
