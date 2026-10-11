"""Two-factor risk profiling: risk CAPACITY (objective) and risk WILLINGNESS (subjective).

Design notes
------------
* Schwab Intelligent Portfolios weights the two scores equally (each out of 100). We instead use
  "the more conservative score, nudged 25% toward the other": combined = low + 0.25 * (high - low).
  A client who *wants* risk but cannot *afford* it should not get it; a client who can afford risk
  but loses sleep over it is likely to sell at the bottom.
* Capacity is recomputed every year in the projections, so the allocation glides down automatically
  as retirement approaches (an age-based de-risking path derived from the client's own inputs).
"""
from __future__ import annotations

from dataclasses import dataclass

NUDGE = 0.25

# ---------------------------------------------------------------- capacity (objective)
INCOME_STABILITY = {
    "Very stable (tenured, government, long-term contract)": 100,
    "Stable (salaried, private sector)": 75,
    "Variable (bonus/commission-heavy)": 40,
    "Unstable (new business, gig, at risk of layoff)": 15,
}
EMERGENCY_FUND = {"None": 0, "Less than 3 months": 35, "3 to 6 months": 75, "More than 6 months": 100}
CAPACITY_WEIGHTS = {"horizon": 0.50, "income": 0.20, "emergency": 0.15, "dependents": 0.15}
RETIRED_WEIGHTS = {"horizon": 0.60, "guaranteed": 0.40}
TRANSITION_YEARS = 10      # blend from working-life to retirement capacity over the last 10 years
HORIZON_FULL = 30.0        # a 30-year spending horizon earns full horizon credit


def horizon_score(years_to_retirement: float, years_in_retirement: float) -> float:
    """0-100 from the 'duration' of the remaining goal: years until withdrawals start plus half
    the years they last (the average time until each dollar is spent). Full credit at 30 years."""
    duration = max(years_to_retirement, 0.0) + max(years_in_retirement, 0.0) / 2
    return min(duration / HORIZON_FULL, 1.0) * 100


def dependents_score(n: int) -> float:
    return {0: 100, 1: 75, 2: 60}.get(int(n), 45)


def capacity_score(years_to_retirement: float, years_in_retirement: float, income_stability: str,
                   emergency_fund: str, dependents: int, guaranteed_share: float = 0.0) -> float:
    """Working-life capacity blends into retirement capacity over the final TRANSITION_YEARS.

    Working life: horizon, income stability, emergency fund, dependents.
    Retirement: horizon and the share of spending covered by guaranteed income (Social Security),
    because a paycheck no longer exists to absorb losses."""
    horizon = horizon_score(years_to_retirement, years_in_retirement)
    working = sum(CAPACITY_WEIGHTS[k] * v for k, v in {
        "horizon": horizon,
        "income": INCOME_STABILITY[income_stability],
        "emergency": EMERGENCY_FUND[emergency_fund],
        "dependents": dependents_score(dependents),
    }.items())
    retired = RETIRED_WEIGHTS["horizon"] * horizon + RETIRED_WEIGHTS["guaranteed"] * min(max(guaranteed_share, 0.0), 1.0) * 100
    w = min(max(1 - years_to_retirement / TRANSITION_YEARS, 0.0), 1.0)
    return (1 - w) * working + w * retired


# ---------------------------------------------------------------- willingness (subjective)
@dataclass(frozen=True)
class Question:
    key: str
    text: str
    options: tuple[str, ...]
    scores: tuple[float, ...]
    weight: float


WILLINGNESS_QUESTIONS: tuple[Question, ...] = (
    Question("knowledge", "How would you describe your investment knowledge?",
             ("None", "Limited", "Good", "Extensive"), (0, 33, 67, 100), 0.10),
    Question("goal", "Which statement best describes your main objective for this money?",
             ("Avoid losses, even if growth is low", "Balance growth and stability",
              "Maximize long-term growth; I can ride out big swings"), (0, 50, 100), 0.20),
    Question("drawdown", "The stock market falls 25% in three months, and your portfolio falls with it. What do you do?",
             ("Sell everything", "Sell some", "Do nothing", "Buy more"), (0, 30, 70, 100), 0.25),
    # "outcomes" options are generated from the efficient frontier at run time (see outcome_menu)
    Question("outcomes", "Which range of one-year outcomes would you choose for this account?",
             ("A", "B", "C", "D", "E"), (0, 25, 50, 75, 100), 0.30),
    Question("max_loss", "What is the largest one-year loss you could live with before changing your plan?",
             ("5%", "10%", "20%", "30%", "40% or more"), (0, 25, 50, 75, 100), 0.15),
)


def willingness_score(answers: dict[str, int]) -> float:
    """answers maps question key -> index of the chosen option."""
    return sum(q.weight * q.scores[answers[q.key]] for q in WILLINGNESS_QUESTIONS)


def combined_score(capacity: float, willingness: float) -> float:
    lo, hi = sorted((capacity, willingness))
    return lo + NUDGE * (hi - lo)


TOLERANCE = ((20, "Low"), (40, "Below average"), (60, "Average"), (80, "Above average"), (101, "High"))
# Portfolio names follow the stock-share bands Schwab uses, so the two robos compare like for like
PORTFOLIOS = ((0.25, "Conservative"), (0.40, "Moderately Conservative"), (0.55, "Moderate"),
              (0.70, "Moderate Growth"), (0.85, "Growth"), (1.01, "Aggressive Growth"))
MAPPING_EXPONENT = 1.0   # linear: keeps the spread between low, average and high scores


def profile_label(score: float) -> str:
    """Risk-tolerance label for a 0-100 combined score."""
    return next(label for cut, label in TOLERANCE if score < cut)


def portfolio_label(equity_share: float) -> str:
    return next(label for cut, label in PORTFOLIOS if equity_share < cut)


def target_sigma(score: float, sigma_lo: float, sigma_hi: float) -> float:
    """Map a 0-100 score onto the efficient frontier's volatility range (concave curve)."""
    s = min(max(score, 0.0), 100.0) / 100
    return sigma_lo + s**MAPPING_EXPONENT * (sigma_hi - sigma_lo)


OUTCOME_SIGMAS = (0.04, 0.065, 0.09, 0.115, 0.14)  # frontier points shown in the outcomes question


def conflict_note(capacity: float, willingness: float) -> str | None:
    gap = willingness - capacity
    if gap >= 25:
        return ("Your willingness to take risk is well above your capacity to absorb losses, so the "
                "recommendation leans toward your capacity.")
    if gap <= -25:
        return ("You can afford more risk than you are comfortable with. The recommendation leans toward "
                "your comfort level; the cost is lower expected growth.")
    return None
