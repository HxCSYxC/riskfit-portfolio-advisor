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

---

## Phase 3: Stress tests and risk measures

### What the code does

**`riskfit/stress_test/scenarios.py`** defines three historical crises and
replays each profile's *current* weights through them:

| Scenario | Window | What happened |
|---|---|---|
| Global Financial Crisis | 9 Oct 2007 – 9 Mar 2009 | US equities −55%; bonds +7%, gold +25% |
| COVID-19 crash | 19 Feb – 23 Mar 2020 | US equities −33% in five weeks; almost everything fell for a few days |
| 2022 inflation and rate shock | calendar year 2022 | US equities −18% **and** bonds −13%, together |

For each scenario it reports:
- **Return over the crisis**: from the first day to the last day of the window.
- **Maximum drawdown**: the largest fall from a peak to a later low inside the
  window. This can be worse than the return, because the portfolio may bounce
  back a little before the window ends.
- **Recovery time**: calendar days from the lowest point until the portfolio
  is back at its pre-crisis peak, using all the data *after* the crisis.
  "Not yet recovered" if that never happens.

The portfolio is rebalanced to its target weights every day, with no fees or taxes.

**`riskfit/stress_test/metrics.py`** holds the maths: portfolio returns,
total return, drawdown, recovery, annualised volatility, historical VaR,
expected shortfall and rolling correlation.

**Results** (maximum drawdown, with recovery time in brackets):

| Profile | 2008 GFC | 2020 COVID | 2022 inflation |
|---|---|---|---|
| Conservative | −12.4% (10 months) | −8.6% (2 months) | −11.4% (14 months) |
| Moderately Conservative | −20.2% (12 months) | −14.2% (2 months) | −17.1% (17 months) |
| Balanced | −30.4% (13 months) | −19.8% (3 months) | −19.5% (14 months) |
| Moderately Aggressive | −40.9% (21 months) | −25.5% (4 months) | −21.2% (14 months) |
| Aggressive | −50.0% (26 months) | −30.8% (4 months) | −23.0% (14 months) |

**Full-period risk** (daily data, June 2007 – Oct 2026):

| Profile | Annual return | Annual volatility | 95% daily VaR | 95% daily ES |
|---|---|---|---|---|
| Conservative | 4.5% | 4.5% | −0.39% | −0.64% |
| Moderately Conservative | 6.3% | 7.5% | −0.67% | −1.10% |
| Balanced | 8.0% | 10.9% | −1.00% | −1.64% |
| Moderately Aggressive | 9.3% | 14.3% | −1.31% | −2.17% |
| Aggressive | 10.5% | 17.7% | −1.64% | −2.70% |

**Two charts** (in `docs/images/`):
- `stress_scenarios.png`: the value of 100 invested, through each crisis, for all five profiles.
- `stock_bond_correlation.png`: the rolling 3-year (36-month) correlation between SPY and AGG.

### What the stress tests changed

1. **Loss limits recalibrated.** In Phase 1, a client who answered "I can
   accept up to 5% loss" was put in the Conservative profile. But the
   Conservative portfolio actually fell **12.4%** in 2008. A proposal must not
   promise a loss limit that the portfolio has already broken. So each
   profile now has a `loss_limit` (15 / 25 / 35 / 45 / 60%) set just above its
   worst historical drawdown. The questionnaire's loss bands match these
   limits. A test (`test_profiles_stay_within_their_loss_limits`) re-checks
   this on the real data every time the tests run.
2. **The gold floor helped, a little.** Compared with the same profiles with
   no gold minimum, 5% gold reduced the maximum drawdown by about 0.3–0.7
   percentage points in 2008 and 2022, and made no difference in COVID. It is
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
shows this clearly. From 2012 to 2021 the 3-year correlation was mostly
between −0.45 and 0, so bonds diversified stocks. After 2022 it jumped to
about **+0.7**. In plain English: when inflation is the main risk, bonds and
stocks are hit by the same thing, so holding bonds does not cushion the fall.
This is why the Balanced portfolio lost almost as much in 2022 (−19.5%) as in
the COVID crash (−19.8%), and why the gaps between profiles were much smaller
in 2022 than in 2008.

One more honest detail. AGG includes corporate and mortgage bonds, which carry
credit risk. So even in 2008 its correlation with stocks briefly turned
*positive* (about +0.3). A Treasury-only fund would have looked more
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

**Q1. Why did the Balanced portfolio lose about as much in 2022 as in the COVID crash, even though stocks fell much less?**
> Because bonds didn't help in 2022. In COVID, bonds were roughly flat and
> cushioned part of the stock fall. In 2022 the shock was inflation, and the
> Fed raised rates quickly, so bond prices fell (AGG −13%) at the same time as
> stocks (−18%). A Balanced portfolio relies on bonds to offset equity losses.
> When both are hit by the same driver, rising rates, the diversification
> disappears. You can see it in the rolling 3-year stock–bond correlation: it
> went from negative for most of the 2010s to about +0.7 after 2022. For a
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
> stress-test drawdown ("in 2008 this portfolio fell about 30% and took about
> a year to recover"), because it is concrete and easy to picture.

**Q3. What are the limitations of historical stress testing?**
> It only shows crises that have already happened, and the next one will be
> different. The ETF data starts in 2007, so we can't test the 1970s
> inflation or the 2000 tech crash. I assume daily rebalancing with no costs,
> and real clients rebalance less often and pay fees. The tests use today's
> weights, which were chosen *after* those events, so there is some hindsight.
> And the proxies matter: AGG and SPY are US funds. In practice I would add
> hypothetical scenarios, such as "rates +200bp" or "equities −30% with bonds
> −10%", to cover risks the history doesn't contain. I also used the stress
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
| Mr Chan Tai Man, 62 | About to retire, may draw on savings | Conservative | Attitude suggests Moderately Conservative, but he can only accept a 15% loss |
| Ms Lee Ka Yan, 41 | Saving for retirement in ~20 years | Balanced | Attitude suggests Moderately Aggressive, but her loss limit is 35% |
| Mr Wong Siu Ming, 34 | Entrepreneur, may buy a flat next year | Aggressive, with 20% cash | High risk appetite and long horizon, but needs liquidity |

### Why these choices

- **One `build_proposal()` for both the PDF and the app**, so the numbers a
  client sees on screen and on paper can never disagree.
- **Plain English and money amounts.** "Your portfolio could have fallen by
  about USD 471,000" means more to a client than "maximum drawdown −31.4%".
  Showing USD amounts makes the risk real *before* it happens. That is the
  point of a suitability conversation.
- **Rounded numbers** (to the nearest USD 1,000 and whole percentages).
  Precise-looking figures like "USD 824,684" suggest false accuracy for
  something based on assumptions.
- **A comparison line (100% shares)** in the crisis chart gives the client a
  reference point, so they can see what diversification did for them.
- **The disclaimer is prominent** and lists the main simplifications: proxies,
  no fees or taxes, USD base, and past performance. In a regulated industry,
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
> range rather than one number: "about 5–6% a year on average, and most years
> between −6% and +17%". Finally the worst case in dollars: "in 2008 this mix
> would have fallen about 30%, or around USD 470,000 on your
> USD 1.5 million, and took about a year to recover." If they react badly to
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
