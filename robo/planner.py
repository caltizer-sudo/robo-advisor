"""Financial planning engine: glide path, Social Security, longevity, Monte Carlo, and solvers.

Everything is simulated in REAL (today's) dollars. Asset returns are drawn each year from a
correlated multivariate lognormal distribution whose arithmetic means and volatilities match the
capital market assumptions; the portfolio is rebalanced annually to that year's glide-path weights.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from functools import lru_cache
import math

import numpy as np

from . import risk
from .assumptions import Assumptions
from .optimizer import Frontier

# ------------------------------------------------------------------ Social Security (rough estimate)
SS_BEND_1, SS_BEND_2, SS_TAX_MAX = 1226.0, 7391.0, 176_100.0   # 2025 PIA bend points & taxable maximum
SS_FRA = 67


def social_security_estimate(income: float, claim_age: int) -> float:
    """Annual benefit in today's dollars, assuming a full career at today's real income.

    Uses the 2025 primary-insurance-amount formula (90% / 32% / 15% of average indexed monthly
    earnings) and the standard early/delayed claiming adjustments. A rough planning estimate only;
    the client's own SSA statement (ssa.gov/myaccount) is the better input."""
    aime = min(max(income, 0.0), SS_TAX_MAX) / 12
    pia = 0.9 * min(aime, SS_BEND_1) + 0.32 * max(min(aime, SS_BEND_2) - SS_BEND_1, 0) \
        + 0.15 * max(aime - SS_BEND_2, 0)
    months_early = max(SS_FRA - claim_age, 0) * 12
    months_late = max(min(claim_age, 70) - SS_FRA, 0) * 12
    factor = 1 - (5 / 900) * min(months_early, 36) - (5 / 1200) * max(months_early - 36, 0) \
        + (8 / 1200) * months_late
    return 12 * pia * factor


# ------------------------------------------------------------------ longevity (Gompertz approximation)
GOMPERTZ_MODE = {"Female": 90.0, "Male": 86.0, "Prefer not to say": 88.0}
GOMPERTZ_DISPERSION = 10.0


def survival(age: float, to_age: float | np.ndarray, sex: str = "Prefer not to say") -> np.ndarray:
    """Probability that someone alive at `age` is still alive at `to_age` (Gompertz law)."""
    m, b = GOMPERTZ_MODE[sex], GOMPERTZ_DISPERSION
    t = np.maximum(np.asarray(to_age, dtype=float) - age, 0.0)
    return np.exp(np.exp((age - m) / b) * (1 - np.exp(t / b)))


def life_expectancy(age: float, sex: str = "Prefer not to say") -> float:
    ages = np.arange(age, 121, 0.25)
    return float(age + np.trapezoid(survival(age, ages, sex), ages))


def planning_age(age: float, sex: str = "Prefer not to say", tail: float = 0.10) -> int:
    """First age at which the chance of still being alive drops below `tail` (default 10%)."""
    ages = np.arange(int(age), 121)
    s = survival(age, ages, sex)
    return int(min(ages[np.argmax(s < tail)], 105))


# ------------------------------------------------------------------ client profile
@dataclass(frozen=True)
class Child:
    age: int
    annual_cost: float          # today's dollars per year of college
    years: int = 4
    start_age: int = 18


@dataclass(frozen=True)
class Profile:
    age: int = 30
    retire_age: int = 67
    plan_age: int = 95
    sex: str = "Prefer not to say"
    savings: float = 25_000.0               # current investable assets
    income: float = 85_000.0                # gross annual income
    income_growth: float = 0.01             # real
    savings_rate: float = 0.10              # employee contribution, % of income
    later_savings_rate: float = 0.15
    later_from_age: int = 40
    employer_match: float = 0.04
    spending_mode: str = "replacement"      # "replacement" or "fixed"
    replacement: float = 0.75               # % of final pre-retirement income
    fixed_spending: float = 60_000.0        # today's dollars per year
    ss_annual: float | None = None          # None -> estimate
    ss_claim_age: int = 67
    ss_haircut: float = 0.0                 # e.g. 0.20 for a trust-fund shortfall scenario
    children: tuple[Child, ...] = ()
    college_real_growth: float = 0.01
    bequest: float = 0.0
    fee: float = 0.0005                     # all-in annual cost (fund expenses + advice)
    income_stability: str = "Stable (salaried, private sector)"
    emergency_fund: str = "3 to 6 months"

    @property
    def years(self) -> int:
        return self.plan_age - self.age

    def social_security(self) -> float:
        base = self.ss_annual if self.ss_annual is not None else social_security_estimate(self.income, self.ss_claim_age)
        return base * (1 - self.ss_haircut)

    def dependents_at(self, age: int) -> int:
        t = age - self.age
        return sum(1 for c in self.children if c.age + t < c.start_age + c.years)


