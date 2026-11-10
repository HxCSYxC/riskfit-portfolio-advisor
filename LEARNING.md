# LEARNING.md: How RiskFit works, in plain English

This file explains each part of the project, why it was built that way, and the
questions an interviewer might ask about it. One section is added per phase.

**Contents**
1. [Data and questionnaire scoring](#phase-1-data-and-questionnaire-scoring)
2. [Optimiser and efficient frontier](#phase-2-optimiser-and-efficient-frontier)
3. [Stress tests and risk measures](#phase-3-stress-tests-and-risk-measures)
4. [The one-page PDF proposal](#phase-4-the-one-page-pdf-proposal)
5. [The Streamlit app](#phase-5-the-streamlit-app)
6. [Testing, the README, and presenting the project](#phase-6-testing-the-readme-and-presenting-the-project)
7. [Improvements: global equities, Hong Kong options, costs, what-if shocks, sensitivity](#phase-7-improvements)

All numbers in this file are for the current version (data to 10 Nov 2026, global equity mix,
1% yearly fee and quarterly rebalancing in the historical tests).

---

## Phase 1: Data and questionnaire scoring

### What the code does

**`riskfit/config.py`** lists the four asset classes and the ETF that stands in for each:

| Asset class | ETF | Why this one |
|---|---|---|
| Equities | SPY 60% / EFA 30% / EEM 10% | A fixed blend of US shares (SPY), other developed markets (EFA) and emerging markets (EEM), close to a global index's regional weights. Global ETFs (ACWI, VT) only start in 2008, too late to test the 2008 crisis; these three all have history from 2003. The first version used SPY alone, which was really *US* shares. |
| Investment-grade bonds | AGG | Covers the whole US investment-grade market: Treasuries, corporate bonds and mortgage bonds. The usual alternative, IEF, holds only 7–10 year Treasuries. Treasuries *rose* in 2008 while corporate bonds fell, so IEF would make bonds look safer than an investment-grade mix really is. |
| Cash | BIL (1–3 month T-bills) | The closest thing to cash in an ETF. It launched in May 2007, just before the 2008 crisis window starts. SHY (1–3 year bonds) has more history but carries some interest-rate risk, so it is not really cash. |
| Gold | GLD | The largest physically backed gold ETF, launched in 2004. |

Everything is in USD. HKD is pegged to the USD (7.75–7.85 band), so a USD-based
analysis is a reasonable guide for a Hong Kong client.

**`riskfit/data/loader.py`** downloads the prices, cleans them and saves them to
`riskfit/data/cache/prices.csv`:

- It uses **adjusted** prices (`auto_adjust=True`). These include dividends and
  coupon payments, so the % change is a *total return*. Without this, bonds and
  cash would look as if they earned almost nothing, because nearly all of their
  return comes from income rather than price changes.
- It **caches** the data in a CSV file. The app reads the file instead of
  downloading on every run. It is faster, it works offline, and every run uses
  the same data, so the results can be reproduced.
- `clean_prices` sorts the dates, removes duplicate dates, and fills gaps of up
  to 5 days with the last known price (for example, a missing quote).
  It does **not** fill long gaps, because that would invent prices for an ETF
  before it existed.
- `common_sample` keeps only the dates where all four ETFs have a price. Risk
  estimates need all four assets measured over the same period.
- `to_returns` turns prices into daily or monthly returns.
- `availability_report` shows each ETF's first date and whether it covers the
  start of the 2008 crisis (9 Oct 2007).

**`riskfit/risk_profile/profiles.py`** defines the five risk profiles
(Conservative → Aggressive). Each profile has:
- a **target volatility**, the most risk the optimiser is allowed to take
  (from 4% a year up to 14%);
- **weight limits** per asset class, e.g. a Conservative portfolio holds at
  most 20% equities;
- a **loss limit** (15% / 25% / 35% / 45% / 60%), the largest fall the client should be
  ready for. It is used to match the client's own maximum acceptable loss.
  (Phase 3 recalibrated these against the stress tests; see below.)

**`riskfit/risk_profile/questionnaire.py`** scores the client. It separates two ideas:

1. **Risk tolerance** (willingness): five questions about the client's goal,
   experience, how they would react to a 20% fall, which range of outcomes they
   prefer, and how they feel about short-term swings. Each answer scores 1–5, so
   the total is 5–25. The score maps to a level: 5–8 → 1, 9–12 → 2, 13–16 → 3,
   17–20 → 4, 21–25 → 5.
2. **Risk capacity** (ability): the investment horizon and the maximum loss the
   client can accept. Each one sets a *cap* on the level. For example, a 1–3 year
   horizon caps the client at level 2.

**Final profile = the lowest of the tolerance level, the horizon cap and the loss cap.**

**Liquidity needs** do not change the profile. They set a **minimum cash
holding** (0%, 10% or 20%) that the optimiser must respect in Phase 2.

The scorer also writes plain-English **reasons**, for example: *"Your investment
horizon (1 to 3 years) limits the profile to Moderately Conservative, because
there may not be time to recover from a large fall."* These reasons go into the
PDF proposal later.

### Why these choices

- **Separating willingness and ability** is standard practice in private
  banking suitability assessments. A client can *want* high risk but not be
  *able* to afford it, for example because they need the money soon. Taking
  the lowest of the three is the cautious, client-protective choice.
- **Treating liquidity as minimum cash instead of a lower profile.** Needing
  some money soon is a cash-flow problem, not an attitude to risk. Holding cash
  for that part solves the problem directly. The rest of the portfolio can
  still follow the client's profile.
- **Simple point scoring** is easy to explain to a client and to check. Real
  banks use longer questionnaires, but the structure is the same.
- **Tests run without the internet.** They use small hand-made tables and
  "monkeypatch" the download function, so they are fast and always give the
  same result.

### Interview questions

**Q1. What is the difference between risk tolerance and risk capacity, and how does your tool combine them?**
> Tolerance is how much risk the client is *willing* to take. It is psychological,
> measured through questions like "what would you do after a 20% fall?". Capacity
> is how much risk they can *afford* to take, given their time horizon and how
> big a loss they could absorb. My tool scores tolerance into a level from 1 to
> 5, and horizon and maximum loss each set a ceiling. The final profile is the
> lowest of the three. If someone is aggressive by temperament but needs the
> money in two years, they get a cautious profile, and the proposal explains why.

**Q2. Why did you use AGG rather than IEF for bonds, and what are the limitations of your ETF proxies?**
> The asset class is "investment-grade bonds", which includes corporate bonds,
> not just Treasuries. IEF is 7–10 year Treasuries only. Treasuries rallied in
> 2008 because investors fled to safety, while corporate bonds fell, so IEF would
> overstate how well bonds protected a portfolio. AGG is the broad
> investment-grade market, so it matches the label. For equities, global ETFs
> don't have data back to 2007, so I blend three regional ETFs at fixed
> weights (60% US, 30% other developed, 10% emerging). A real global index
> changes its weights over time, so the blend is an approximation. Bonds and
> cash are US instruments. Also, ETF data only goes back about 20 years, so it
> covers a small number of crises.

**Q3. Why use adjusted prices, and why cache the data?**
> Adjusted prices add back dividends and coupons, so their returns are total
> returns. For a bond or T-bill ETF the income *is* the return. Using unadjusted
> prices would make those assets look as if they earned almost nothing and
> would distort the optimisation. I cache the data so the app is fast and works
> offline, and so every run uses the same data set. That means the numbers in
> the proposal can be reproduced and checked later, which matters for
> compliance.

---

## Phase 2: Optimiser and efficient frontier

### What the code does

**`riskfit/optimiser/assumptions.py`** sets the *expected return* for each asset
class using simple "building blocks":

| Asset | Building block | Expected return |
|---|---|---|
| Cash | long-run T-bill rate | 3.0% |
| Bonds | cash + 1.0% term and credit premium | 4.0% |
| Equities | cash + 4.0% equity risk premium | 7.0% |
| Gold | 2.5% inflation + 1.0% real return | 3.5% |

**`riskfit/optimiser/mean_variance.py`** builds the portfolios:

1. **Covariance matrix.** It uses month-end returns from June 2007 to November
   2026 (about 230 months) for all four asset classes and applies **Ledoit-Wolf
   shrinkage to the correlations**. Each asset keeps its own measured
   volatility (equities 15.7%, bonds 4.7%, cash 0.6%, gold 17.6% a year). The
   correlations are pulled 23% of the way towards zero. For example, the
   stock–bond correlation goes from 0.29 to 0.23.
2. **Optimisation.** For each profile, SciPy's `SLSQP` solver finds the weights that
   - **maximise expected return**,
   - with **volatility ≤ the profile's target**,
   - **weights adding up to 100%**,
   - and **each weight within the profile's limits** (no short selling).
3. **Liquidity.** If the client needs cash, the cash floor is raised to 10% or
   20%. If that is above the profile's normal cash cap, the cap is raised too.
4. **Unreachable target.** If even the safest allowed mix is riskier than the
   target, the code returns the minimum-risk portfolio and sets
   `target_met = False`, instead of failing.

**`riskfit/optimiser/frontier.py`** traces the **efficient frontier**: for 40
target returns it finds the lowest-risk portfolio that reaches each one. The
chart (`docs/images/efficient_frontier.png`) shows the frontier, the four
single assets and the five profile portfolios.

**Results:**

| Profile | Equities | Bonds | Cash | Gold | Exp. return | Volatility |
|---|---|---|---|---|---|---|
| Conservative | 17.4% | 41.4% | 36.2% | 5.0% | 4.14% | 4.0% |
| Moderately Conservative | 32.2% | 57.8% | 5.0% | 5.0% | 4.89% | 6.5% |
| Balanced | 51.6% | 43.4% | 0.0% | 5.0% | 5.52% | 9.0% |
| Moderately Aggressive | 70.0% | 25.0% | 0.0% | 5.0% | 6.07% | 11.5% |
| Aggressive | 87.5% | 7.5% | 0.0% | 5.0% | 6.60% | 14.0% |

Each profile's weight limits cost less than 0.1% a year compared with the
unconstrained frontier.

### Why these choices

- **Forward-looking returns, not historical averages.** Mean-variance
  optimisation is very sensitive to expected returns. Historically, global
  equities returned about 8% a year from 2007 to 2026, and gold about 9%. Both
  were good periods that may not repeat. An optimiser fed those numbers
  would put almost everything into shares and gold. Building-block assumptions are
  conservative, easy to explain to a client, and close to the long-term
  capital market assumptions that banks and asset managers publish.
- **Ledoit-Wolf on correlations only.** The sample covariance matrix contains
  estimation noise, and the optimiser leans on that noise ("error
  maximisation"). Shrinkage pulls the estimate towards a simple target, and
  Ledoit-Wolf chooses *how much* from the data. I apply it to standardised
  returns, so it shrinks correlations but leaves each volatility alone. The
  standard version pulls all variances towards their average, which made cash
  look like it had 2% volatility instead of 0.6%. Volatilities are estimated
  quite precisely; correlations are the noisy part.
- **Monthly returns** reduce day-to-day noise and timing mismatches. For
  example, gold trades on different exchanges and hours than US stocks.
  Monthly returns also match how a strategic portfolio is reviewed. One
  caveat: volatility measured from *daily* data is higher (about 20% for
  equities, because of very turbulent days in 2008 and 2020). Phase 3 reports
  that realised daily risk as well.
- **Volatility target + weight limits** instead of a fixed allocation table.
  The volatility target links each profile to a clear risk number. The weight
  limits stop "corner solutions", such as 0% bonds for a Balanced client, and
  reflect house policy.
- **A 5% minimum in gold.** With a 3.5% expected return and about 18%
  volatility, the pure optimiser held **no gold at all**. That is correct
  given its inputs, but gold's value is as a *crisis diversifier*, which an
  average covariance matrix misses. So I added a small strategic floor and
  measured its cost (under 0.1% a year). This is a deliberate policy decision,
  not the optimiser's output, and I say so openly.
- **SciPy SLSQP rather than cvxpy.** With four assets the problem is tiny.
  SLSQP handles the nonlinear volatility constraint directly, and it means one
  library fewer to install.

### Interview questions

**Q1. Why didn't you use historical average returns in the optimiser?**
> Mean-variance optimisation is extremely sensitive to expected returns: a
> small change can swing the weights a lot. Historical averages are very noisy
> estimates of the future, and the last 20 years were unusually good for US
> equities and gold. Using them would make the optimiser "chase" past
> performance and concentrate the portfolio. Instead I used building blocks:
> a cash rate plus a risk premium for each asset class. That is conservative,
> easy to justify to a client, and close to how banks publish their capital
> market assumptions. Risk, measured by volatilities and correlations, is
> estimated from data, because it is much more stable than returns.

**Q2. What is Ledoit-Wolf shrinkage and why did you apply it to correlations only?**
> The sample covariance matrix has estimation error. The optimiser treats
> that error as real and over-weights assets that *look* like good
> diversifiers by chance. Ledoit-Wolf blends the sample estimate with a
> simple, stable target, and it calculates the best blend from the data. Here
> it pulled correlations 23% of the way towards zero. I applied it to
> standardised returns because the standard version also pulls all the
> variances towards the average. With cash at 0.6% volatility and gold at
> 18%, that made cash look about four times riskier than it is. Volatilities
> are measured accurately, so there's no reason to shrink them.

**Q3. The optimiser wanted 0% gold, but your portfolios hold 5%. Isn't that overriding the model?**
> Yes, and on purpose. The model is only as good as its inputs. With a
> conservative return assumption and one average correlation matrix, gold
> looks like a high-volatility asset with a low return. But its main role is
> to diversify in crises, especially when inflation is the problem and bonds
> and stocks fall together, as in 2022. A single covariance matrix can't
> capture that. So I set a small 5% strategic floor, measured its cost (less
> than 0.1% a year of expected return), and documented it. In practice,
> investment committees often combine optimiser output with this kind of
> judgement. The important thing is to be transparent about it, and the
> Phase 3 stress tests show whether it helped.

---

## Phase 3: Stress tests and risk measures

### What the code does

**`riskfit/stress_test/scenarios.py`** defines three historical crises and
replays each profile's *current* weights through them:

| Scenario | Window | What happened |
|---|---|---|
| Global Financial Crisis | 9 Oct 2007 – 9 Mar 2009 | Global equities −56%; bonds +7%, gold +25% |
| COVID-19 crash | 19 Feb – 23 Mar 2020 | Global equities −33% in five weeks; almost everything fell for a few days |
| 2022 inflation and rate shock | calendar year 2022 | Global equities −17% **and** bonds −13%, together |

For each scenario it reports:
- **Return over the crisis**: from the first day to the last day of the window.
- **Maximum drawdown**: the largest fall from a peak to a later low inside the
  window. This can be worse than the return, because the portfolio may bounce
  back a little before the window ends.
- **Recovery time**: calendar days from the lowest point until the portfolio
  is back at its pre-crisis peak, using all the data *after* the crisis.
  "Not yet recovered" if that never happens.

The portfolio is rebalanced to its target weights every quarter and pays a 1%
yearly fee. Taxes are ignored. (The first version used daily rebalancing and no
fees; Phase 7 explains the change.)

**`riskfit/stress_test/metrics.py`** holds the maths: portfolio returns,
total return, drawdown, recovery, annualised volatility, historical VaR,
expected shortfall and rolling correlation.

**Results** (maximum drawdown, with recovery time in brackets):

| Profile | 2008 GFC | 2020 COVID | 2022 inflation |
|---|---|---|---|
| Conservative | −13.2% (12 months) | −8.4% (2 months) | −12.3% (19 months) |
| Moderately Conservative | −21.7% (14 months) | −14.0% (3 months) | −18.5% (21 months) |
| Balanced | −32.3% (19 months) | −18.8% (3 months) | −21.0% (19 months) |
| Moderately Aggressive | −42.9% (25 months) | −23.7% (4 months) | −23.0% (16 months) |
| Aggressive | −51.7% (46 months) | −29.2% (4 months) | −24.9% (16 months) |

**Full-period risk** (daily data, June 2007 – Nov 2026, after the 1% fee):

| Profile | Annual return | Annual volatility | 95% daily VaR | 95% daily ES |
|---|---|---|---|---|
| Conservative | 2.8% | 4.3% | −0.40% | −0.63% |
| Moderately Conservative | 4.2% | 7.3% | −0.68% | −1.06% |
| Balanced | 5.3% | 10.6% | −0.96% | −1.60% |
| Moderately Aggressive | 6.2% | 14.1% | −1.29% | −2.15% |
| Aggressive | 7.0% | 17.7% | −1.62% | −2.70% |

**Two charts** (in `docs/images/`):
- `stress_scenarios.png`: the value of 100 invested, through each crisis, for all five profiles.
- `stock_bond_correlation.png`: the rolling 3-year (36-month) correlation between global equities and AGG.

### What the stress tests changed

1. **Loss limits recalibrated.** In Phase 1, a client who answered "I can
   accept up to 5% loss" was put in the Conservative profile. But the
   Conservative portfolio actually fell about **13%** in 2008. A proposal must not
   promise a loss limit that the portfolio has already broken. So each
   profile now has a `loss_limit` (15 / 25 / 35 / 45 / 60%) set just above its
   worst historical drawdown. The questionnaire's loss bands match these
   limits. A test (`test_profiles_stay_within_their_loss_limits`) re-checks
   this on the real data every time the tests run.
2. **The gold floor helped, a little.** Compared with the same profiles with
   no gold minimum, 5% gold reduced the maximum drawdown by about 0.3–0.8
   percentage points in 2008 and 2022, and by about 0.2 in COVID. It is
   modest but in the right direction, for a cost of under 0.1% a year of
   expected return.

### Why 2022 matters: bonds don't always protect you

Usually, when stocks fall it is because the economy is weakening. Central
banks then cut interest rates, which pushes bond prices *up*. So bonds rise
when stocks fall, and the stock–bond correlation is negative. That is why a
"balanced" portfolio works.

In 2022 the problem was **inflation**. To fight it, the Federal Reserve raised
rates very fast. Higher rates push bond prices *down*, and they also hurt
company valuations, so **both fell at the same time**. The correlation chart
shows this clearly. From 2012 to 2021 the 3-year correlation stayed between
about −0.4 and +0.2, so bonds diversified stocks. After 2022 it jumped to
about **+0.8**. In plain English: when inflation is the main risk, bonds and
stocks are hit by the same thing, so holding bonds does not cushion the fall.
This is why the Balanced portfolio lost more in 2022 (−21.0%) than in
the COVID crash (−18.8%), and why the gaps between profiles were much smaller
in 2022 than in 2008.

One more honest detail. AGG includes corporate and mortgage bonds, which carry
credit risk. So even in 2008 its correlation with stocks briefly turned
*positive* (up to about +0.4). A Treasury-only fund would have looked more
defensive. That is the trade-off of choosing a proxy that matches "investment
grade" rather than one that flatters the results.

### Why these choices

- **Historical scenarios rather than made-up shocks.** They are easy for a
  client to understand ("this is what would have happened in 2008"). They
  also capture real correlations during crises, which are different from
  normal times.
- **Maximum drawdown *and* recovery time.** Clients feel losses as "how far
  did it fall?" and "how long until I was back to where I started?". Recovery
  time shows that the 2008 losses took the Aggressive portfolio over two years
  to recover from the low point. After COVID it took only about four months.
- **Historical VaR and ES** (not a normal-distribution formula). They use the
  actual daily returns, so they include fat tails such as the crash days in
  2008 and 2020. VaR says "on 95% of days the loss was smaller than X".
  Expected shortfall says "on the worst 5% of days, the average loss was Y".
  ES is the better measure of tail risk because it looks *inside* the tail.
- **Monthly 36-month window for the correlation.** It is long enough to be
  stable, short enough to show regime changes, and it is the convention in
  most research on stock–bond correlation.
- **Daily vs monthly volatility.** The optimiser's target uses monthly data,
  for example 14% for Aggressive. Realised daily volatility is higher (17.7%),
  because daily data captures the turbulent days in 2008 and 2020, and
  volatility clusters. Both numbers are shown so the client sees the fuller
  picture.

### Interview questions

**Q1. Why did the Balanced portfolio lose more in 2022 than in the COVID crash, even though stocks fell much less?**
> Because bonds didn't help in 2022. In COVID, bonds were roughly flat and
> cushioned part of the stock fall. In 2022 the shock was inflation, and the
> Fed raised rates quickly, so bond prices fell (AGG −13%) at the same time as
> stocks (−17%). A Balanced portfolio relies on bonds to offset equity losses.
> When both are hit by the same driver, rising rates, the diversification
> disappears. You can see it in the rolling 3-year stock–bond correlation: it
> went from around zero or below in the 2010s to about +0.8 after 2022. For a
> client, the lesson is that "60/40" is not automatically safe when inflation
> is the main risk. Assets like cash, short-term T-bills and gold matter more
> in that environment.

**Q2. What is the difference between VaR and expected shortfall, and which would you show a client?**
> Historical 95% VaR is the daily loss that was exceeded on only 5% of days.
> For the Balanced portfolio that is about 1.0%. It tells you where the bad
> days start, but nothing about how bad they get. Expected shortfall is the
> average loss on those worst 5% of days: about 1.6% for Balanced. It looks
> inside the tail, so it is the better risk measure, and regulators moved from
> VaR to ES for that reason. For a private client, though, I'd lead with the
> stress-test drawdown ("in 2008 this portfolio fell about 32% and took about
> a year and a half to recover"), because it is concrete and easy to picture.

**Q3. What are the limitations of historical stress testing?**
> It only shows crises that have already happened, and the next one will be
> different. The ETF data starts in 2007, so we can't test the 1970s
> inflation or the 2000 tech crash. The tests use today's weights, which were
> chosen *after* those events, so there is some hindsight. The costs are
> simplified to one flat 1% fee with quarterly rebalancing. And the proxies
> matter: the bond and cash funds are US funds. To cover risks the history
> doesn't contain, I added three hypothetical shocks: rates up 2%,
> stagflation and a severe recession. I also used the stress
> results to check my own questionnaire: they showed my original loss bands
> were too optimistic, so I recalibrated them.

---

## Phase 4: The one-page PDF proposal

### What the code does

**`riskfit/proposal.py`** connects all the earlier steps in one function, `build_proposal(client)`:

```
client answers ──► score_client()            → risk profile + cash floor   (Phase 1)
               ──► build_profile_portfolio() → weights, exp. return, vol    (Phase 2)
               ──► stress_test(), risk_summary() → crisis results, VaR, ES   (Phase 3)
               ──► Proposal object (everything the PDF and the app need)
```

- `Client` stores a client's name, age, amount and answers. It can be saved to
  and loaded from JSON. The three example clients are in `examples/*.json`.
- `Proposal.typical_range` is the expected return ± one historical volatility.
  If returns were roughly normal, about 2 years in 3 would fall in this range.
- `explain_allocation()` writes the "Why this mix suits you" text from
  templates. It explains *why* this profile (using the reasons from the
  questionnaire), *what each asset does* ("bonds … usually cushion falls in
  share prices"), and *what to expect*, including the worst loss in plain numbers.

**`riskfit/report/pdf.py`** lays out one A4 page with reportlab:
1. Header: client name, date, and "fictional client".
2. **Your risk profile**: profile name, level, and the client's key answers.
3. **Recommended allocation**: pie (donut) chart, plus a table with the
   weights, USD amounts and the ETF used for each asset class.
4. **What to expect**, as three tiles: expected return, typical yearly range,
   and the worst historical fall (also in USD).
5. **Past crises**: a table with return, largest fall, USD loss and recovery
   time for each crisis. Below it, a chart of *this client's* portfolio vs
   100% shares through each crisis.
6. **Why this mix suits you**: the plain-English explanation.
7. **Disclaimer**: "For illustration only. Not investment advice", plus data sources.

`scripts/generate_examples.py` builds the PDFs for the three fictional clients:

| Client | Situation | Profile | Why |
|---|---|---|---|
| Mr Chan Tai Man, 62, HKD 6 million | About to retire, may draw on savings | Conservative | Attitude suggests Moderately Conservative, but he can only accept a 15% loss |
| Ms Lee Ka Yan, 41, HKD 12 million | Saving for retirement in ~20 years, wants a Hong Kong tilt | Balanced | Attitude suggests Moderately Aggressive, but her loss limit is 35% |
| Mr Wong Siu Ming, 34, USD 2 million | Entrepreneur, may buy a flat next year | Aggressive, with 20% cash | High risk appetite and long horizon, but needs liquidity |

### Why these choices

- **One `build_proposal()` for both the PDF and the app**, so the numbers a
  client sees on screen and on paper can never disagree.
- **Plain English and money amounts.** "Your portfolio could have fallen by
  about HKD 3.9 million" means more to a client than "maximum drawdown −32.4%".
  Showing money amounts, in the client's own currency, makes the risk real *before* it happens. That is the
  point of a suitability conversation.
- **Rounded numbers** (to the nearest USD 1,000 and whole percentages).
  Precise-looking figures like "USD 824,684" suggest false accuracy for
  something based on assumptions.
- **A comparison line (100% shares)** in the crisis chart gives the client a
  reference point, so they can see what diversification did for them.
- **The disclaimer is prominent** and lists the main simplifications: proxies,
  no taxes, analysis in USD, and past performance. In a regulated industry,
  what you *don't* promise matters as much as what you show.
- **A test checks every example PDF is exactly one page** and contains the key
  sections. Layout changes can quietly push content onto page 2.

### Interview questions

**Q1. How would you explain this proposal to a client with no finance background?**
> I'd start with them, not the products. "From your answers, you're
> comfortable with some ups and downs, but you told us you couldn't accept
> losing more than about a third, so we've matched you to a Balanced
> portfolio." Then the mix, with each part's job: shares for growth, bonds for
> income and cushioning, a little gold for crises. Then expectations, as a
> range rather than one number: "about 4.5% a year after fees on average, and
> most years between −6% and +15%". Finally the worst case in money: "in 2008
> this mix would have fallen about 32%, or around HKD 3.9 million on your
> HKD 12 million, and took about a year and a half to recover." If they react badly to
> that number, it's a sign the profile may be too aggressive, and that is the
> purpose of showing it.

**Q2. Why show a "typical range" instead of just the expected return?**
> A single number sounds like a promise, and clients anchor on it. The range,
> expected return ± one volatility (roughly 2 years in 3), shows that negative
> years are normal even for a well-built portfolio. That sets the right
> expectations and reduces the risk of panic selling in a bad year. I also
> state the worst historical loss separately, because a ± one-volatility range
> says nothing about crashes. Returns have fat tails, and a 2008-type fall is
> far outside it.

**Q3. What would need to change before a real bank could use this proposal?**
> Several things. A proper suitability process, including knowledge and
> experience checks, financial situation and concentration, with the
> relationship manager's sign-off. The bank's own capital market
> assumptions, approved products instead of ETF proxies, and fees and taxes
> included. Currency: an HKD-based client with USD assets is fine under the
> peg, but other currencies would need hedging decisions. Compliance-approved
> wording and disclosures, plus record-keeping of what was shown to the
> client. Technically I'd add versioned data and assumptions, so any past
> proposal could be reproduced exactly.

---

## Phase 5: The Streamlit app

### What the code does

Run it from the project root with `streamlit run app/streamlit_app.py`.

```
app/
  streamlit_app.py      # entry point: page setup, sidebar, navigation between the 4 pages
  common.py             # shared helpers: cached data, current proposal, chart display
  views/
    questionnaire.py    # 1. Client Questionnaire
    portfolio.py        # 2. Recommended Portfolio
    stress_tests.py     # 3. Stress Tests
    download.py         # 4. Download Proposal
.streamlit/config.toml  # light theme matching the chart colours
```

1. **Client Questionnaire.** The relationship manager can start from a blank
   form or load one of the three fictional example clients. Part A (attitude
   to risk) and Part B (ability to take risk) sit side by side. On submit, the
   app checks every question is answered, then calls `build_proposal()`. The
   result table shows *how* the profile was decided: the highest level allowed
   by attitude, by horizon and by loss limit, and the final level (the lowest).
2. **Recommended Portfolio.** Key numbers, the donut chart, and a weights
   table with USD amounts and each asset's *allowed range*, so the RM can see
   which limits bind. Then the plain-English explanation, the efficient
   frontier with the client's portfolio ringed, and an expander with the
   return assumptions and the shrunk correlation matrix.
3. **Stress Tests.** The crisis table, a chart of the client's portfolio vs
   100% shares in each crisis, everyday risk measures (realised volatility,
   VaR, expected shortfall, also in USD), the rolling stock–bond correlation
   with the 2022 explanation, and a comparison of all five profiles.
4. **Download Proposal.** A short summary and a button that downloads the
   same one-page PDF as in Phase 4.

**How the pages share data:** Streamlit re-runs the whole script on every
click. So the client's `Proposal` is stored in `st.session_state`, which
survives re-runs and page changes. Pages 2–4 call `require_proposal()`. If no
client has been scored yet, it shows a message and a link back to the
questionnaire instead of crashing.

**Caching:** `@st.cache_data` stores the price data, the covariance matrix,
the frontier and the five profile portfolios after the first run, so clicking
around is fast.

**Testing:** `tests/test_app.py` uses Streamlit's `AppTest` to load an example
client, submit the form, open every page and check for errors. It also checks
that submitting a blank form shows an error. I also clicked through the real
app in a headless browser (Playwright) and checked the screenshots.

### Why these choices

- **The app is a thin layer.** All the finance logic lives in the `riskfit`
  package, which has its own tests. The app only collects inputs and displays
  results. So the same logic serves the app, the PDF and the tests, and the
  numbers on screen always match the PDF.
- **Show *why*, not just *what*.** The "highest level allowed" table and the
  "allowed range" column let an RM explain the result to a client or a
  compliance reviewer. In private banking, being able to justify a
  recommendation matters as much as the recommendation itself.
- **Matplotlib charts, shared with the PDF**, so the client sees the same
  visuals on screen and on paper.
- **A form (`st.form`)** so the app only recalculates when the RM presses the
  button, not after every single answer.
- **No blank defaults.** For a new client, every radio button starts empty
  and must be answered. Defaulting to an answer could quietly put a client in
  the wrong profile, which would be a suitability failure.

### Interview questions

**Q1. How does the app keep track of the client between pages?**
> Streamlit re-runs the page script from top to bottom on every interaction,
> so normal variables are lost. I store the client's `Proposal` object in
> `st.session_state`, which lasts for the browser session. The questionnaire
> page creates it, and the other pages read it. If someone opens the
> portfolio page first, a helper function notices there's no proposal and
> shows a link back to the questionnaire. I also cache the expensive,
> client-independent work, such as loading prices and estimating the
> covariance matrix, with `@st.cache_data`, so it only runs once.

**Q2. Why did you separate the app from the calculation code?**
> So each part can be tested and reused on its own. The `riskfit` package
> does scoring, optimisation, stress tests and the PDF, and has over 90 unit
> tests. The app is just a user interface on top. The PDF generator and the
> app call the same `build_proposal()` function, so the numbers can't
> disagree. If the bank wanted a different front end later, for example
> inside their CRM, the core logic could be reused unchanged.

**Q3. What would you add before relationship managers used this for real?**
> Log-in and an audit trail: who ran which proposal, when, with which data
> and assumptions. A record of the client's signed answers. Validation
> against the client's full financial situation and existing holdings, not
> just one pot of money. The bank's approved product list instead of ETF
> proxies. Hosting inside the bank's network, because client data is
> confidential under Hong Kong's privacy law (PDPO). Finally, a review by
> compliance of all client-facing wording.

---

## Phase 6: Testing, the README, and presenting the project

### What was done

- **README.md**, written for recruiters: a one-paragraph summary, screenshots
  of the app and a sample PDF, how to run it, the methodology, key results
  (the 2008 vs 2022 story), and an honest list of limitations.
- **Screenshots** in `docs/screenshots/`, captured automatically from the
  running app with Playwright, a browser-automation tool.
- **Final test pass: 97 tests** at the time, all passing (`pytest`). Phase 7 brought this to 112.

### How the project is tested

The tests are layered, from small and exact to broad and realistic:

| Layer | Example | What it protects against |
|---|---|---|
| Hand-checked maths | 100 → 120 → 90 must give a −25% drawdown; recovery is exactly 5 days | Formula mistakes |
| Rules | A short horizon must cap an aggressive client; band edges 8/9, 12/13… | Wrong suitability outcomes |
| Invariants | For every profile: weights sum to 1, limits respected, volatility ≤ target, cash ≥ liquidity floor | Optimiser bugs and edge cases |
| Calibration on real data | Each profile's worst crisis drawdown is within its loss limit | The questionnaire promising something the portfolio can't deliver |
| Output | Every example PDF is exactly one page and contains the disclaimer | Layout changes silently breaking the proposal |
| App smoke test | Submit an example client and open every page with no errors | Broken pages before a demo |

The unit tests use small hand-made data, so they are fast and don't need the
internet. The tests that need real data skip themselves if the price cache is
missing.

### How to present this project in 60 seconds

> "RiskFit is a tool that turns a client's risk questionnaire into a one-page
> portfolio proposal. It separates *willingness* to take risk from *ability*
> to take risk, using horizon and maximum loss, and takes the lower of the
> two. It then builds a four-asset portfolio with constrained mean-variance
> optimisation. I used forward-looking return assumptions and Ledoit-Wolf
> shrinkage, so it doesn't just chase past returns. Next it stress-tests the
> portfolio on 2008, COVID and 2022, after fees, and on three hypothetical
> shocks. The most interesting finding was 2022: because inflation pushed
> bonds and stocks down together, a Balanced portfolio lost more than in the
> COVID crash. The stress tests also showed that my first questionnaire was
> too optimistic about losses, so I recalibrated it. The output is a
> plain-English PDF for the client, in USD or HKD, with a Streamlit app
> around it and 112 tests."

### Interview questions

**Q1. Walk me through one design decision you changed because of what the data showed.**
> Three, actually. First, standard Ledoit-Wolf made cash look about four
> times riskier than it really is, so I applied the shrinkage to
> correlations only. Second, the optimiser held no gold at all. I added a
> small strategic floor, measured its cost, and checked in the stress tests
> that it helped a little. Third, and most important, the stress tests showed
> my Conservative portfolio fell about 13% in 2008, while the questionnaire placed
> clients who said "up to 5% loss" into it. I recalibrated the loss bands and
> added a test that re-checks this against real data. In a suitability
> context, a promise the portfolio can't keep is the worst kind of bug.

**Q2. What would you do with more time?**
> I already did a second round: global equities instead of US-only, fees and
> quarterly rebalancing, hypothetical shocks, HKD display and a sensitivity
> table (see Phase 7). Next I would widen the asset universe with Asian
> bonds and separate regional equity choices. I would make the costs more
> realistic, with different fees per asset class and rebalancing when weights
> drift by 5%. I would handle uncertainty in the return assumptions more
> formally, e.g. with resampling or Black-Litterman. On the product side, I
> would add true multi-currency support and a proper audit trail.

**Q3. How does this project relate to a role in private wealth management?**
> It mirrors the RM workflow: understand the client, match them to a
> suitable risk profile, propose an allocation, explain the risks honestly,
> and document it. Building it forced me to think about the parts that matter
> in practice. Suitability means willingness vs ability. Expectations should
> be a range, not a promise. Risk should be shown in dollars and recovery
> time, not just percentages. And clients should be told that diversification
> can fail, as it did in 2022. I'd see this as a way to show I can combine
> the analytics with clear client communication.


---

## Phase 7: Improvements

After the first version was finished, six weaknesses from its own Limitations
list were fixed. Every number in this file was updated to the new version.

### What changed

**1. Global equities instead of US-only** (`riskfit/config.py`, `riskfit/data/loader.py`)

The equity part is now a blend: **60% SPY (US), 30% EFA (other developed
markets), 10% EEM (emerging markets)**. `blend_index()` combines the three
ETFs' daily returns at those fixed weights into one "global equities" index.
The weights are close to a global index's regional split. All three ETFs
start by 2003, so the 2008 test still works.

What it changed: global equities returned about 8% a year over 2007–2026
(US alone: about 11%), fell 56% in 2008, and are slightly more volatile. So
each profile holds slightly less in equities than before, e.g. Balanced 52%
instead of 54%.

**2. Hong Kong options**

- **HKD display.** A client has a `currency` (USD or HKD). Amounts are
  entered and shown in that currency. Nothing is converted, because every
  result is a percentage, and under the peg (7.75–7.85 per USD) an HKD
  investor's percentage return is the same to within about 1.3%.
- **Hong Kong tilt.** A second equity mix puts 15% of the equity part into
  EWH (MSCI Hong Kong): SPY 50% / EFA 25% / EEM 10% / EWH 15%. The app
  re-estimates risk and re-runs every test with that mix. It barely changes
  the results (Balanced worst fall −32.4% vs −32.3%), because Hong Kong
  shares fell about as much as global shares in each crisis.
- **SFC suitability.** The README links the questionnaire to the SFC Code of
  Conduct: paragraph 5.1 ("know your client": financial situation, investment
  experience, investment objectives) and paragraph 5.2 (a recommendation must
  be reasonably suitable for the client). The questionnaire covers
  objectives, experience, risk tolerance, horizon and liquidity. It does not
  cover the client's full financial situation, and it is not a compliance tool.

**3. Hypothetical "what if" shocks** (`riskfit/stress_test/hypothetical.py`)

| Shock | Equities | Bonds | Cash | Gold |
|---|---|---|---|---|
| Interest rates rise 2% | −10% | −12% | 0% | −5% |
| Stagflation | −30% | −10% | 0% | +15% |
| Severe recession | −40% | +5% | 0% | 0% |

The portfolio's loss is its weights times the shocks. For Balanced
(52/43/0/5): rates −10.6%, stagflation −19.1%, recession −18.5%.

The −12% for bonds comes from **duration**: a bond fund's price falls by
roughly its duration times the rise in rates. AGG's duration is about 6
years, so 6 × 2% = 12%. The other numbers are judgement calls.

**4. Fees and quarterly rebalancing** (`riskfit/stress_test/metrics.py`)

`portfolio_returns()` now takes two settings:
- `rebalance="quarterly"`: weights **drift** with the markets and are reset
  to target on the first trading day of each quarter. Before, they were reset
  every day, which no real portfolio does.
- `annual_fee=0.01`: a 1% yearly fee, taken off in equal daily slices.

The proposal now shows the expected return **after** the fee (e.g. Balanced
5.5% before, 4.5% after).

What it changed, for the same portfolios:

| Profile | 2008 fall: no fee, daily | 2008 fall: 1% fee, quarterly | Recovery before | Recovery after |
|---|---|---|---|---|
| Conservative | −12.9% | −13.2% | 10 months | 12 months |
| Balanced | −30.7% | −32.3% | 13 months | 19 months |
| Aggressive | −50.8% | −51.7% | 26 months | 46 months |

**5. Sensitivity to the return assumptions** (`riskfit/optimiser/sensitivity.py`)

The optimiser is re-run with one building block changed at a time. Equity
weight of each profile:

| Case | Conservative | Mod. Conservative | Balanced | Mod. Aggressive | Aggressive |
|---|---|---|---|---|---|
| Base case | 17% | 32% | 52% | 70% | 88% |
| Equity premium 3% | 14% | 32% | 52% | 70% | 88% |
| Equity premium 5% | 20% | 33% | 52% | 70% | 88% |
| Bond premium 0.5% | 20% | 38% | 53% | 70% | 88% |

The mix hardly moves when the equity premium changes. The **volatility
target** decides how much equity a profile can hold, so the return assumption
only changes the expected return figure. The sensitive part is **bonds vs
cash** in the cautious profiles: with a bond premium of 0.5%, Moderately
Conservative moves from 58% bonds / 5% cash to 25% bonds / 32% cash, because
bonds no longer pay enough for their risk.

**6. Tests**: 112, up from 97. New ones cover the blend index, weight drift
and the quarterly reset, the fee, the shocks, the sensitivity cases, HKD
amounts, and the loss-limit calibration for both equity mixes.

### Why these choices

- **A fixed blend instead of a fifth and sixth asset class.** Letting the
  optimiser choose between US, developed and emerging shares would need
  separate return assumptions for each, which I can't justify. A fixed blend
  keeps four asset classes and one equity assumption.
- **EWH instead of the Tracker Fund (2800.HK).** EWH is listed in the US in
  USD, so it has the same trading days as the other ETFs. Mixing a Hong
  Kong-listed fund would mean aligning two holiday calendars and a currency.
- **No currency conversion.** Converting at a fixed 7.8 would add a step
  without changing any percentage. Showing the amounts in HKD is enough, and
  the limitation (the peg must hold) is stated.
- **Costs on by default.** Showing results before fees flatters them. The app
  still shows the no-fee, daily-rebalancing version in a comparison table, so
  the effect of the assumption is visible.
- **One-off shocks instead of simulated paths.** A weighted sum is easy to
  explain to a client and to check by hand. The cost is that it says nothing
  about how long the loss lasts.

### Interview questions

**Q1. Your quarterly-rebalanced, after-fee Aggressive portfolio took 46 months to recover from 2008, against 26 months before. Why such a big difference?**
> Two effects. The 1% fee compounds: over four years it takes about 4% off,
> and near the old peak the portfolio was climbing slowly, so a small
> shortfall adds many months. The second is rebalancing. With daily
> rebalancing the portfolio keeps buying shares all the way down and so owns
> more of them at the bottom, which speeds up the recovery. Quarterly
> rebalancing does that only four times a year. The fall itself is only about
> 1 percentage point deeper. So the lesson is that costs and rebalancing rules
> matter far more for *how long* a client is under water than for *how deep*,
> and a result quoted before fees can be much too optimistic about recovery.

**Q2. In your "rates rise 2%" shock, the Conservative portfolio loses 7% and the Aggressive one 10%. Why are they so close?**
> Because in that scenario bonds are the problem. I assume bonds fall 12%,
> which is duration of about 6 years times 2%, and shares fall 10%. The
> cautious profiles hold more bonds, so they are hit almost as hard as the
> aggressive ones. Four of the five profiles lose about 10%. Only cash
> protects, which is why the Conservative portfolio, with 36% cash, loses
> least. It's the same lesson as 2022: bonds reduce the risk of an equity
> crash, but they are the source of risk when rates rise. A "low-risk"
> label depends on which risk you mean.

**Q3. How do you know your recommended portfolios aren't just a product of your return assumptions?**
> I tested it. I re-ran the optimiser with the equity risk premium at 3% and
> 5% instead of 4%, and the weights of the three riskier profiles did not
> change at all. That's because each profile has a volatility target, and
> that target, with the weight limits, decides how much equity it can hold.
> The return assumption mainly changes the expected return I quote. The part
> that *is* sensitive is the bond and cash split for cautious clients: if I
> halve the bond premium, the Moderately Conservative portfolio swaps most of
> its bonds for cash. So I would tell a client that the equity share is
> robust, and that the choice between bonds and cash depends on how much
> extra yield bonds actually offer at the time.
