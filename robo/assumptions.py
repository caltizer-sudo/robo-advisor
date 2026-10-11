"""Capital market assumptions for the robo-advisor's six asset classes.

All numbers live in data/assumptions.json (single source of truth). Returns there are
10-year nominal *compound* (geometric) expectations in percent; this module converts them
to decimals and derives arithmetic means and covariance matrices.

Because the planner works in REAL (today's) dollars, optimization uses a real-return covariance
that adds inflation risk: an inflation surprise lowers the real return of every asset in
proportion to (1 - pass-through). TIPS (pass-through 1) are the only full hedge, which is how
their purpose shows up in the risk model.
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
    vol: np.ndarray          # nominal annual volatility (decimal)
    corr: np.ndarray         # base correlation matrix
    corr_stress: np.ndarray  # stock/bond correlations at their 2022-26 levels
    inflation: float         # expected inflation (decimal)
    infl_vol: float          # long-run volatility of annual inflation (decimal)
    infl_persistence: float  # AR(1) coefficient of inflation surprises
    pass_through: np.ndarray # share of an inflation surprise absorbed by each asset's nominal return
    replay_2022: np.ndarray  # real 2022 returns (decimal) for the stress replay
    replay_surprise: float   # 2022 inflation minus expected inflation (decimal)
    as_of: str
    raw: dict

    @property
    def n(self) -> int:
        return len(self.keys)

    @property
    def equity_idx(self) -> list[int]:
        return [self.keys.index(k) for k in ("US_EQ", "INTL_DEV", "EM_EQ")]

    def idx(self, key: str) -> int:
        return self.keys.index(key)

    def arith(self) -> np.ndarray:
        """Nominal arithmetic mean ~= compound mean + variance / 2."""
        return self.geo + self.vol**2 / 2

    def real_arith(self) -> np.ndarray:
        return (1 + self.arith()) / (1 + self.inflation) - 1

    def cov(self, stress: bool = False) -> np.ndarray:
        """Nominal covariance (as in the Unit 3 analysis)."""
        c = self.corr_stress if stress else self.corr
        return np.outer(self.vol, self.vol) * c

    def cov_real(self, stress: bool = False) -> np.ndarray:
        """Real-return covariance: deflated nominal covariance + inflation-surprise risk."""
        exposure = 1.0 - self.pass_through
        return self.cov(stress) / (1 + self.inflation) ** 2 + self.infl_vol**2 * np.outer(exposure, exposure)

    def vol_real(self) -> np.ndarray:
        return np.sqrt(np.diag(self.cov_real()))

    def portfolio_stats(self, w: np.ndarray, stress: bool = False) -> dict:
        """Expected returns and risk of a portfolio. Volatility is in real terms."""
        w = np.asarray(w, dtype=float)
        mu = float(w @ self.real_arith())
        var = float(w @ self.cov_real(stress) @ w)
        real_geo = mu - var / 2
        return {
            "real_arith": mu,
            "vol": var**0.5,
            "real_geo": real_geo,
            "geo": (1 + real_geo) * (1 + self.inflation) - 1,   # nominal compound
            "equity": float(w[self.equity_idx].sum()),
        }


def load(path: Path | str = DATA_PATH) -> Assumptions:
    raw = json.loads(Path(path).read_text())
    cls = raw["classes"]
    keys = tuple(c["key"] for c in cls)
    corr = np.array(raw["corr"], dtype=float)
    corr_s = np.array(raw.get("corr_stress", raw["corr"]), dtype=float)
    for m in (corr, corr_s):
        if not np.allclose(m, m.T, atol=1e-8):
            raise ValueError("correlation matrix must be symmetric")
        if np.linalg.eigvalsh(m).min() <= 0:
            raise ValueError("correlation matrix must be positive definite")
    infl = raw["inflation"] / 100
    ir = raw.get("inflation_risk", {})
    pt = ir.get("pass_through", {})
    rp = raw.get("replay_2022", {})
    cpi = rp.get("cpi", raw["inflation"]) / 100
    nominal_2022 = np.array([rp.get("nominal", {}).get(k, 0.0) for k in keys]) / 100
    return Assumptions(
        keys=keys,
        names=tuple(c["name"] for c in cls),
        etfs=tuple(c["etf"] for c in cls),
        methods=tuple(c["method"] for c in cls),
        geo=np.array([c["exp_return"] for c in cls]) / 100,
        vol=np.array([c["vol"] for c in cls]) / 100,
        corr=corr,
        corr_stress=corr_s,
        inflation=infl,
        infl_vol=ir.get("vol", 0.0) / 100,
        infl_persistence=ir.get("persistence", 0.0),
        pass_through=np.array([pt.get(k, 0.0) for k in keys]),
        replay_2022=(1 + nominal_2022) / (1 + cpi) - 1,
        replay_surprise=cpi - infl,
        as_of=raw["as_of"],
        raw=raw,
    )
