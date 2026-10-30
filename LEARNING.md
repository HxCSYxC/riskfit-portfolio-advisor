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
  (from 4% a year up to 15%);
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
