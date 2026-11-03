"""Page 3: historical crises, risk measures, and the stock-bond correlation story."""

import pandas as pd
import streamlit as st

from common import PAGES, get_prices, get_profile_portfolios, require_proposal, show_figure, usd
from riskfit.config import ASSET_ORDER
from riskfit.data.loader import to_returns
from riskfit.report.charts import plot_rolling_correlation, plot_scenario_paths
from riskfit.risk_profile.profiles import PROFILES
from riskfit.stress_test.metrics import rolling_correlation
from riskfit.stress_test.scenarios import SCENARIOS, format_recovery, stress_test

proposal = require_proposal()
client, portfolio = proposal.client, proposal.portfolio
amount = client.investment_amount

st.title("Stress Tests")
st.write(f"How **{client.name}**'s portfolio would have done if held through three real crises. "
         "Weights are rebalanced daily; fees and taxes are ignored.")

table = pd.DataFrame([
    {"Crisis": name, "Period": f"{r.start:%b %Y} – {r.end:%b %Y}", "Return over the crisis": r.total_return * 100,
     "Largest fall": r.max_drawdown * 100, "Largest fall in USD": usd(round(r.max_drawdown * amount, -3)),
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
         f"**{usd(round(-risk['var_95_daily'] * amount, -2))}**, and on the worst 5% of days about "
         f"**{usd(round(-risk['es_95_daily'] * amount, -2))}** on average.")

st.subheader("Why 2022 matters: bonds do not always protect a portfolio")
prices = get_prices()
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
    for level, p in get_profile_portfolios().items():
        t = stress_test(daily, p.weights)
        rows.append({"Profile": PROFILES[level].name,
                     **{s.name: t.loc[s.name, "max_drawdown"] * 100 for s in SCENARIOS}})
    st.dataframe(pd.DataFrame(rows), hide_index=True,
                 column_config={s.name: percent for s in SCENARIOS})
    st.caption("Largest fall in each crisis.")

st.page_link(PAGES["download"], label="Download the client proposal", icon=":material/arrow_forward:")
