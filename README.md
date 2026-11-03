# RiskFit — Private Wealth Portfolio Proposal Engine

RiskFit is a tool a relationship manager could use to turn a client's risk-profiling questionnaire into an
investment proposal. It scores the client into one of five risk profiles, separating their **willingness**
to take risk (attitude) from their **ability** to take risk (horizon and maximum loss). It then builds a
portfolio of global equities, investment-grade bonds, cash and gold using **constrained mean-variance
optimisation** with Ledoit-Wolf shrinkage. It **stress-tests** that portfolio against the 2008 Global
Financial Crisis, the 2020 COVID crash and the 2022 inflation shock. Finally, it produces a **one-page PDF
proposal** written for a non-expert client. Everything runs in a four-page Streamlit app on free daily ETF
data from 2007 to 2026.

> **For illustration only. Not investment advice.** This is a student portfolio project. All clients are fictional.

![Recommended portfolio page](docs/screenshots/2_portfolio.png)

| Client questionnaire | Stress tests | One-page PDF proposal |
|---|---|---|
| ![Questionnaire](docs/screenshots/1_questionnaire.png) | ![Stress tests](docs/screenshots/3_stress_tests.png) | ![Sample PDF](docs/images/sample_proposal.png) |

Sample PDFs for three fictional clients are in [`examples/`](examples/).

---

## How it works

```
Questionnaire ─► Risk profile ─► Optimised portfolio ─► Stress tests ─► PDF proposal
 (5 + 3 questions)  (1 of 5 levels)  (SciPy SLSQP)          (2008 / 2020 / 2022)  (reportlab)
```

1. **Client Questionnaire.** Five attitude-to-risk questions (goal, experience, reaction to a 20% fall,
   preferred range of outcomes, comfort with swings), plus investment horizon, maximum acceptable loss
   and liquidity needs.
2. **Recommended Portfolio.** The optimised allocation, the efficient frontier with the client marked on
   it, and a plain-English explanation of why the mix suits them.
3. **Stress Tests.** Return, maximum drawdown and recovery time in each crisis, plus volatility,
   historical VaR and expected shortfall, and the rolling stock–bond correlation.
4. **Download Proposal.** A one-page PDF with the client's profile, allocation chart, expected return and
   range, worst historical loss in USD, a plain-English explanation and a clear disclaimer.

## How to run

You need Python 3.10 or newer.

```bash
git clone https://github.com/HxCSYxC/riskfit-portfolio-advisor.git
cd riskfit-portfolio-advisor
pip install -r requirements.txt

streamlit run app/streamlit_app.py      # the app, at http://localhost:8501
pytest                                  # 97 tests
```

The price data is already cached in `riskfit/data/cache/prices.csv`, so the app works offline. Other commands:

```bash
python -m riskfit.data.loader --refresh     # download fresh prices from Yahoo Finance
python -m riskfit.optimiser.frontier        # print profile portfolios, save the frontier chart
python -m riskfit.stress_test.scenarios     # print stress-test tables, save the charts
python scripts/generate_examples.py         # rebuild the three example PDFs
```

---

## Methodology

### Data and asset proxies

All data is daily, from Yahoo Finance via `yfinance`. Prices are **adjusted** for dividends and coupons,
so returns are total returns. The base currency is **USD**. HKD is pegged to the USD (7.75–7.85 band),
so USD results are a fair guide for a Hong Kong client.

| Asset class | ETF | Data from | Why this proxy |
|---|---|---|---|
| Global equities | SPY | 1993 | Global ETFs (ACWI, VT) only start in 2008, too late for the GFC. So this sleeve is really *US* large-cap. |
| Investment-grade bonds | AGG | Sep 2003 | Whole US investment-grade market (Treasuries, corporates, MBS). A Treasury-only fund (IEF) would flatter 2008. |
| Cash | BIL | May 2007 | 1–3 month T-bills. The closest ETF to cash with history before the GFC. |
| Gold | GLD | Nov 2004 | Physically backed gold. |

The four-asset sample runs from **30 May 2007 to 29 Oct 2026** (4,887 trading days).

### Risk profiling: willingness vs ability