# ------------------------------------------------------------------ glide path
TIPS_FLOOR_EARLY, TIPS_FLOOR_RETIRED, TIPS_RAMP_YEARS = 0.15, 0.40, 15


def spending_need(p: Profile) -> float:
    """Annual retirement spending goal in today's dollars."""
    if p.spending_mode != "replacement":
        return p.fixed_spending
    final_income = p.income * (1 + p.income_growth) ** max(p.retire_age - p.age - 1, 0)
    return p.replacement * final_income


def guaranteed_share(p: Profile) -> float:
    need = spending_need(p)
    return 1.0 if need <= 0 else min(p.social_security() / need, 1.0)


def capacity_at(p: Profile, age: int) -> float:
    return risk.capacity_score(p.retire_age - age, p.plan_age - max(age, p.retire_age),
                               p.income_stability, p.emergency_fund, p.dependents_at(age), guaranteed_share(p))


def tips_floor(years_to_retirement: float) -> float:
    """Minimum TIPS share of the bond sleeve: 15% early in a career, rising linearly over the last
    15 working years to 40% in retirement, when spending must keep pace with inflation."""
    if years_to_retirement >= TIPS_RAMP_YEARS:
        return TIPS_FLOOR_EARLY
    if years_to_retirement <= 0:
        return TIPS_FLOOR_RETIRED
    f = 1 - years_to_retirement / TIPS_RAMP_YEARS
    return TIPS_FLOOR_EARLY + f * (TIPS_FLOOR_RETIRED - TIPS_FLOOR_EARLY)


def apply_tips_floor(w: np.ndarray, a: Assumptions, floor: float) -> np.ndarray:
    b, t = a.idx("US_BOND"), a.idx("TIPS")
    sleeve = w[b] + w[t]
    if sleeve <= 0 or w[t] >= floor * sleeve:
        return w
    w = w.copy()
    w[t] = floor * sleeve
    w[b] = sleeve - w[t]
    return w


def sigma_range(fr: Frontier) -> tuple[float, float]:
    """Volatility range used for recommendations: from the minimum-variance portfolio up to the
    portfolio with the highest expected COMPOUND return. Beyond that point extra risk lowers
    expected growth (volatility drag), so the robo never recommends it."""
    j = int(np.argmax(fr.geo))
    return fr.sigma_min, float(fr.sigmas[j])


