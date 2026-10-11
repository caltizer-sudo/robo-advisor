# Changelog

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
