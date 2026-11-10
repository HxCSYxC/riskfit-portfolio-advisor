"""Page 3: historical crises, risk measures, and the stock-bond correlation story."""

import pandas as pd
import streamlit as st

from common import PAGES, get_prices, get_profile_portfolios, require_proposal, show_figure
from riskfit.config import ASSET_LABELS, ASSET_ORDER
from riskfit.data.loader import to_returns
from riskfit.report.charts import plot_rolling_correlation, plot_scenario_paths
from riskfit.risk_profile.profiles import PROFILES
from riskfit.stress_test.hypothetical import HYPOTHETICAL_SCENARIOS
from riskfit.stress_test.metrics import rolling_correlation
from riskfit.stress_test.scenarios import SCENARIOS, format_recovery, stress_test

proposal = require_proposal()
client, portfolio = proposal.client, proposal.portfolio
amount = client.investment_amount

st.title("Stress Tests")
st.write(f"How **{client.name}**'s portfolio would have done if held through three real crises. "
         f"The tests assume {proposal.rebalance} rebalancing and a {proposal.annual_fee:.0%} yearly fee; "
         "taxes are ignored.")

table = pd.DataFrame([
    {"Crisis": name, "Period": f"{r.start:%b %Y} – {r.end:%b %Y}", "Return over the crisis": r.total_return * 100,
     "Largest fall": r.max_drawdown * 100, f"Largest fall in {client.currency}": proposal.money(r.max_drawdown * amount, 1000),
     "Time to recover": format_recovery(r.recovery_days)}
    for name, r in proposal.stress.iterrows()
])
percent = st.column_config.NumberColumn(format="%.1f%%")   # values are already x100
st.dataframe(table, hide_index=True, column_config={"Return over the crisis": percent, "Largest fall": percent})

for scenario in SCENARIOS:
    st.markdown(f"- **{scenario.name}:** {scenario.description}")

show_figure(plot_scenario_paths(proposal.asset_returns,
                                {"Client portfolio": portfolio.weights, "100% shares (for comparison)": {"equities": 1.0}},
                                colours={"Client portfolio": "#1c5cab", "100% shares (for comparison)": "#b9b8b2"},
                                figsize=(12, 3.6), title=None))

st.subheader("What if? Hypothetical shocks")
st.write("History since 2007 does not contain every risk, so these are made-up one-off shocks. "
         "The portfolio's loss is its weights multiplied by the assumed move in each asset class.")
what_if = pd.DataFrame([
    {"Scenario": name, "Portfolio return": r.portfolio_return * 100,
     f"In {client.currency}": proposal.money(r.portfolio_return * amount, 1000),
     **{f"{ASSET_LABELS[a]}": shock.shocks[a] * 100 for a in ASSET_ORDER}}
    for (name, r), shock in zip(proposal.hypothetical.iterrows(), HYPOTHETICAL_SCENARIOS)
])
st.dataframe(what_if, hide_index=True,
             column_config={c: st.column_config.NumberColumn(format="%.0f%%") for c in what_if.columns[1:]
                            if not c.startswith("In ")})
for shock in HYPOTHETICAL_SCENARIOS:
    st.markdown(f"- **{shock.name}:** {shock.description}")

with st.expander("What difference do fees and rebalancing make?"):
    gross = stress_test(proposal.asset_returns, portfolio.weights, rebalance="daily", annual_fee=0.0)
    compare = pd.DataFrame({
        "Crisis": proposal.stress.index,
        "Largest fall: 1% fee, quarterly rebalancing": proposal.stress["max_drawdown"].values * 100,
        "Largest fall: no fee, daily rebalancing": gross["max_drawdown"].values * 100,
        "Recovery: 1% fee, quarterly": [format_recovery(d) for d in proposal.stress["recovery_days"]],
        "Recovery: no fee, daily": [format_recovery(d) for d in gross["recovery_days"]],
    })
    st.dataframe(compare, hide_index=True, column_config={c: percent for c in compare.columns[1:3]})
    st.caption("Fees make every fall slightly deeper and every recovery slower. Quarterly rebalancing lets "
               "the weights drift between rebalancing dates, which is how real portfolios are run.")

st.subheader("Everyday risk measures")
st.caption(f"Daily data from {proposal.data_start:%b %Y} to {proposal.data_end:%b %Y}.")
risk = proposal.risk
c1, c2, c3, c4 = st.columns(4)
c1.metric("Annual volatility (realised)", f"{risk['annual_volatility']:.1%}",
          help="Measured from daily returns. Higher than the optimiser's estimate, because daily data captures "
               "the most turbulent days.")
c2.metric("95% daily VaR", f"{risk['var_95_daily']:.2%}",
          help="On 95% of days the loss was smaller than this.")
c3.metric("95% daily expected shortfall", f"{risk['es_95_daily']:.2%}",
          help="The average loss on the worst 5% of days.")
c4.metric("Worst fall since 2007", f"{risk['max_drawdown']:.1%}")
st.write(f"In money terms, on a typical bad day (1 in 20) this portfolio would lose about "
         f"**{proposal.money(-risk['var_95_daily'] * amount, 100)}**, and on the worst 5% of days about "
         f"**{proposal.money(-risk['es_95_daily'] * amount, 100)}** on average.")

st.subheader("Why 2022 matters: bonds do not always protect a portfolio")
prices = get_prices(client.equity_style)
monthly = to_returns(prices[["equities", "bonds"]].dropna(), "M")
show_figure(plot_rolling_correlation(rolling_correlation(monthly["equities"], monthly["bonds"], window=36)))
st.markdown(
    "Usually, when shares fall it is because the economy is weakening. Central banks then cut interest rates, "
    "which pushes bond prices **up**, so bonds cushion the fall. That is the idea behind a balanced portfolio, "
    "and why the correlation between shares and bonds was mostly below zero in the 2010s.\n\n"
    "In 2022 the problem was **inflation**. Central banks raised rates quickly, which pushed bond prices "
    "**down** and hurt share prices at the same time. The correlation jumped to about +0.7, and shares and bonds "
    "fell together. **When inflation is the main risk, bonds may not protect a portfolio.** Cash, "
    "short-term T-bills and gold matter more in that situation."
)

with st.expander("Compare all five standard profiles"):
    daily = proposal.asset_returns
    rows = []
    for level, p in get_profile_portfolios(client.equity_style).items():
        t = stress_test(daily, p.weights)
        rows.append({"Profile": PROFILES[level].name,
                     **{s.name: t.loc[s.name, "max_drawdown"] * 100 for s in SCENARIOS}})
    st.dataframe(pd.DataFrame(rows), hide_index=True,
                 column_config={s.name: percent for s in SCENARIOS})
    st.caption("Largest fall in each crisis.")

st.page_link(PAGES["download"], label="Download the client proposal", icon=":material/arrow_forward:")
