# Methodology

## 1. Capital market assumptions (`data/assumptions.json`)

Expected returns are 10-year nominal **compound** returns, built from market prices as of Oct 8–9, 2026:

| Asset class | Exp. return | Volatility | How it was estimated |
|---|---|---|---|
| U.S. stocks | 5.31% | 16.0% | Dividend yield 1.04% + net buybacks 1.35% + real EPS growth 1.80% + inflation 2.35% − valuation drift 1.23%/yr (CAPE 41.9 → 37 over 10 years) |
| Intl. developed stocks | 6.64% | 17.4% | 3.09% + 0.50% + 1.20% + 2.35% − 0.50% |
| Emerging-market stocks | 5.51% | 22.7% | 1.66% − 1.00% (share issuance) + 3.00% + 2.35% − 0.50% |
| U.S. core bonds | 5.30% | 5.4% | Starting yield: 60% Treasuries (5.00%) / 40% IG corporates (5.74% after expected losses) |
| U.S. TIPS | 5.22% | 5.9% | 10-yr real yield 2.87% + expected inflation 2.35% |
| Cash / T-bills | 3.90% | 1.1% | 3-month bill 4.25%, fading halfway toward a 3.5% long-run rate |

- **Inflation:** 2.35%, from the 10-year breakeven (2.33%) and the 5-year, 5-year-forward rate (2.32%).
- **Arithmetic means** (used by the optimizer and the simulation): μ_arith ≈ μ_compound + σ²/2. Real means: (1 + μ_arith) / (1 + π) − 1.
- **Volatilities:** the average of historical volatility (Sep 2000–Sep 2026, public index funds) and forward-looking survey volatility. Emerging markets uses the survey only.
- **Correlations:** a 50/50 blend of historical monthly correlations and the Horizon Actuarial 2026 survey average of 43 investment advisors. The **stress** matrix replaces the stock/bond and stock/TIPS correlations with their 2022–26 values (about +0.6 to +0.8), a period when stocks and bonds fell together.

## 2. Inflation risk and TIPS

