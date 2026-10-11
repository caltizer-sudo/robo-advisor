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
- **Arithmetic means** (used by the optimizer and the simulation): μ_arith ≈ μ_compound + σ²/2.
- **Volatilities:** the average of historical volatility (Sep 2000–Sep 2026, public index funds) and forward-looking survey volatility. Emerging markets uses the survey only.
- **Correlations:** a 50/50 blend of historical monthly correlations and the Horizon Actuarial 2026 survey average of 43 investment advisors. The **stress** matrix replaces the stock/bond and stock/TIPS correlations with their 2022–26 values (about +0.6 to +0.8), a period when stocks and bonds fell together.

## 2. Risk profile (`robo/risk.py`)

| Score | Components (weights) |
|---|---|
| Capacity, 0–100 | Horizon (50%): 70% from years until withdrawals start (full credit at 25+), 30% from years of withdrawals (full credit at 30+). Income stability (20%), emergency fund (15%), dependents (15%) |
| Willingness, 0–100 | Knowledge (10%), objective (20%), reaction to a 25% crash (25%), choice among five one-year outcome ranges taken from the actual frontier (30%), maximum tolerable loss (15%) |
| Combined | lower + 0.25 × (higher − lower) |

- **How the combined score is used:** it maps onto the frontier's volatility range: σ = σ_min + (score/100)^0.7 × (σ_cap − σ_min).
- **Why the cap:** σ_cap is the portfolio with the **highest expected compound return**. Beyond it, extra risk lowers expected growth, because volatility drag rises faster than the extra average return. With today's assumptions the cap is about 81% stocks.
- **Why the conservative combination rule:** a client who *wants* risk but cannot *afford* it shouldn't get it; a client who can afford risk but would panic-sell shouldn't either.

## 3. Optimization (`robo/optimizer.py`)

The frontier maximizes w·μ subject to w Σ wᵀ ≤ σ², at 41 volatility levels, with these guardrails:

- U.S. stocks ≥ 50% of the stock portion
- International developed ≤ 35% of the stock portion
- Emerging markets ≤ 15% of the stock portion
- TIPS ≤ 40% of the bond portion
- Cash between 2% and 30%
- Total stocks ≤ 95%

The guardrails exist because unconstrained mean-variance optimization amplifies small errors in the inputs. In the MCERS pension analysis (Q5), a 0.5-point change in expected returns moved the private-equity weight from 25% to 51%.

## 4. Glide path (`robo/planner.py::glide_path`)

Each year, capacity is recomputed with the remaining time horizon and the number of dependents still in or before college. Willingness answers stay fixed. The resulting combined score sets that year's target volatility and weights.

## 5. Monte Carlo (`robo/planner.py::simulate`)

- **Units:** everything is in real (today's) dollars.
- **Returns:** correlated lognormal draws for each asset class each year (2,000 paths), matched to the real arithmetic means and volatilities. The portfolio is rebalanced annually to the glide-path weights, minus the all-in fee.
- **Cash flows:** contributions are (savings rate + employer match) × income, with income growing at the chosen real rate. College costs and retirement withdrawals (spending minus Social Security) come out at the start of each year; contributions go in at the end.
- **Success:** spending is fully funded every year through the plan-to age.
- **Chance of outliving your money:** the probability of running out, weighting each scenario by the chance of being alive at the age the money runs out.
- **Advice solvers:** bisection on the same scenarios (common random numbers) finds the savings rate, the spending level and the retirement age that reach 85% success.

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