def glide_path(p: Profile, willingness: float, fr: Frontier, a: Assumptions) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (ages, combined scores, weights[len(ages), n_assets]) from today to plan_age - 1.
    Weights always come from the BASE frontier; stress tests never change the recommendation."""
    lo, hi = sigma_range(fr)
    ages = np.arange(p.age, p.plan_age)
    scores = np.array([risk.combined_score(capacity_at(p, int(x)), willingness) for x in ages])
    W = np.array([apply_tips_floor(fr.at_sigma(risk.target_sigma(sc, lo, hi)), a, tips_floor(p.retire_age - x))
                  for sc, x in zip(scores, ages)])
    return ages, scores, W


# ------------------------------------------------------------------ cash flows
def cash_flows(p: Profile) -> dict[str, np.ndarray]:
    """Real cash flows per simulation year (index t = age - p.age)."""
    T = p.years
    ages = np.arange(p.age, p.plan_age)
    working = ages < p.retire_age
    income = p.income * (1 + p.income_growth) ** np.arange(T) * working
    rate = np.where(ages < p.later_from_age, p.savings_rate, p.later_savings_rate)
    contrib = income * (rate + p.employer_match)
    need = spending_need(p)
    spending = np.where(ages >= p.retire_age, need, 0.0)
    ss = np.where(ages >= p.ss_claim_age, p.social_security(), 0.0)
    withdraw = np.where(ages >= p.retire_age, np.maximum(spending - ss, 0.0), 0.0)
    college = np.zeros(T)
    for c in p.children:
        for k in range(c.years):
            t = c.start_age + k - c.age
            if 0 <= t < T:
                college[t] += c.annual_cost * (1 + p.college_real_growth) ** t
    return {"ages": ages, "income": income, "contrib": contrib, "spending": spending, "ss": ss,
            "withdraw": withdraw, "college": college, "need": np.array(need)}


# ------------------------------------------------------------------ Monte Carlo
@lru_cache(maxsize=8)
def _shocks(paths: int, years: int, n: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).standard_normal((paths, years, n))


def asset_returns(a: Assumptions, years: int, paths: int = 2000, stress: bool = False, seed: int = 7,
                  replay_at: int | None = None) -> np.ndarray:
    """Real annual asset returns, shape (paths, years, n_assets).

    1. Correlated lognormal draws matched to each asset's real arithmetic mean and (deflated) volatility.
    2. Inflation surprises follow an AR(1) process; each asset's real return falls by
       (1 - pass-through) x surprise, so nominal bonds and stocks lose in inflation shocks and TIPS don't.
    3. Optional stress replay: year `replay_at` repeats 2022 (real returns of every asset class), and
       the 2022 inflation surprise then decays at the AR(1) rate in later years.
    """
    mu = a.real_arith()
    sd = a.vol / (1 + a.inflation)
    s2 = np.log(1 + sd**2 / (1 + mu) ** 2)
    m = np.log(1 + mu) - s2 / 2
    L = np.linalg.cholesky(a.corr_stress if stress else a.corr)
    raw = _shocks(paths, years, a.n + 1, seed)
    z = raw[:, :, : a.n] @ L.T
    R = np.exp(m + np.sqrt(s2) * z) - 1
    if a.infl_vol > 0:
        phi = a.infl_persistence
        e = raw[:, :, a.n] * a.infl_vol * np.sqrt(1 - phi**2)
        u = np.empty((paths, years))
        u[:, 0] = a.replay_surprise if replay_at == 0 else raw[:, 0, a.n] * a.infl_vol  # stationary start
        for t in range(1, years):
            u[:, t] = a.replay_surprise if t == replay_at else phi * u[:, t - 1] + e[:, t]
        R = R - u[:, :, None] * (1 - a.pass_through)[None, None, :]
    if replay_at is not None and 0 <= replay_at < years:
        R[:, replay_at, :] = a.replay_2022
    return R


@dataclass
class SimResult:
    ages: np.ndarray               # length T+1 (wealth at start of each age, plus plan end)
    wealth: np.ndarray             # (paths, T+1)
    success: float                 # P(no spending shortfall through plan_age)
    bequest_prob: float
    depletion_age: np.ndarray      # per path; np.inf if never depleted
    ruin_while_alive: float        # survival-weighted probability of running out
    pct: dict = field(default_factory=dict)


def simulate(p: Profile, W: np.ndarray, R: np.ndarray, flows: dict | None = None) -> SimResult:
    flows = cash_flows(p) if flows is None else flows
    T = p.years
    port = np.einsum("pyk,yk->py", R[:, :T, :], W[:T]) - p.fee
    P = port.shape[0]
    wealth = np.empty((P, T + 1))
    wealth[:, 0] = p.savings
    failed_at = np.full(P, np.inf)
    out = flows["withdraw"] + flows["college"]
    for t in range(T):
        w = wealth[:, t] - out[t]
        short = w < 0
        newly = short & np.isinf(failed_at)
        failed_at[newly] = p.age + t
        w = np.maximum(w, 0.0)
        wealth[:, t + 1] = w * (1 + port[:, t]) + flows["contrib"][t]
    ages = np.arange(p.age, p.plan_age + 1)
    success = float(np.isinf(failed_at).mean())
    beq = float((np.isinf(failed_at) & (wealth[:, -1] >= p.bequest)).mean())
    alive = survival(p.age, np.where(np.isinf(failed_at), p.plan_age + 50, failed_at), p.sex)
    ruin_alive = float(np.where(np.isinf(failed_at), 0.0, alive).mean())
    pct = {q: np.percentile(wealth, q, axis=0) for q in (10, 25, 50, 75, 90)}
    return SimResult(ages, wealth, success, beq, failed_at, ruin_alive, pct)


# ------------------------------------------------------------------ solvers (bisection on common shocks)
def _bisect(f, lo, hi, target, iters=18, increasing=True):
    flo, fhi = f(lo), f(hi)
    if increasing and fhi < target:
        return None
    if not increasing and flo < target:
        return None
    for _ in range(iters):
        mid = (lo + hi) / 2
        ok = f(mid) >= target
        if increasing:
            lo, hi = (lo, mid) if ok else (mid, hi)
        else:
            lo, hi = (mid, hi) if ok else (lo, mid)
    return hi if increasing else lo


def required_savings_rate(p: Profile, W, R, target=0.85) -> float | None:
    """Constant employee savings rate (from today to retirement) that achieves `target` success."""
    def f(s):
        return simulate(replace(p, savings_rate=s, later_savings_rate=s), W, R).success
    return _bisect(f, 0.0, 0.60, target, increasing=True)


def sustainable_spending(p: Profile, W, R, target=0.85) -> float | None:
    """Retirement spending (today's dollars per year) that achieves `target` success."""
    hi = 4 * float(cash_flows(p)["need"]) + 50_000

    def f(x):
        return simulate(replace(p, spending_mode="fixed", fixed_spending=x), W, R).success
    return _bisect(f, 0.0, hi, target, increasing=False)


def retirement_age_needed(p: Profile, willingness: float, fr: Frontier, a: Assumptions, R, target=0.85, max_age=75) -> int | None:
    for ra in range(p.retire_age, max_age + 1):
        q = replace(p, retire_age=ra)
        _, _, W = glide_path(q, willingness, fr, a)
        if simulate(q, W, R).success >= target:
            return ra
    return None