The planner works in real (today's) dollars, so inflation surprises are a risk, not a constant.

- **Inflation process:** annual surprises follow an AR(1) process with persistence 0.6 and long-run volatility 1.95% (Horizon 2026 survey).
- **Pass-through:** the share of a surprise each asset's nominal return absorbs within the year. TIPS 100% (principal indexed to CPI), T-bills 70% (yields reset quickly), stocks and nominal bonds 0% in the short run.
- **Real covariance used by the optimizer:** Σ_real = Σ_nominal / (1 + π)² + σ_π² × (1 − pass-through)(1 − pass-through)ᵀ. TIPS are the only full inflation hedge, so they now earn a place on the frontier: 15–31% of the portfolio at low-to-moderate risk.
- **TIPS floor:** a policy floor on the TIPS share of the bond sleeve: 15% when retirement is 15 or more years away, rising linearly to 40% at retirement and staying there. Retirement spending is a real liability, and TIPS are its natural hedge.
- **Why this changed in v0.2:** in v0.1, inflation was fixed. TIPS (5.22%, 5.9% volatility) then looked strictly dominated by core bonds (5.30%, 5.4%) and always got 0%.

## 3. Risk profile (`robo/risk.py`)

| Score | Components (weights) |
|---|---|
| Capacity, working years | Horizon (50%), income stability (20%), emergency fund (15%), dependents (15%) |
| Capacity, retirement | Horizon (60%) and the share of spending covered by guaranteed income, i.e. Social Security (40%) |
| Willingness, 0–100 | Knowledge (10%), objective (20%), reaction to a 25% crash (25%), choice among five one-year outcome ranges taken from the actual frontier (30%), maximum tolerable loss (15%) |
| Combined | lower + 0.25 × (higher − lower) |

- **Horizon** works like the duration of the remaining goal: (years until withdrawals start) + (years of withdrawals) / 2, with full credit at 30 years. It keeps falling throughout retirement.
- **Transition:** working-life capacity blends linearly into retirement capacity over the final 10 working years. This avoids a jump at the retirement date.
- **Why the allocation is flat early in a career:** horizon credit is capped once the goal's duration reaches 30 years. With a 30-year retirement, withdrawals contribute 15 years of duration, so the cap binds until about 15 years before retirement. For the default persona (retiring at 67, plan to 97), weights are identical from 30 through 52 and start declining at 53, 14 years out; the decline steepens once the 10-year transition to retirement capacity begins at 57. This is deliberate: an extra year of horizon matters little when the money is 30+ years from being spent. Target-date funds likewise hold a constant stock share early in a career.
- **Mapping:** the combined score maps **linearly** onto the frontier's volatility range: σ = σ_min + score/100 × (σ_cap − σ_min).
- **The cap:** σ_cap is the portfolio with the highest expected compound return, about 83% stocks today. Beyond it, extra risk lowers expected growth.
- **Resulting glide paths** (stock share at ages 30 / 67 / 80 / 90):

  | Willingness | 30 | 67 | 80 | 90 |
  |---|---|---|---|---|
  | High (78) | 70% | 49% | 42% | 35% |
  | Average (50) | 54% | 44% | 36% | 29% |
  | Low (25) | 40% | 29% | 26% | 22% |

  For comparison, Vanguard's target-date path is 90% stocks at 25, 50% at 65 and 30% from 72; its reference points appear on the app's glide-path chart. Our young-investor equity is lower because the robo honors stated willingness, and because the frontier is flat at today's valuations.

## 4. Optimization (`robo/optimizer.py`)

The frontier maximizes real expected return w·μ subject to w Σ_real wᵀ ≤ σ², at 41 volatility levels, with these guardrails:

- U.S. stocks ≥ 50% of the stock portion
- International developed ≤ 35% of the stock portion
- Emerging markets ≤ 15% of the stock portion
- TIPS ≤ 40% of the bond portion
- Cash between 2% and 30%
- Total stocks ≤ 95%

The guardrails exist because unconstrained mean-variance optimization amplifies small errors in the inputs. In the MCERS pension analysis (Q5), a 0.5-point change in expected returns moved the private-equity weight from 25% to 51%.

## 5. Monte Carlo and the stress test (`robo/planner.py`)

- **Base case:** each year, draw correlated lognormal real returns matched to the real arithmetic means and deflated volatilities. Subtract (1 − pass-through) × the inflation surprise. Rebalance to that year's glide-path weights and deduct fees. 2,000 paths, real dollars.
- **Cash flows:** contributions go in at year end; college costs and retirement withdrawals (spending minus Social Security) come out at the start of the year.
- **Success:** spending is fully funded every year through the plan-to age.
- **Advice solvers:** bisection on common random numbers finds the savings rate, spending level and retirement age that reach 85% success.
- **Stress test (v0.2 redesign):** the stress test **never changes the recommended portfolio.** It re-runs the same glide path with:
  1. **2022–26 correlations:** stocks with bonds and TIPS at about +0.6 to +0.9.
  2. **A replay of calendar 2022 in the first year of retirement**, when sequence risk is greatest. Real returns: U.S. stocks −24%, international −21%, core bonds −17%, TIPS −17%, cash −4%, with 6.4% CPI. The 2022 inflation surprise (+4.05 points) then decays at the AR(1) rate.
- **What it reports:** base vs. stressed plan success and the change in points. For the default persona: 69% → 45%.
- **Why it changed in v0.1 → v0.2:** v0.1 re-optimized the frontier on the stress matrix. Bonds lost their diversification value, so the same score mapped to *more* stocks (82% vs. 72%), which users would read as a bug.

## 6. Social Security and longevity

- **Social Security:** the 2025 primary-insurance-amount formula, with bend points of $1,226 and $7,391 of average indexed monthly earnings and a $176,100 taxable maximum.
  - The estimate assumes a full career at today's real income, with full retirement age 67.
  - Claiming early reduces the benefit by 5/9% a month for the first 36 months and 5/12% a month after that; delaying adds 8% a year up to age 70.
  - An optional scenario cuts benefits 20%.
- **Longevity:** Gompertz survival, S(x→y) = exp(e^{(x−m)/b} (1 − e^{(y−x)/b})).
  - Modal age m = 86 for men, 90 for women and 88 if sex is unspecified; dispersion b = 10.
  - The default plan-to age is the first age at which survival drops below 10%.

## 7. Sources

- Unit 3 capital market assumptions (Q1) and risk model (Q2–Q3).
- U.S. Treasury Daily Par Yield Curve (Oct 9, 2026). FRED: T10YIE, T5YIFR, DFII10, DTB3, BAMLC0A0CMEY.
- multpl.com: Shiller CAPE 41.87 and dividend yield 1.04% (Oct 9, 2026). chartrow.com: S&P 500 net buyback yield 1.35%.
- iShares EFA / EEM fund pages (trailing 12-month yields and P/E ratios).
- Horizon Actuarial Services, *Survey of Capital Market Assumptions*, 2026 Edition (Exhibit 17).
- Yahoo Finance monthly total returns (VTSMX, VGTSX, VFITX, VFICX, VIPSX), Sep 2000–Sep 2026.
- Schwab Intelligent Portfolios sample allocations (schwab.com/intelligent-portfolios), used in the comparison panel.
