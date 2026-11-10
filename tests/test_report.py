"""Tests for the proposal builder and the one-page PDF (they need the cached price data)."""

from io import BytesIO

import pytest
from pypdf import PdfReader

from riskfit.config import PROJECT_ROOT
from riskfit.proposal import Client, build_proposal, explain_allocation, format_money, pct
from riskfit.report.pdf import build_pdf

EXAMPLES = sorted((PROJECT_ROOT / "examples").glob("*.json"))


@pytest.fixture(scope="module")
def proposals():
    """One proposal per example client (built once, as they need the cached price data)."""
    if not (PROJECT_ROOT / "riskfit" / "data" / "cache" / "prices.csv").exists():
        pytest.skip("price cache not available")
    return {path.stem: build_proposal(Client.from_json(path)) for path in EXAMPLES}


def test_there_are_three_example_clients():
    assert len(EXAMPLES) == 3


def test_client_json_round_trip(tmp_path):
    client = Client.from_json(EXAMPLES[0])
    client.to_json(tmp_path / "c.json")
    assert Client.from_json(tmp_path / "c.json") == client


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_example_pdf_is_one_page_with_key_content(path, proposals):
    proposal = proposals[path.stem]
    buffer = BytesIO()
    build_pdf(proposal, buffer)
    reader = PdfReader(BytesIO(buffer.getvalue()))
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    for expected in [proposal.client.name, proposal.profile.profile.name, "Not investment advice",
                     "Global Financial Crisis", "Why this mix suits you", "What if?",
                     proposal.money(proposal.client.investment_amount)]:
        assert expected in text


def test_explanation_mentions_profile_and_worst_loss(proposals):
    proposal = proposals[EXAMPLES[0].stem]
    text = " ".join(explain_allocation(proposal))
    assert proposal.profile.profile.name in text
    assert f"{-proposal.worst[1].max_drawdown:.0%}" in text


def test_liquidity_need_shows_up_in_portfolio(proposals):
    # Example 3 may withdraw more than 10% next year, so at least 20% is kept in cash.
    assert proposals[EXAMPLES[2].stem].portfolio.weights["cash"] >= 0.20 - 1e-6


def test_hkd_client_sees_hkd_amounts(proposals):
    proposal = proposals[EXAMPLES[0].stem]
    assert proposal.client.currency == "HKD"
    assert proposal.money(1_234_567, 1000) == "HKD 1,235,000"


def test_hk_tilt_client_gets_a_different_equity_series(proposals):
    tilted = proposals[EXAMPLES[1].stem]
    plain = proposals[EXAMPLES[0].stem]
    assert tilted.client.equity_style == "hk_tilt"
    assert not tilted.asset_returns["equities"].equals(plain.asset_returns["equities"])
    assert "Hong Kong" in " ".join(explain_allocation(tilted))


def test_expected_return_is_shown_after_fees(proposals):
    proposal = proposals[EXAMPLES[0].stem]
    assert proposal.expected_return_net == pytest.approx(proposal.portfolio.expected_return - 0.01)
    low, high = proposal.typical_range
    assert (low + high) / 2 == pytest.approx(proposal.expected_return_net)


@pytest.mark.parametrize("amount, currency, round_to, text", [
    (1_500_000, "USD", 1, "USD 1,500,000"),
    (824_684.2, "USD", 1000, "USD 825,000"),
    (-471_229, "HKD", 1000, "-HKD 471,000"),
])
def test_money_formatting(amount, currency, round_to, text):
    assert format_money(amount, currency, round_to) == text


@pytest.mark.parametrize("x, signed, text", [(-0.003, True, "0%"), (0.087, True, "+9%"), (-0.06, False, "-6%")])
def test_pct_never_shows_minus_zero(x, signed, text):
    assert pct(x, signed) == text