- **Attitude to risk:** five questions scored 1–5 points each (total 5–25), mapped to levels 1–5.
- **Ability to take risk:** the investment horizon and the maximum acceptable loss each set a **cap** on
  the level (e.g. a 1–3 year horizon caps the client at level 2).
- **Final profile = the lowest of the three.** A client who *wants* high risk but needs the money soon
  gets a cautious profile, and the proposal explains why.
- **Liquidity needs** don't lower the profile. They set a **minimum cash holding** (10% or 20%).

The maximum-loss bands (15% / 25% / 35% / 45% / more) were **calibrated against the stress tests**, so
every profile's worst historical drawdown stays within the loss the client said they could accept. A unit
test re-checks this on the real data.

### Portfolio construction

For each profile, the optimiser **maximises expected return** subject to:
- **volatility ≤ the profile's target** (4% / 6.5% / 9% / 11.5% / 14%);
- weights adding up to 100%, with no short selling;
- **minimum and maximum weights per asset**, including a 5% minimum in gold and the liquidity cash floor.

It is solved with SciPy's SLSQP.

- **Expected returns are forward-looking "building blocks", not historical averages:**
  - cash 3.0%;
  - bonds 4.0% (cash + 1% term/credit premium);
  - equities 7.0% (cash + 4% equity risk premium);
  - gold 3.5% (inflation + 1%).

  From 2007 to 2026, US equities returned about 11% a year and gold about 9%. Feeding those numbers into
  an optimiser would make it chase past winners.
- **Covariance** comes from monthly returns with **Ledoit-Wolf shrinkage applied to the correlations**
  (shrinkage intensity 0.25). Each asset keeps its measured volatility. The standard version would pull
  cash's 0.6% volatility up towards the average.
- **The 5% gold floor is a deliberate policy choice.** With a conservative return assumption, pure
  mean-variance holds no gold. The floor costs under 0.1% a year of expected return and slightly reduced
  drawdowns in 2008 and 2022.

![Efficient frontier](docs/images/efficient_frontier.png)

### Stress tests and risk measures

| Scenario | Window | What happened |
|---|---|---|
| Global Financial Crisis | 9 Oct 2007 – 9 Mar 2009 | US equities −55%; bonds +7%, gold +25% |
| COVID-19 crash | 19 Feb – 23 Mar 2020 | US equities −33% in five weeks |
| 2022 inflation and rate shock | calendar 2022 | US equities −18% **and** bonds −13% |

For each scenario, RiskFit reports:
- **return over the window**;
- **maximum drawdown**, the worst peak-to-trough fall;
- **recovery time**, from the trough until the portfolio is back at its pre-crisis peak, using the data after the crisis.

Full-period measures:
- annualised volatility;
- **historical 95% VaR and expected shortfall**, from actual daily returns, so fat tails are included;
- the **rolling 3-year stock–bond correlation**.

---

## Key results

**The five profile portfolios** (no liquidity needs):

| Profile | Equities | Bonds | Cash | Gold | Exp. return | Exp. volatility |
|---|---|---|---|---|---|---|
| Conservative | 18% | 42% | 35% | 5% | 4.2% | 4.0% |
| Moderately Conservative | 34% | 56% | 5% | 5% | 5.0% | 6.5% |
| Balanced | 54% | 41% | 0% | 5% | 5.6% | 9.0% |
| Moderately Aggressive | 72% | 23% | 0% | 5% | 6.1% | 11.5% |
| Aggressive | 90% | 5% | 0% | 5% | 6.7% | 14.0% |

**How they would have done in past crises** (maximum drawdown, recovery time in brackets):

| Profile | 2008 GFC | 2020 COVID | 2022 inflation | 95% daily VaR | 95% daily ES |
|---|---|---|---|---|---|
| Conservative | −12.4% (10 months) | −8.6% (2 months) | −11.4% (14 months) | −0.39% | −0.64% |
| Moderately Conservative | −20.2% (12 months) | −14.2% (2 months) | −17.1% (17 months) | −0.67% | −1.10% |
| Balanced | −30.4% (13 months) | −19.8% (3 months) | −19.5% (14 months) | −1.00% | −1.64% |
| Moderately Aggressive | −40.9% (21 months) | −25.5% (4 months) | −21.2% (14 months) | −1.31% | −2.17% |
| Aggressive | −50.0% (26 months) | −30.8% (4 months) | −23.0% (14 months) | −1.64% | −2.70% |

