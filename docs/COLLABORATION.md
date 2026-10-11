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
- Every dollar amount in the simulation is in real (today's) dollars.
- Each asset class keeps its color in every chart (`charts.ASSET_COLORS`, a validated categorical order). Don't recolor by rank.
- Any text containing `$` passed to `st.markdown`, a radio or a checkbox label must go through `md()` in `app.py`, or Streamlit renders it as LaTeX.

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
- [ ] The default persona shows a Growth portfolio (about 72% stocks), a success probability, and three advice levers.
- [ ] The stress toggle and the Social Security cut checkbox both change the results.
- [ ] Open the Streamlit Cloud link 5 minutes before presenting so it wakes up.
