"""Page 2: the recommended allocation, why it suits the client, and where it sits on the efficient frontier."""

import numpy as np
import pandas as pd
import streamlit as st

from common import PAGES, get_frontier, get_market_inputs, get_profile_portfolios, require_proposal, show_figure
from riskfit.config import ASSET_LABELS, ASSET_ORDER, asset_label, proxy_description
from riskfit.optimiser import assumptions
from riskfit.optimiser.mean_variance import profile_bounds
from riskfit.optimiser.sensitivity import assumption_sensitivity
from riskfit.proposal import explain_allocation, pct
from riskfit.report.charts import plot_allocation_donut, plot_efficient_frontier

proposal = require_proposal()
client, profile, portfolio = proposal.client, proposal.profile, proposal.portfolio
style = client.equity_style

st.title("Recommended Portfolio")
st.write(f"**{client.name}** · {profile.profile.name} profile · {proposal.money(client.investment_amount)}")

low, high = proposal.typical_range
c1, c2, c3 = st.columns(3)
c1.metric("Expected return per year, after fees", f"{proposal.expected_return_net:.1%}",
          help=f"Long-term assumption of {portfolio.expected_return:.1%} before fees, less an assumed "
               f"{proposal.annual_fee:.0%} yearly fee.")
c2.metric("Expected volatility per year", f"{portfolio.volatility:.1%}",
          help=f"The optimiser's risk estimate (monthly data). The target for this profile is "
               f"{portfolio.target_volatility:.1%}.")
c3.metric("Typical yearly range", f"{pct(low, True)} to {pct(high, True)}",
          help="Expected return after fees ± one historical volatility: about 2 years in 3 should fall in "
               "this range.")

left, right = st.columns([1, 2])
with left:
    show_figure(plot_allocation_donut(portfolio.weights), width=260, transparent=True)
with right:
    bounds = profile_bounds(profile.profile, profile.min_cash)
    table = pd.DataFrame({
        "Asset class": [asset_label(a, style) for a in ASSET_ORDER],
        "ETF proxy": [proxy_description(a, style) for a in ASSET_ORDER],
        "Weight": [portfolio.weights[a] * 100 for a in ASSET_ORDER],
        "Amount": [proposal.money(portfolio.weights[a] * client.investment_amount, 1000) for a in ASSET_ORDER],
        "Allowed range": [f"{lo:.0%} – {hi:.0%}" for lo, hi in bounds],
    })
    st.dataframe(table, hide_index=True,
                 column_config={"Weight": st.column_config.NumberColumn(format="%.0f%%")})
    if not portfolio.target_met:
        st.warning("The weight limits do not allow a portfolio this safe, so the lowest-risk allowed mix is shown.")

st.subheader("Why this mix suits the client")
for paragraph in explain_allocation(proposal):
    st.write(paragraph)

st.subheader("Where the portfolio sits on the efficient frontier")
mu, cov = get_market_inputs(style)
fig = plot_efficient_frontier(get_frontier(style), get_profile_portfolios(style), mu, cov,
                              highlight=(portfolio.volatility, portfolio.expected_return, client.name))
show_figure(fig)
st.caption("The line shows the highest expected return for each level of risk. Dots are the five standard "
           "profiles; the ring is this client's portfolio. A liquidity cash floor can move it slightly below "
           "its profile's dot.")

with st.expander("Method and assumptions"):
    st.markdown(
        "**Optimisation.** Maximise expected return, subject to: volatility ≤ the profile's target, weights "
        "add up to 100%, and each asset within its allowed range (no short selling). Solved with SciPy's SLSQP.\n\n"
        "**Expected returns** are forward-looking building blocks, not historical averages, so the optimiser "
        "does not chase past winners:"
    )
    st.dataframe(pd.DataFrame({
        "Asset class": [ASSET_LABELS[a] for a in ASSET_ORDER],
        "Expected return": [assumptions.EXPECTED_RETURNS[a] for a in ASSET_ORDER],
        "Building block": [
            f"cash {assumptions.CASH_RATE:.1%} + equity risk premium {assumptions.EQUITY_RISK_PREMIUM:.1%}",
            f"cash {assumptions.CASH_RATE:.1%} + term/credit premium {assumptions.BOND_PREMIUM:.1%}",
            "long-run T-bill yield",
            f"inflation {assumptions.EXPECTED_INFLATION:.1%} + real return {assumptions.GOLD_REAL_RETURN:.1%}",
        ],
    }), hide_index=True, column_config={"Expected return": st.column_config.NumberColumn(format="percent")})
    st.markdown("**Risk** comes from monthly returns since mid-2007. Volatilities are measured directly; "
                "correlations are shrunk towards zero with Ledoit-Wolf to reduce estimation noise:")
    vols = np.sqrt(np.diag(cov))
    corr = pd.DataFrame(cov.values / np.outer(vols, vols), index=[ASSET_LABELS[a] for a in cov.index],
                        columns=[ASSET_LABELS[a] for a in cov.columns])
    st.dataframe(corr.style.format("{:.2f}"))

with st.expander("How sensitive is this portfolio to the return assumptions?"):
    st.markdown(
        "Expected returns are the least certain input, so the optimiser is re-run with one assumption changed "
        "at a time. If the weights barely move, the recommendation does not depend on getting that number "
        "exactly right."
    )
    sensitivity = assumption_sensitivity(profile.profile, cov, profile.min_cash) * 100
    sensitivity.columns = [ASSET_LABELS.get(c, "Expected return (before fees)") for c in sensitivity.columns]
    st.dataframe(sensitivity.style.format("{:.1f}%"))
    st.caption("The volatility target and weight limits do most of the work: changing the equity premium "
               "changes the expected return but hardly changes the mix. The split between bonds and cash is "
               "the most sensitive part.")

st.page_link(PAGES["stress"], label="See how this portfolio did in past crises", icon=":material/arrow_forward:")
