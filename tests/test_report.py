"""Tests for the proposal builder and the one-page PDF (they need the cached price data)."""

from io import BytesIO

import pytest
from pypdf import PdfReader

from riskfit.config import PROJECT_ROOT
from riskfit.proposal import Client, build_proposal, explain_allocation, pct
from riskfit.report.pdf import _usd, build_pdf

EXAMPLES = sorted((PROJECT_ROOT / "examples").glob("*.json"))


@pytest.fixture(scope="module")
def prices():
    from riskfit.data.loader import load_prices
    try:
        return load_prices()
    except Exception:
        pytest.skip("price cache not available")


def test_there_are_three_example_clients():
    assert len(EXAMPLES) == 3


def test_client_json_round_trip(tmp_path):
    client = Client.from_json(EXAMPLES[0])
    client.to_json(tmp_path / "c.json")
    assert Client.from_json(tmp_path / "c.json") == client


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_example_pdf_is_one_page_with_key_content(path, prices):
    proposal = build_proposal(Client.from_json(path), prices)
    buffer = BytesIO()
    build_pdf(proposal, buffer)
    reader = PdfReader(BytesIO(buffer.getvalue()))
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    for expected in [proposal.client.name, proposal.profile.profile.name, "Not investment advice",
                     "Global Financial Crisis", "Why this mix suits you"]:
        assert expected in text


def test_explanation_mentions_profile_and_worst_loss(prices):
    proposal = build_proposal(Client.from_json(EXAMPLES[0]), prices)
    text = " ".join(explain_allocation(proposal))
    assert proposal.profile.profile.name in text
    assert f"{-proposal.worst[1].max_drawdown:.0%}" in text


def test_liquidity_need_shows_up_in_portfolio(prices):
    # Example 3 may withdraw more than 10% next year, so at least 20% is kept in cash.
    proposal = build_proposal(Client.from_json(EXAMPLES[2]), prices)
    assert proposal.portfolio.weights["cash"] >= 0.20 - 1e-6


@pytest.mark.parametrize("amount, round_to, text", [
    (1_500_000, 1, "USD 1,500,000"),
    (824_684.2, 1000, "USD 825,000"),
    (-471_229, 1000, "-USD 471,000"),
])
def test_usd_formatting(amount, round_to, text):
    assert _usd(amount, round_to) == text


@pytest.mark.parametrize("x, signed, text", [(-0.003, True, "0%"), (0.087, True, "+9%"), (-0.06, False, "-6%")])
def test_pct_never_shows_minus_zero(x, signed, text):
    assert pct(x, signed) == text
