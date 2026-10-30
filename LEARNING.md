# LEARNING.md: How RiskFit works, in plain English

This file explains each part of the project, why it was built that way, and the
questions an interviewer might ask about it. One section is added per phase.

---

## Phase 1: Data and questionnaire scoring

### What the code does

**`riskfit/config.py`** lists the four asset classes and the ETF that stands in for each:

| Asset class | ETF | Why this one |
|---|---|---|
| Equities | SPY (S&P 500) | Very liquid, history back to 1993. Global ETFs (ACWI, VT) only start in 2008, too late to test the 2008 crisis. So the equity sleeve is really *US* large-cap, and we say so. |
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
- an indicative **"bad year" loss**, used to match the client's own loss limit.

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
> investment-grade market, so it matches the label. The main limitation is
> equities: SPY is US-only, because global ETFs don't have data back to 2007.
> A real global equity allocation would differ, especially in currency exposure.
> Also, ETF data only goes back about 20 years, so it covers a small number of
> crises.

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

1. **Covariance matrix.** It uses month-end returns from June 2007 to October
   2026 (about 230 months) for all four ETFs and applies **Ledoit-Wolf
   shrinkage to the correlations**. Each asset keeps its own measured
   volatility (equities 15.5%, bonds 4.7%, cash 0.6%, gold 17.6% a year). The
   correlations are pulled 25% of the way towards zero. For example, the
   stock–bond correlation goes from 0.25 to 0.19.
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
| Conservative | 18.4% | 41.7% | 34.9% | 5.0% | 4.18% | 4.0% |
| Moderately Conservative | 34.1% | 55.9% | 5.0% | 5.0% | 4.95% | 6.5% |
| Balanced | 53.6% | 41.4% | 0.0% | 5.0% | 5.58% | 9.0% |
| Moderately Aggressive | 72.1% | 22.9% | 0.0% | 5.0% | 6.14% | 11.5% |
| Aggressive | 89.7% | 5.3% | 0.0% | 5.0% | 6.67% | 14.0% |

Each profile's weight limits cost less than 0.1% a year compared with the
unconstrained frontier.

### Why these choices

- **Forward-looking returns, not historical averages.** Mean-variance
  optimisation is very sensitive to expected returns. Historically, US
  equities returned about 11% a year from 2007 to 2026, and gold about 9%. Both
  were strong periods that may not repeat. An optimiser fed those numbers
  would put almost everything into US stocks. Building-block assumptions are
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
> it pulled correlations 25% of the way towards zero. I applied it to
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
