"""Page 1: the relationship manager enters the client's answers."""

import pandas as pd
import streamlit as st

from common import EXAMPLES_DIR, PAGES, get_prices
from riskfit.proposal import Client, build_proposal
from riskfit.risk_profile.profiles import PROFILES
from riskfit.risk_profile.questionnaire import (
    HORIZON_OPTIONS,
    LIQUIDITY_OPTIONS,
    MAX_LOSS_OPTIONS,
    TOLERANCE_QUESTIONS,
)

st.title("Client Questionnaire")
st.write("Enter the client's answers. RiskFit scores their **attitude to risk** (willingness) and their "
         "**ability to take risk** (horizon and maximum loss), and uses the **lower** of the two.")

examples = {"Blank form": None}
for path in sorted(EXAMPLES_DIR.glob("*.json")):
    examples[f"Example: {Client.from_json(path).name}"] = path
proposal = st.session_state.get("proposal")
if proposal is not None:
    st.success(f"Current client: **{proposal.client.name}**, scored as **{proposal.profile.profile.name}**. "
               "See the result at the bottom of this page, or edit the answers and score again.")

choice = st.selectbox("Start from a blank form or load a fictional example client", list(examples))
base = Client.from_json(examples[choice]) if examples[choice] else None
if base and base.notes:
    st.caption(f"Example notes: {base.notes}")


def option_radio(label, options, default, key):
    """Radio button that returns the chosen option's index (or None if nothing is chosen yet)."""
    return st.radio(label, range(len(options)), format_func=lambda i: options[i], index=default, key=key)


form_key = f"form_{choice}"   # a new key per example, so loading an example resets the form
with st.form(form_key):
    st.subheader("Client details")
    c1, c2, c3 = st.columns(3)
    name = c1.text_input("Client name", value=base.name if base else "")
    age = c2.number_input("Age", min_value=18, max_value=100, value=base.age if base else 45)
    amount = c3.number_input("Amount to invest (USD)", min_value=10_000, step=50_000,
                             value=int(base.investment_amount) if base else 1_000_000)

    part_a, part_b = st.columns(2, gap="large")
    with part_a:
        st.subheader("Part A: Attitude to risk")
        answers = {}
        for qid, question in TOLERANCE_QUESTIONS.items():
            answers[qid] = option_radio(question["text"], question["options"],
                                        base.answers[qid] if base else None, f"{form_key}_{qid}")

    with part_b:
        st.subheader("Part B: Ability to take risk")
        horizon = option_radio("How long can this money stay invested?", [o[0] for o in HORIZON_OPTIONS],
                               base.horizon if base else None, f"{form_key}_horizon")
        max_loss = option_radio("What is the largest fall in value you could accept without needing to sell?",
                                [o[0] for o in MAX_LOSS_OPTIONS], base.max_loss if base else None,
                                f"{form_key}_max_loss")
        liquidity = option_radio("Will you need to withdraw money soon?", [o[0] for o in LIQUIDITY_OPTIONS],
                                 base.liquidity if base else None, f"{form_key}_liquidity")

    submitted = st.form_submit_button("Score client and build portfolio", type="primary")

if submitted:
    missing = [qid for qid, a in answers.items() if a is None]
    missing += [n for n, v in [("horizon", horizon), ("max loss", max_loss), ("liquidity", liquidity)] if v is None]
    if not name.strip():
        st.error("Please enter the client's name.")
    elif missing:
        st.error("Please answer every question before scoring.")
    else:
        client = Client(name=name.strip(), age=int(age), investment_amount=float(amount), answers=answers,
                        horizon=horizon, max_loss=max_loss, liquidity=liquidity, notes=base.notes if base else "")
        with st.spinner("Scoring the client, optimising the portfolio and running stress tests..."):
            st.session_state["proposal"] = build_proposal(client, get_prices())
        st.rerun()   # refresh so the sidebar shows the new client

if proposal is not None:
    p = proposal.profile
    st.divider()
    st.subheader(f"Result for {proposal.client.name}: {p.profile.name}")
    st.write(p.profile.description)

    decision = pd.DataFrame([
        {"Factor": "Attitude to risk (Part A)", "Answer": f"Score {p.tolerance_score} of 25",
         "Highest level allowed": PROFILES[p.tolerance_level].name},
        {"Factor": "Investment horizon", "Answer": p.horizon, "Highest level allowed": PROFILES[p.horizon_cap].name},
        {"Factor": "Largest acceptable loss", "Answer": p.max_loss,
         "Highest level allowed": PROFILES[p.loss_cap].name},
        {"Factor": "Final profile (the lowest of the above)", "Answer": "",
         "Highest level allowed": p.profile.name},
    ])
    st.dataframe(decision, hide_index=True)
    for reason in p.reasons:
        st.markdown(f"- {reason}")
    st.page_link(PAGES["portfolio"], label="See the recommended portfolio", icon=":material/arrow_forward:")
