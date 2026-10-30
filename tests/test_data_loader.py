"""Tests for the data helpers. They use small hand-made tables, so no internet is needed."""

import numpy as np
import pandas as pd
import pytest

from riskfit.data import loader


def make_prices():
    dates = pd.to_datetime(["2020-01-03", "2020-01-01", "2020-01-02", "2020-01-02", "2020-01-06"])
    return pd.DataFrame(
        {"SPY": [102.0, 100.0, 101.0, 101.5, np.nan], "AGG": [np.nan, 50.0, 50.5, 50.5, 51.0]},
        index=dates,
    )


def test_clean_prices_sorts_dedupes_and_fills_short_gaps():
    clean = loader.clean_prices(make_prices())
    assert clean.index.is_monotonic_increasing
    assert not clean.index.duplicated().any()
    assert clean.loc["2020-01-02", "SPY"] == 101.5         # last duplicate kept
    assert clean.loc["2020-01-03", "AGG"] == 50.5          # one-day gap filled
    assert clean.loc["2020-01-06", "SPY"] == 102.0


def test_clean_prices_does_not_invent_history_before_launch():
    dates = pd.bdate_range("2020-01-01", periods=10)
    prices = pd.DataFrame({"OLD": range(10), "NEW": [np.nan] * 8 + [10.0, 11.0]}, index=dates)
    clean = loader.clean_prices(prices)
    assert clean["NEW"].first_valid_index() == dates[8]


def test_to_returns_daily_and_monthly():
    dates = pd.to_datetime(["2020-01-30", "2020-01-31", "2020-02-28", "2020-03-31"])
    prices = pd.DataFrame({"A": [100.0, 110.0, 99.0, 99.0]}, index=dates)

    daily = loader.to_returns(prices, "D")
    assert daily["A"].tolist() == pytest.approx([0.10, -0.10, 0.0])

    monthly = loader.to_returns(prices, "M")
    assert monthly["A"].tolist() == pytest.approx([-0.10, 0.0])   # Jan-end 110 -> Feb 99 -> Mar 99


def test_to_returns_rejects_unknown_frequency():
    with pytest.raises(ValueError):
        loader.to_returns(make_prices(), "W")


def test_load_prices_uses_cache_and_renames_to_asset_classes(tmp_path, monkeypatch):
    dates = pd.bdate_range("2007-01-01", periods=5)
    fake = pd.DataFrame({t: np.linspace(10, 11, 5) for t in ["SPY", "AGG", "BIL", "GLD"]}, index=dates)
    calls = []

    def fake_download(tickers, start=None, end=None):
        calls.append(tickers)
        return fake[tickers]

    monkeypatch.setattr(loader, "download_prices", fake_download)
    cache = tmp_path / "prices.csv"

    first = loader.load_prices(path=cache)
    second = loader.load_prices(path=cache)          # should read the CSV, not download again

    assert len(calls) == 1
    assert cache.exists()
    assert list(first.columns) == ["equities", "bonds", "cash", "gold"]
    pd.testing.assert_frame_equal(first, second)


def test_availability_report_flags_2008_coverage():
    dates = pd.bdate_range("2007-06-01", "2007-12-31")
    prices = pd.DataFrame({"early": 1.0, "late": np.nan}, index=dates)
    prices.loc["2007-11-01":, "late"] = 1.0
    report = loader.availability_report(prices)
    assert bool(report.loc["early", "covers_2008"]) is True
    assert bool(report.loc["late", "covers_2008"]) is False
