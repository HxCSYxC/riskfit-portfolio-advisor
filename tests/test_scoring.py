import pytest

from riskfit.risk_profile.questionnaire import (
    TOLERANCE_QUESTIONS,
    score_client,
    tolerance_level_from_score,
)

LONG_HORIZON = 4   # more than 10 years -> no cap
BIG_LOSS_OK = 4    # more than 30% -> no cap
NO_LIQUIDITY = 0


def same_answer(index):
    return {qid: index for qid in TOLERANCE_QUESTIONS}


@pytest.mark.parametrize("index, expected_level", [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)])
def test_uniform_answers_map_to_each_level(index, expected_level):
    result = score_client(same_answer(index), LONG_HORIZON, BIG_LOSS_OK, NO_LIQUIDITY)
    assert result.tolerance_score == 5 * (index + 1)
    assert result.final_level == expected_level


@pytest.mark.parametrize("score, level", [
    (5, 1), (8, 1), (9, 2), (12, 2), (13, 3), (16, 3), (17, 4), (20, 4), (21, 5), (25, 5),
])
def test_band_edges(score, level):
    assert tolerance_level_from_score(score) == level


@pytest.mark.parametrize("bad_score", [4, 26])
def test_score_out_of_range_raises(bad_score):
    with pytest.raises(ValueError):
        tolerance_level_from_score(bad_score)


def test_short_horizon_caps_aggressive_client():
    result = score_client(same_answer(4), horizon=1, max_loss=BIG_LOSS_OK, liquidity=NO_LIQUIDITY)
    assert result.tolerance_level == 5
    assert result.final_level == 2
    assert result.profile.name == "Moderately Conservative"
    assert any("horizon" in reason for reason in result.reasons)


def test_loss_limit_caps_profile():
    result = score_client(same_answer(4), LONG_HORIZON, max_loss=2, liquidity=NO_LIQUIDITY)
    assert result.final_level == 3
    assert any("maximum loss" in reason for reason in result.reasons)


def test_final_level_is_lowest_of_tolerance_and_caps():
    result = score_client(same_answer(3), horizon=2, max_loss=1, liquidity=NO_LIQUIDITY)
    assert result.final_level == min(result.tolerance_level, result.horizon_cap, result.loss_cap) == 2


def test_caps_do_not_raise_a_cautious_client():
    result = score_client(same_answer(0), LONG_HORIZON, BIG_LOSS_OK, NO_LIQUIDITY)
    assert result.final_level == 1


@pytest.mark.parametrize("liquidity, min_cash", [(0, 0.0), (1, 0.10), (2, 0.20)])
def test_liquidity_sets_min_cash_without_changing_profile(liquidity, min_cash):
    result = score_client(same_answer(2), LONG_HORIZON, BIG_LOSS_OK, liquidity)
    assert result.min_cash == min_cash
    assert result.final_level == 3


def test_missing_answer_raises():
    answers = same_answer(2)
    del answers["reaction"]
    with pytest.raises(ValueError, match="Missing"):
        score_client(answers, LONG_HORIZON, BIG_LOSS_OK, NO_LIQUIDITY)


@pytest.mark.parametrize("bad_index", [-1, 5, "2", 2.0])
def test_invalid_option_raises(bad_index):
    answers = same_answer(2)
    answers["objective"] = bad_index
    with pytest.raises(ValueError):
        score_client(answers, LONG_HORIZON, BIG_LOSS_OK, NO_LIQUIDITY)


def test_invalid_capacity_option_raises():
    with pytest.raises(ValueError):
        score_client(same_answer(2), horizon=9, max_loss=BIG_LOSS_OK, liquidity=NO_LIQUIDITY)
