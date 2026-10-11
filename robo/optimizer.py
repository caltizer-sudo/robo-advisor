"""Mean-variance efficient frontier with guardrails.

Lesson from the MCERS analysis (Q5): unconstrained mean-variance optimization amplifies small
errors in expected returns into extreme, unstable weights. The robo therefore optimizes only
inside "guardrails" that keep portfolios diversified and close to market weights:

* U.S. stocks >= 50% of the equity sleeve; international developed <= 35%; emerging <= 15%
* TIPS <= 40% of the bond sleeve
* Cash between 2% and 30%; total equity <= 95%
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize

from .assumptions import Assumptions

CASH_MIN, CASH_MAX, EQUITY_MAX = 0.02, 0.30, 0.95


def _constraints(a: Assumptions) -> list[dict]:
    k = {key: i for i, key in enumerate(a.keys)}
    us, dev, em, bond, tips = k["US_EQ"], k["INTL_DEV"], k["EM_EQ"], k["US_BOND"], k["TIPS"]

    def eq(w):
        return w[us] + w[dev] + w[em]

    return [
        {"type": "eq", "fun": lambda w: w.sum() - 1.0},
        {"type": "ineq", "fun": lambda w: w[us] - 0.50 * eq(w)},
        {"type": "ineq", "fun": lambda w: 0.35 * eq(w) - w[dev]},
        {"type": "ineq", "fun": lambda w: 0.15 * eq(w) - w[em]},
        {"type": "ineq", "fun": lambda w: 0.40 * (w[bond] + w[tips]) - w[tips]},
        {"type": "ineq", "fun": lambda w: EQUITY_MAX - eq(w)},
    ]


def _bounds(a: Assumptions) -> list[tuple[float, float]]:
    return [(CASH_MIN, CASH_MAX) if key == "CASH" else (0.0, 1.0) for key in a.keys]


def _start(a: Assumptions) -> np.ndarray:
    w = np.array([0.30, 0.15, 0.05, 0.30, 0.15, 0.05])
    return w / w.sum()


def min_variance(a: Assumptions, stress: bool = False) -> np.ndarray:
    S = a.cov(stress)
    r = minimize(lambda w: w @ S @ w, _start(a), jac=lambda w: 2 * S @ w, method="SLSQP",
                 bounds=_bounds(a), constraints=_constraints(a), options={"ftol": 1e-12, "maxiter": 500})
    return _clean(r.x)


def max_return(a: Assumptions) -> np.ndarray:
    mu = a.arith()
    r = minimize(lambda w: -(w @ mu), _start(a), jac=lambda w: -mu, method="SLSQP",
                 bounds=_bounds(a), constraints=_constraints(a), options={"ftol": 1e-12, "maxiter": 500})
    return _clean(r.x)


def max_return_at_vol(a: Assumptions, sigma: float, stress: bool = False, x0=None) -> np.ndarray:
    S, mu = a.cov(stress), a.arith()
    cons = _constraints(a) + [{"type": "ineq", "fun": lambda w: sigma**2 - w @ S @ w,
                               "jac": lambda w: -2 * S @ w}]
    r = minimize(lambda w: -(w @ mu), _start(a) if x0 is None else x0, jac=lambda w: -mu,
                 method="SLSQP", bounds=_bounds(a), constraints=cons, options={"ftol": 1e-12, "maxiter": 500})
    return _clean(r.x)


def _clean(w: np.ndarray) -> np.ndarray:
    w = np.clip(w, 0, None)
    w[w < 1e-6] = 0.0
    return w / w.sum()


@dataclass(frozen=True)
class Frontier:
    sigmas: np.ndarray     # realized volatility of each frontier portfolio
    weights: np.ndarray    # (n_points, n_assets)
    arith: np.ndarray
    geo: np.ndarray

    @property
    def sigma_min(self) -> float:
        return float(self.sigmas[0])

    @property
    def sigma_max(self) -> float:
        return float(self.sigmas[-1])

    def at_sigma(self, sigma: float) -> np.ndarray:
        """Weights at a target volatility, linearly interpolated between frontier points.
        Interpolated weights still satisfy every (linear) guardrail."""
        s = float(np.clip(sigma, self.sigmas[0], self.sigmas[-1]))
        j = int(np.searchsorted(self.sigmas, s))
        if j == 0:
            return self.weights[0].copy()
        lo, hi = self.sigmas[j - 1], self.sigmas[j]
        t = 0.0 if hi == lo else (s - lo) / (hi - lo)
        w = (1 - t) * self.weights[j - 1] + t * self.weights[j]
        return w / w.sum()


def frontier(a: Assumptions, n: int = 41, stress: bool = False) -> Frontier:
    w_lo, w_hi = min_variance(a, stress), max_return(a)
    S = a.cov(stress)
    s_lo, s_hi = float(np.sqrt(w_lo @ S @ w_lo)), float(np.sqrt(w_hi @ S @ w_hi))
    W, x0 = [w_lo], w_lo
    for s in np.linspace(s_lo, s_hi, n)[1:-1]:
        x0 = max_return_at_vol(a, s, stress, x0)
        W.append(x0)
    W.append(w_hi)
    W = np.array(W)
    sig = np.sqrt(np.einsum("ij,jk,ik->i", W, S, W))
    order = np.argsort(sig)
    W, sig = W[order], sig[order]
    ar = W @ a.arith()
    return Frontier(sigmas=sig, weights=W, arith=ar, geo=ar - sig**2 / 2)
