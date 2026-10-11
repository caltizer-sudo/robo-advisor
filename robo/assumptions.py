"""Capital market assumptions for the robo-advisor's six asset classes.

All numbers live in data/assumptions.json (single source of truth). Returns there are
10-year nominal *compound* (geometric) expectations in percent; this module converts them
to decimals and derives arithmetic means and covariance matrices.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "assumptions.json"


@dataclass(frozen=True)
class Assumptions:
    keys: tuple[str, ...]
    names: tuple[str, ...]
    etfs: tuple[str, ...]
    methods: tuple[str, ...]
    geo: np.ndarray          # nominal compound expected return (decimal)
    vol: np.ndarray          # annual volatility (decimal)
    corr: np.ndarray         # base correlation matrix
    corr_stress: np.ndarray  # stock/bond correlations at their 2022-26 levels
    inflation: float         # decimal
    as_of: str
    raw: dict

    @property
    def n(self) -> int:
        return len(self.keys)

    @property
    def equity_idx(self) -> list[int]:
        return [self.keys.index(k) for k in ("US_EQ", "INTL_DEV", "EM_EQ")]

    def cov(self, stress: bool = False) -> np.ndarray:
        c = self.corr_stress if stress else self.corr
        return np.outer(self.vol, self.vol) * c

    def arith(self) -> np.ndarray:
        """Arithmetic mean ~= compound mean + variance / 2."""
        return self.geo + self.vol**2 / 2

    def real_arith(self) -> np.ndarray:
        """Arithmetic real mean (approximation: nominal arithmetic minus inflation)."""
        return self.arith() - self.inflation

    def portfolio_stats(self, w: np.ndarray, stress: bool = False) -> dict:
        w = np.asarray(w, dtype=float)
        mu = float(w @ self.arith())
        var = float(w @ self.cov(stress) @ w)
        return {
            "arith": mu,
            "vol": var**0.5,
            "geo": mu - var / 2,
            "real_geo": mu - var / 2 - self.inflation,
            "equity": float(w[self.equity_idx].sum()),
        }


def load(path: Path | str = DATA_PATH) -> Assumptions:
    raw = json.loads(Path(path).read_text())
    cls = raw["classes"]
    corr = np.array(raw["corr"], dtype=float)
    corr_s = np.array(raw.get("corr_stress", raw["corr"]), dtype=float)
    for m in (corr, corr_s):
        if not np.allclose(m, m.T, atol=1e-8):
            raise ValueError("correlation matrix must be symmetric")
        if np.linalg.eigvalsh(m).min() <= 0:
            raise ValueError("correlation matrix must be positive definite")
    return Assumptions(
        keys=tuple(c["key"] for c in cls),
        names=tuple(c["name"] for c in cls),
        etfs=tuple(c["etf"] for c in cls),
        methods=tuple(c["method"] for c in cls),
        geo=np.array([c["exp_return"] for c in cls]) / 100,
        vol=np.array([c["vol"] for c in cls]) / 100,
        corr=corr,
        corr_stress=corr_s,
        inflation=raw["inflation"] / 100,
        as_of=raw["as_of"],
        raw=raw,
    )
