# Robo-Advisor (MSFO 6831, Unit 3)

**Live app:** <https://scqubx2arm6ms5putx6eyb.streamlit.app> · **Repo:** <https://github.com/caltizer-sudo/robo-advisor>

A goals-based robo-advisor built for Georgetown University's MSFO 6831 (Unit 3: Robo Advisers and the Montgomery County Employee Retirement System). It:

1. **Asks about the client's situation:** age, retirement age, savings, income and income growth, current and future savings rates, employer match, retirement spending goal, Social Security, college goals for children, a bequest goal, and fees.
2. **Measures risk tolerance on two scales:** *capacity* (objective: time horizon, income stability, emergency fund, dependents) and *willingness* (five behavioral questions).
3. **Turns the profile into a portfolio** on a mean-variance efficient frontier, with guardrails that keep weights diversified. The allocation shifts toward bonds automatically as retirement approaches.
4. **Shows the recommendation and projections:** allocation and example ETFs, an age-by-age allocation chart, and a Monte Carlo fan chart of savings in today's dollars (2,000 scenarios). It reports the probability the plan works, the chance of outliving the money, and three concrete adjustments that would close any shortfall (save more, spend less, or retire later).

Expected returns are **forward-looking** (built from yields and valuations as of Oct 9, 2026), not historical averages. See [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).

> Educational project. Not investment, tax or legal advice.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate     # optional
pip install -r requirements.txt
streamlit run app.py                                   # opens http://localhost:8501
pytest -q                                              # 11 unit tests
```

## Deploy (free) on Streamlit Community Cloud

1. Push this folder to a **public GitHub repository** (`app.py` at the repo root).
2. Go to <https://share.streamlit.io>, sign in with GitHub, click **Create app**, then choose the repo, the branch (`main`) and the main file (`app.py`).
3. Optionally pick a custom subdomain, then click **Deploy**. The app rebuilds on every push to `main`.
4. Apps go to sleep after a period of inactivity. Open the link a few minutes before presenting so it has time to wake up.

## Repository layout

```
app.py                     Streamlit UI (sidebar inputs + 5 tabs)
robo/assumptions.py        loads data/assumptions.json; arithmetic means, covariance
robo/optimizer.py          guard-railed efficient frontier (scipy SLSQP)
robo/risk.py               questionnaire, capacity/willingness scoring, score -> risk mapping
robo/planner.py            glide path, Social Security, longevity, Monte Carlo, solvers
robo/charts.py             Plotly figures (fixed asset-class colors)
data/assumptions.json      capital market assumptions: single source of truth
tests/test_core.py         unit tests (guardrails, scoring, SS formula, closed-form MC check, stress, TIPS, inflation)
docs/METHODOLOGY.md        formulas, assumptions and sources
docs/COLLABORATION.md      guide for AI agents and humans iterating on this repo
```

## Updating the market assumptions

Edit `data/assumptions.json` only: expected returns (`exp_return`, % compound), volatilities, correlations and `as_of`. `tests/test_core.py` checks that the correlation matrices remain valid (symmetric and positive definite). Nothing else needs to change.

## Credits

Built by Connor with Claude (Anthropic) and Perplexity Computer. The AI prompts used are documented in the course discussion post. Market data: U.S. Treasury, FRED, Yahoo Finance, iShares, multpl.com, and the Horizon Actuarial Services 2026 Survey of Capital Market Assumptions.
