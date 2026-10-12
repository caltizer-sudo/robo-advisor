# Collaboration guide (humans and AI agents)

This repo is developed iteratively by Connor, Claude (Anthropic) and Perplexity Computer. To keep everyone in sync:

## Ground rules

1. **GitHub `main` is the only source of truth.** Pull before you start; never edit a stale copy.
2. **Keep changes small and focused,** with a commit message that says *what* changed and *why*. Update `CHANGELOG.md`.
3. **Run `pytest -q` and `streamlit run app.py` before pushing.** All tests must pass and no red error boxes may appear in any tab.
4. **Don't change numbers in code.** Market assumptions live only in `data/assumptions.json`. Changing a guardrail or scoring weight is a methodology change: update `docs/METHODOLOGY.md` in the same commit.
5. **Keep UI and logic separate.** `app.py` handles layout and widgets only. Calculations belong in `robo/` with a unit test.

## Invariants (tests enforce most of these)

- Weights sum to 1, are non-negative, and satisfy every guardrail in `optimizer.py`.
- Correlation matrices are symmetric and positive definite.
- `simulate()` with zero volatility matches a hand-computed closed form (`test_zero_volatility_matches_closed_form`).
- The recommended risk never exceeds the highest-compound-return portfolio (`planner.sigma_range`).
- **The stress test never changes the recommendation.** Weights always come from the base frontier (`test_stress_keeps_portfolio_and_lowers_success`).
- The glide path never re-risks with age, and the TIPS share of bonds respects `planner.tips_floor` (`test_tips_floor`).
- Every dollar amount in the simulation is in real (today's) dollars.
- **Advice must reproduce its target.** The solvers run on the same scenario set as the headline success rate and re-derive the glide path per candidate (`test_advice_reproduces_target_on_same_scenarios`); the retirement lever stays at least `planner.MIN_RETIREMENT_YEARS` inside the plan horizon (`test_retirement_solver_stays_inside_plan_horizon`).
- Each asset class keeps its color in every chart (`charts.ASSET_COLORS`, a validated categorical order). Don't recolor by rank.
- Any text containing `$` passed to `st.markdown`, `st.metric` (values too), a radio or a checkbox label must go through `md()` in `app.py`, or Streamlit renders it as LaTeX. Use the `stat()` helper for metrics; it escapes automatically.

## How to propose a change (AI agents)

State the **goal**, the **files touched**, and the **tests added or updated**. If a change alters a recommendation for the default persona (30-year-old, retire at 67), note the before/after allocation and success probability in the pull request.

## Backlog (ideas for the next iterations)

| Priority | Idea | Notes |
|---|---|---|
| High | Human-capital adjustment | Treat the present value of future earnings as a bond-like asset. This would justify more stocks for young savers; the current cap is about 81% stocks. |
| High | Downloadable PDF/CSV report of the recommendation | For the Canvas upload and the live demo |
| Medium | Taxes and account location (401(k) / Roth / taxable) | Tax drag, required minimum distributions, Roth-conversion hints |
| Medium | Spouse / joint planning | Joint life expectancy, spousal Social Security |
| Medium | Scenario compare (A vs. B side by side) | e.g., retire at 65 vs. 67 |
| Medium | Shareable link that saves inputs | `st.query_params` |
| Low | Assumption sliders (e.g., U.S. stock return ± 1%) | Shows how sensitive the advice is to the forecasts |
| Low | Dark mode, mobile layout polish | Charts already use one fixed palette |

## Release checklist (before the live session)

- [ ] `pytest -q` passes; the app loads with no errors in any tab.
- [ ] The default persona shows about 70% stocks (49% at 67), plan success of about 69%, and three advice levers on the Recommendation tab.
- [ ] The stress toggle leaves the allocation unchanged and lowers success (about 69% → 45%). The Social Security cut checkbox also changes the results.
- [ ] Open the Streamlit Cloud link 5 minutes before presenting so it wakes up.
- [ ] After any push that changes `robo/*`, check the live app, not just `pytest`. Streamlit Cloud hot-reloads `app.py` but can keep the old `robo/*` modules in memory; the symptom is a `TypeError`/`AttributeError` that does not reproduce locally (v0.3.0 hit this with `fan_chart`'s new `y_max` argument). Fix: **Manage app → Reboot app**, or bump the `redeploy-marker` comment in `requirements.txt`, which forces a full redeploy.