![Stress scenarios](docs/images/stress_scenarios.png)

**What stands out:**

- **2008 rewarded diversification; 2022 did not.** In the GFC the gap between Conservative (−12%) and
  Aggressive (−50%) was huge, because bonds and gold rose while stocks fell. In 2022 the gap shrank to
  −11% vs −23%, and the Balanced portfolio lost about as much as in the COVID crash (−19.5% vs −19.8%),
  even though stocks fell far less.
- **Why: bonds don't always protect a portfolio when inflation is the main risk.** Normally, falling
  stocks mean a weaker economy, rate cuts and *rising* bond prices. In 2022, inflation forced rapid rate
  *rises*, which hit bonds and stocks at the same time. The rolling 3-year stock–bond correlation went from
  mostly between −0.45 and 0 in the 2010s to about **+0.7** after 2022.
- **Recovery matters as much as the fall.** After 2008 the Aggressive portfolio needed over two years to
  regain its peak. After COVID it needed four months.
- **The stress tests changed the questionnaire.** The first version allowed a client who accepts "up to 5%
  loss" into a portfolio that fell 12% in 2008. The loss bands were recalibrated so that no proposal
  promises a loss limit its portfolio has already broken.

![Rolling stock-bond correlation](docs/images/stock_bond_correlation.png)

---

## Limitations

- **History is a limited guide.** About 19 years of ETF data cover only three major crises. The next one
  may look different (e.g. 1970s-style inflation or a long bear market), and tested weights were chosen
  *after* these events.
- **ETF proxies.** "Global equities" is really US large-cap (SPY), which adds home bias, sector
  concentration and no currency diversification. AGG and BIL are US instruments.
- **No fees, taxes or trading costs**, and **daily rebalancing** in the tests. Real portfolios rebalance
  less often and pay management fees and spreads, so real outcomes would be somewhat worse.
- **USD base only.** This is fine for HKD clients under the peg, but not for clients spending in other currencies.
- **Assumption-driven.** Expected returns are judgement-based capital market assumptions. Different (but
  reasonable) numbers would change the weights. Volatility is estimated from monthly data, which
  understates daily volatility (e.g. 14% target vs 17.7% realised for Aggressive). The app shows both.
- **Simplified suitability.** A real assessment covers the client's whole financial situation, existing
  holdings, concentration, knowledge of products and regulatory requirements. Here it is eight questions
  and one pot of money.
- **Four asset classes only.** No regional equities, high yield, private markets or alternatives.

---

## Project structure

```
riskfit/
  config.py                    # asset classes, ETF tickers, paths
  data/loader.py               # download, clean, cache prices; returns
  risk_profile/questionnaire.py  # questions, scoring, willingness vs ability
  risk_profile/profiles.py     # 5 profiles: volatility target, loss limit, weight limits
  optimiser/assumptions.py     # building-block expected returns
  optimiser/mean_variance.py   # Ledoit-Wolf covariance, constrained optimisation
  optimiser/frontier.py        # efficient frontier
  stress_test/metrics.py       # drawdown, recovery, VaR, ES, rolling correlation
  stress_test/scenarios.py     # 2008 / 2020 / 2022 scenarios
  proposal.py                  # questionnaire -> portfolio -> stress tests -> explanation
  report/charts.py             # matplotlib charts used by the app, PDF and README
  report/pdf.py                # one-page reportlab proposal
app/                           # Streamlit app (4 pages)
examples/                      # 3 fictional clients (.json) and their PDFs
scripts/generate_examples.py
tests/                         # 97 pytest tests
LEARNING.md                    # plain-English explanation of every part, with interview Q&A
```

**Tests** cover:
- the scoring rules (band edges, capacity caps, liquidity);
- the optimiser constraints (weights sum to 1, limits respected, volatility target met, cash floor);
- the stress-test maths (drawdown, recovery and VaR/ES on hand-checked examples);
- a calibration check on real data;
- the PDF (exactly one page, key content present);
- a smoke test of every app page.

---

*Built as a portfolio project for private wealth management, using Python, pandas, SciPy, scikit-learn,
matplotlib, reportlab and Streamlit.*
