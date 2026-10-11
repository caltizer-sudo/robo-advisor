import numpy as np
import pytest
from dataclasses import replace

from robo import assumptions, optimizer, planner, risk


@pytest.fixture(scope="module")
def model():
    a = assumptions.load()
    return a, optimizer.frontier(a)


def test_assumptions_valid(model):
    a, _ = model
    assert a.n == 6 and np.all(a.vol > 0)
    for c in (a.corr, a.corr_stress):
        assert np.allclose(c, c.T) and np.linalg.eigvalsh(c).min() > 0
    # arithmetic = compound + variance / 2
    assert np.allclose(a.arith() - a.geo, a.vol**2 / 2)


def test_frontier_guardrails(model):
    a, fr = model
    k = {key: i for i, key in enumerate(a.keys)}
    for w in fr.weights:
        eq = w[[k["US_EQ"], k["INTL_DEV"], k["EM_EQ"]]].sum()
        assert abs(w.sum() - 1) < 1e-6 and w.min() >= -1e-9
        assert w[k["US_EQ"]] >= 0.5 * eq - 1e-6
        assert w[k["INTL_DEV"]] <= 0.35 * eq + 1e-6 and w[k["EM_EQ"]] <= 0.15 * eq + 1e-6
        assert w[k["TIPS"]] <= 0.40 * (w[k["US_BOND"]] + w[k["TIPS"]]) + 1e-6
        assert optimizer.CASH_MIN - 1e-6 <= w[k["CASH"]] <= optimizer.CASH_MAX + 1e-6
        assert eq <= optimizer.EQUITY_MAX + 1e-6
    assert np.all(np.diff(fr.sigmas) >= -1e-9)          # sorted by risk
    assert np.all(np.diff(fr.arith) >= -1e-6)           # more risk, more arithmetic return


def test_risk_scores_monotonic():
    base = dict(years_in_retirement=28, income_stability="Stable (salaried, private sector)",
                emergency_fund="3 to 6 months", dependents=0)
    caps = [risk.capacity_score(y, **base) for y in (0, 5, 15, 30)]
    assert caps == sorted(caps)
    low = risk.willingness_score({q.key: 0 for q in risk.WILLINGNESS_QUESTIONS})
    high = risk.willingness_score({q.key: len(q.options) - 1 for q in risk.WILLINGNESS_QUESTIONS})
    assert low == 0 and high == pytest.approx(100)
    assert risk.combined_score(90, 40) == pytest.approx(40 + 0.25 * 50)
    assert risk.profile_label(10) == "Low" and risk.profile_label(95) == "High"
    assert risk.portfolio_label(0.72) == "Growth" and risk.portfolio_label(0.10) == "Conservative"


def test_social_security_formula():
    # AIME = 85,000/12 = 7,083.33; PIA = 0.9*1226 + 0.32*(7083.33-1226) = 2,977.75/month at 67
    assert planner.social_security_estimate(85_000, 67) == pytest.approx(12 * 2977.75, rel=1e-4)
    assert planner.social_security_estimate(85_000, 62) == pytest.approx(0.70 * 12 * 2977.75, rel=1e-4)
    assert planner.social_security_estimate(85_000, 70) == pytest.approx(1.24 * 12 * 2977.75, rel=1e-4)


def test_survival_decreasing():
    s = planner.survival(30, np.arange(30, 111))
    assert s[0] == pytest.approx(1.0) and np.all(np.diff(s) <= 0) and s[-1] < 0.01
    assert 75 < planner.life_expectancy(30) < 90


def test_glide_path_derisks(model):
    a, fr = model
    p = planner.Profile()
    _, scores, W = planner.glide_path(p, willingness=80, fr=fr)
    eq = W[:, :3].sum(1)
    assert eq[0] > eq[p.retire_age - p.age] and scores[0] >= scores[-1]


def test_zero_volatility_matches_closed_form():
    """With no risk, simulated wealth must equal a hand-computed annuity."""
    p = planner.Profile(age=60, retire_age=61, plan_age=62, savings=100_000, income=50_000, savings_rate=0.10,
                        later_savings_rate=0.10, employer_match=0.0, spending_mode="fixed", fixed_spending=20_000,
                        ss_annual=0.0, ss_claim_age=70, fee=0.0)
    R = np.full((5, 2, 6), 0.03)
    W = np.tile(np.array([0, 0, 0, 0, 0, 1.0]), (2, 1))
    res = planner.simulate(p, W, R)
    year1 = 100_000 * 1.03 + 5_000          # end of working year: growth + contribution
    year2 = (year1 - 20_000) * 1.03          # retirement year: withdraw at start, then grow
    assert res.wealth[0, -1] == pytest.approx(year2)
    assert res.success == 1.0


def test_solvers_consistent(model):
    a, fr = model
    p = planner.Profile()
    _, _, W = planner.glide_path(p, 80, fr)
    R = planner.asset_returns(a, p.years, paths=500)
    s = planner.required_savings_rate(p, W, R, 0.85)
    assert s is not None
    hit = planner.simulate(replace(p, savings_rate=s, later_savings_rate=s), W, R).success
    assert hit >= 0.85
