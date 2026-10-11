"""Plotly figures. Colors follow a fixed categorical order (validated for color-vision deficiency
on adjacent pairs); each asset class keeps its color everywhere in the app."""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from .assumptions import Assumptions
from .optimizer import Frontier

ASSET_COLORS = {"US_EQ": "#2a78d6", "INTL_DEV": "#eb6834", "EM_EQ": "#1baf7a",
                "US_BOND": "#eda100", "TIPS": "#e87ba4", "CASH": "#008300"}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
BLUE = "#2a78d6"
FONT = dict(family="Inter, -apple-system, Segoe UI, Helvetica, Arial, sans-serif", size=13, color=INK)


def _layout(fig: go.Figure, title: str, height: int = 360, **kw) -> go.Figure:
    fig.update_layout(title=dict(text=title, x=0, xanchor="left", font=dict(size=15)), height=height,
                      font=FONT, plot_bgcolor="white", paper_bgcolor="white",
                      margin=dict(l=20, r=30, t=50, b=20), hoverlabel=dict(bgcolor="white"), **kw)
    fig.update_xaxes(showgrid=False, linecolor=GRID, tickfont=dict(color=INK2), automargin=True)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, tickfont=dict(color=INK2), automargin=True)
    return fig


def allocation_bar(a: Assumptions, w: np.ndarray, title: str = "Recommended allocation") -> go.Figure:
    order = list(range(a.n))[::-1]
    fig = go.Figure(go.Bar(
        x=[w[i] * 100 for i in order], y=[a.names[i] for i in order], orientation="h",
        marker=dict(color=[ASSET_COLORS[a.keys[i]] for i in order]),
        text=[f"{w[i]*100:.1f}%" for i in order], textposition="outside", cliponaxis=False,
        customdata=[a.etfs[i] for i in order],
        hovertemplate="<b>%{y}</b><br>%{x:.1f}%<br>Example ETFs: %{customdata}<extra></extra>"))
    _layout(fig, title, height=300, showlegend=False)
    fig.update_xaxes(range=[0, max(w) * 100 * 1.25], ticksuffix="%", showgrid=True, gridcolor=GRID)
    fig.update_yaxes(showgrid=False)
    return fig


def glide_path_area(a: Assumptions, ages: np.ndarray, W: np.ndarray, retire_age: int, now_age: int) -> go.Figure:
    fig = go.Figure()
    for k in range(a.n):
        fig.add_trace(go.Scatter(
            x=ages, y=W[:, k] * 100, name=a.names[k], stackgroup="one", mode="lines",
            line=dict(width=0.5, color="white"), fillcolor=ASSET_COLORS[a.keys[k]],
            hovertemplate=f"{a.names[k]}: %{{y:.1f}}%<extra></extra>"))
    fig.add_vline(x=retire_age, line=dict(color=INK2, width=1, dash="dot"))
    fig.add_annotation(x=retire_age, y=102, text="Retirement", showarrow=False, font=dict(size=11, color=INK2), yanchor="bottom")
    fig.add_vline(x=now_age, line=dict(color=INK, width=1))
    _layout(fig, "How your allocation changes with age", height=420, hovermode="x unified",
            legend=dict(orientation="h", y=-0.22, x=0))
    fig.update_yaxes(range=[0, 108], ticksuffix="%", title=None)
    return fig


def fan_chart(ages: np.ndarray, pct: dict, retire_age: int, title: str) -> go.Figure:
    def band(lo, hi, name, alpha):
        return [go.Scatter(x=ages, y=pct[hi], line=dict(width=0), showlegend=False, hoverinfo="skip"),
                go.Scatter(x=ages, y=pct[lo], fill="tonexty", line=dict(width=0), name=name,
                           fillcolor=f"rgba(42,120,214,{alpha})", hoverinfo="skip")]
    fig = go.Figure(band(10, 90, "10th–90th percentile", 0.15) + band(25, 75, "25th–75th percentile", 0.30))
    fig.add_trace(go.Scatter(x=ages, y=pct[50], name="Median", line=dict(color=BLUE, width=2.5),
                             customdata=np.stack([pct[10], pct[90]], axis=-1),
                             hovertemplate="Age %{x}<br>Median: $%{y:,.0f}<br>10th pct: $%{customdata[0]:,.0f}"
                                           "<br>90th pct: $%{customdata[1]:,.0f}<extra></extra>"))
    fig.add_vline(x=retire_age, line=dict(color=INK2, width=1, dash="dot"))
    fig.add_annotation(x=retire_age, y=1, yref="paper", text="Retirement", showarrow=False,
                       font=dict(size=11, color=INK2), yanchor="bottom")
    _layout(fig, title, height=440, legend=dict(orientation="h", y=-0.12, x=0, yanchor="top"))
    fig.update_yaxes(tickprefix="$", tickformat="~s", rangemode="tozero")
    return fig


def frontier_chart(a: Assumptions, fr: Frontier, points: dict[str, np.ndarray], stress: bool = False) -> go.Figure:
    fig = go.Figure(go.Scatter(x=fr.sigmas * 100, y=fr.geo * 100, mode="lines", name="Efficient frontier (with guardrails)",
                               line=dict(color=BLUE, width=2.5),
                               hovertemplate="Risk %{x:.1f}%<br>Compound return %{y:.2f}%<extra></extra>"))
    symbols = ["circle", "diamond", "square", "triangle-up"]
    colors = [INK, "#eb6834", "#1baf7a", "#6250d6"]
    for i, (name, w) in enumerate(points.items()):
        s = a.portfolio_stats(w, stress)
        fig.add_trace(go.Scatter(x=[s["vol"] * 100], y=[s["geo"] * 100], mode="markers", name=name,
                                 marker=dict(size=13, symbol=symbols[i % 4], color=colors[i % 4], line=dict(color="white", width=1.5)),
                                 hovertemplate=f"<b>{name}</b><br>Risk %{{x:.1f}}%<br>Compound return %{{y:.2f}}%<extra></extra>"))
    _layout(fig, "Risk vs. expected compound return", height=400,
            legend=dict(orientation="h", y=-0.25, x=0))
    fig.update_xaxes(title="Volatility (σ)", ticksuffix="%", showgrid=True, gridcolor=GRID)
    fig.update_yaxes(title="Compound return", ticksuffix="%", title_standoff=6)
    return fig


def score_bars(capacity: float, willingness: float, combined: float) -> go.Figure:
    labels = ["Risk capacity", "Risk willingness", "Combined score"]
    vals = [capacity, willingness, combined]
    fig = go.Figure(go.Bar(x=vals[::-1], y=labels[::-1], orientation="h",
                           marker=dict(color=["#2a78d6", "#9ec1ec", "#9ec1ec"]),
                           text=[f"{v:.0f}" for v in vals[::-1]], textposition="outside", cliponaxis=False,
                           hovertemplate="%{y}: %{x:.0f} / 100<extra></extra>"))
    _layout(fig, "Your risk scores (0–100)", height=220, showlegend=False)
    fig.update_xaxes(range=[0, 110], showgrid=True, gridcolor=GRID)
    return fig
