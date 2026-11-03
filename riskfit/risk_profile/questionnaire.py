"""Risk-profiling questionnaire and scoring.

Two ideas from private banking practice:

1. Risk TOLERANCE (willingness): how much risk the client is comfortable with.
   Measured by five questions, each scored 1-5 points (total 5-25).
2. Risk CAPACITY (ability): how much risk the client can afford to take.
   Set by investment horizon and maximum acceptable loss. Each one caps the profile.

Final profile = the LOWEST of tolerance, horizon cap and loss cap.
A client who wants high risk but needs the money in two years still gets a low-risk profile.

Liquidity needs do not change the profile. They set a minimum cash holding instead.
"""

from dataclasses import dataclass, field

from riskfit.risk_profile.profiles import RiskProfile, get_profile

# Tolerance questions. The answer at position i scores i + 1 points.
TOLERANCE_QUESTIONS = {
    "objective": {
        "text": "What is your main goal for this investment?",
        "options": [
            "Protect my capital",
            "Earn steady income",
            "A balance of income and growth",
            "Grow my wealth over time",
            "Grow my wealth as much as possible",
        ],
    },
    "experience": {
        "text": "Which investments have you held before?",
        "options": [
            "None, or bank deposits only",
            "Bonds or money-market funds",
            "Mixed or multi-asset funds",
            "Individual stocks or equity funds",
            "Leveraged products, options or other derivatives",
        ],
    },
    "reaction": {
        "text": "Your portfolio falls 20% in a few months. What would you do?",
        "options": [
            "Sell everything",
            "Sell some to limit further losses",
            "Do nothing and wait",
            "Invest a little more",
            "Invest a lot more while prices are low",
        ],
    },
    "trade_off": {
        "text": "Which range of one-year outcomes would you choose (worst year / best year)?",
        "options": [
            "-1% / +3%",
            "-5% / +6%",
            "-12% / +10%",
            "-20% / +15%",
            "-30% / +22%",
        ],
    },
    "volatility_comfort": {
        "text": "'I accept large short-term swings in value for higher long-term returns.'",
        "options": [
            "Strongly disagree",
            "Disagree",
            "Neutral",
            "Agree",
            "Strongly agree",
        ],
    },
}

# Capacity questions. Each option gives the highest risk level allowed (the "cap").
HORIZON_OPTIONS = [
    ("Less than 1 year", 1),
    ("1 to 3 years", 2),
    ("3 to 5 years", 3),
    ("5 to 10 years", 4),
    ("More than 10 years", 5),
]

# The bands match each profile's loss_limit, so the client's answer is consistent
# with how that profile actually behaved in the historical stress tests.
MAX_LOSS_OPTIONS = [
    ("Up to 15%", 1),
    ("Up to 25%", 2),
    ("Up to 35%", 3),
    ("Up to 45%", 4),
    ("More than 45%", 5),
]

# Liquidity needs set a minimum cash weight instead of capping the profile.
LIQUIDITY_OPTIONS = [
    ("No withdrawals planned in the next 12 months", 0.00),
    ("May withdraw up to 10% in the next 12 months", 0.10),
    ("May withdraw more than 10% in the next 12 months", 0.20),
]

# Upper bound of the tolerance score for levels 1-4. Scores above 20 are level 5.
TOLERANCE_BANDS = [8, 12, 16, 20]


@dataclass
class ProfileResult:
    tolerance_score: int
    tolerance_level: int
    horizon_cap: int
    loss_cap: int
    final_level: int
    profile: RiskProfile
    min_cash: float
    horizon: str
    max_loss: str
    liquidity: str
    reasons: list = field(default_factory=list)


def tolerance_level_from_score(score):
    """Map a tolerance score (5-25) to a risk level (1-5)."""
    min_score = len(TOLERANCE_QUESTIONS)
    max_score = 5 * len(TOLERANCE_QUESTIONS)
    if not min_score <= score <= max_score:
        raise ValueError(f"Tolerance score must be {min_score}-{max_score}, got {score}")
    for level, upper in enumerate(TOLERANCE_BANDS, start=1):
        if score <= upper:
            return level
    return 5


def _check_index(name, index, n_options):
    if not isinstance(index, int) or not 0 <= index < n_options:
        raise ValueError(f"Answer for '{name}' must be an option number 0-{n_options - 1}, got {index!r}")


def score_client(answers, horizon, max_loss, liquidity):
    """Score a client.

    answers:   dict of question id -> chosen option index (0-4) for each tolerance question
    horizon:   option index into HORIZON_OPTIONS
    max_loss:  option index into MAX_LOSS_OPTIONS
    liquidity: option index into LIQUIDITY_OPTIONS
    """
    missing = set(TOLERANCE_QUESTIONS) - set(answers)
    if missing:
        raise ValueError(f"Missing answers for: {sorted(missing)}")
    for qid, index in answers.items():
        if qid not in TOLERANCE_QUESTIONS:
            raise ValueError(f"Unknown question: {qid}")
        _check_index(qid, index, len(TOLERANCE_QUESTIONS[qid]["options"]))
    _check_index("horizon", horizon, len(HORIZON_OPTIONS))
    _check_index("max_loss", max_loss, len(MAX_LOSS_OPTIONS))
    _check_index("liquidity", liquidity, len(LIQUIDITY_OPTIONS))

    tolerance_score = sum(index + 1 for index in answers.values())
    tolerance_level = tolerance_level_from_score(tolerance_score)
    horizon_label, horizon_cap = HORIZON_OPTIONS[horizon]
    loss_label, loss_cap = MAX_LOSS_OPTIONS[max_loss]
    liquidity_label, min_cash = LIQUIDITY_OPTIONS[liquidity]

    final_level = min(tolerance_level, horizon_cap, loss_cap)

    # Explain in plain English which factor decided the profile.
    tolerance_name = get_profile(tolerance_level).name
    final_name = get_profile(final_level).name
    reasons = [f"Your attitude to risk (score {tolerance_score} out of 25) points to {tolerance_name}."]
    if horizon_cap < tolerance_level and horizon_cap == final_level:
        reasons.append(f"Your investment horizon ({horizon_label.lower()}) limits the profile to {final_name}, "
                       "because there may not be time to recover from a large fall.")
    if loss_cap < tolerance_level and loss_cap == final_level:
        reasons.append(f"The maximum loss you can accept ({loss_label.lower()}) limits the profile to {final_name}.")
    if min_cash > 0:
        reasons.append(f"Because you may need to withdraw money, at least {min_cash:.0%} is kept in cash.")

    return ProfileResult(
        tolerance_score=tolerance_score,
        tolerance_level=tolerance_level,
        horizon_cap=horizon_cap,
        loss_cap=loss_cap,
        final_level=final_level,
        profile=get_profile(final_level),
        min_cash=min_cash,
        horizon=horizon_label,
        max_loss=loss_label,
        liquidity=liquidity_label,
        reasons=reasons,
    )
