# Changelog

## 0.2.0 (2026-10-11): methodology and UX fixes from Perplexity Computer's review (Claude)
- **Stress test redesigned:** the recommendation is always built from the base frontier. Stress re-runs the simulation with 2022–26 correlations and a replay of 2022 in the first year of retirement, and reports base vs. stress success. Default persona: 69% → 45%.
- **Inflation risk:** an AR(1) inflation process with asset pass-through; the optimizer now uses a real-return covariance. TIPS enter the frontier naturally.
- **TIPS floor:** the TIPS share of bonds rises from 15% to 40% into retirement.
- **Retirement-phase capacity:** horizon measured as the duration of the remaining goal; in retirement, capacity depends on horizon plus guaranteed-income coverage, phased in over the last 10 working years. Linear score mapping. Default persona glide path: 70% stocks now, 49% at 67, 35% at 90 (was 72% / 61% / 55%).
- **Benchmark:** Vanguard target-date reference points on the glide-path chart.
- **UX:**
  - Short metric labels; static context moved into captions (no misleading up-arrows).
  - Tables use `st.table`, so they wrap instead of clipping.
  - New "plan success + three levers" card at the top of the Recommendation tab.
- **Tests:** 11 (new: TIPS floor, stress never changes weights, inflation hits nominal bonds but not TIPS, glide path never re-risks).

## 0.1.1 (2026-10-11): first deployment (Perplexity Computer)
- Published to GitHub (`caltizer-sudo/robo-advisor`) and Streamlit Community Cloud; live URL added to the README.
- Verified on the deployed app: 8 tests pass, all five tabs render with no errors, the stress toggle and the Social Security cut both change the results. No code or assumption changes.

## 0.1.0 (2026-10-11): first working version (Claude)
- Six-asset-class assumptions from the Unit 3 analysis: forward-looking returns, plus volatilities and correlations blended from history and the Horizon 2026 survey; a 2022–26 stress matrix.
- Guard-railed efficient frontier; two-factor risk score mapped onto the frontier; risk capped at the highest-compound-return portfolio.
- Glide path that recomputes risk capacity every year.
- Monte Carlo in real dollars covering college goals, a bequest goal, a Social Security estimate (with optional 20% cut) and Gompertz longevity.
- Advice solvers: required savings rate, sustainable spending and retirement age, each at 85% success.
- Streamlit UI with 5 tabs, a comparison with Schwab Intelligent Portfolios, and methodology and limitations pages.
- 8 unit tests.
