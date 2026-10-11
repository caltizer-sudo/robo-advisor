"""Robo-advisor — MSFO 6831 Unit 3 (Georgetown MSF).

Run locally:  streamlit run app.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from robo import assumptions, charts, optimizer, planner, risk

st.set_page_config(page_title="Robo-Advisor", page_icon="📈", layout="wide")

TARGET_SUCCESS = 0.85
OUTCOME_LABELS = ("A", "B", "C", "D", "E")

# ------------------------------------------------------------------ defaults (Part 1(f) persona)
DEFAULTS = {
    "age": 30, "retire_age": 67, "sex": "Prefer not to say", "plan_override": False, "plan_age": 95,
    "savings": 25_000, "income": 85_000, "income_growth": 1.0, "savings_rate": 10.0,
    "later_savings_rate": 15.0, "later_from_age": 40, "employer_match": 4.0,
    "spending_mode": "% of final salary", "replacement": 75, "fixed_spending": 60_000,
    "ss_override": False, "ss_annual": 30_000, "ss_claim_age": 67, "ss_haircut": False,
    "n_kids": 0, "bequest": 0, "fee": 0.05, "stress": False,
    "income_stability": "Stable (salaried, private sector)", "emergency_fund": "3 to 6 months",
    "q_knowledge": 2, "q_goal": 2, "q_drawdown": 2, "q_outcomes": 3, "q_max_loss": 3,
}
for i in range(4):
    DEFAULTS[f"kid_age_{i}"] = 2 + 3 * i
    DEFAULTS[f"kid_cost_{i}"] = 30_000
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)


def load_example() -> None:
    for k, v in DEFAULTS.items():
        st.session_state[k] = v


def money(x: float) -> str:
    sign, x = ("−" if x < 0 else ""), abs(x)
    if x >= 1e6:
        return f"{sign}${x/1e6:,.2f}M"
    if x >= 1e4:
        return f"{sign}${x/1e3:,.0f}K"
    return f"{sign}${x:,.0f}"


def md(text: str) -> str:
    """Escape dollar signs so Streamlit markdown doesn't render them as LaTeX."""
    return text.replace("$", "\\$")


def stat(col, label: str, value: str, note: str | None = None, help: str | None = None) -> None:
    """A metric with static context underneath (st.metric deltas imply gains or losses)."""
    col.metric(label, md(value), help=help)
    if note:
        col.caption(md(note))


# ------------------------------------------------------------------ cached model pieces
@st.cache_resource
def model():
    a = assumptions.load()
    return a, optimizer.frontier(a)


@st.cache_data(show_spinner=False)
def run_plan(profile: planner.Profile, willingness: float, stress: bool):
    a, fr = model()
    ages, scores, W = planner.glide_path(profile, willingness, fr, a)
    base = planner.simulate(profile, W, planner.asset_returns(a, profile.years, paths=2000))
    stressed = None
    if stress:
        replay = min(max(profile.retire_age - profile.age, 0), profile.years - 1)
        R = planner.asset_returns(a, profile.years, paths=2000, stress=True, replay_at=replay)
        stressed = planner.simulate(profile, W, R)
    return ages, scores, W, base, stressed


@st.cache_data(show_spinner=False)
def run_solvers(profile: planner.Profile, willingness: float):
    a, fr = model()
    _, _, W = planner.glide_path(profile, willingness, fr, a)
    R = planner.asset_returns(a, profile.years, paths=1000, seed=11)
    return {
        "savings_rate": planner.required_savings_rate(profile, W, R, TARGET_SUCCESS),
        "spending": planner.sustainable_spending(profile, W, R, TARGET_SUCCESS),
        "retire_age": planner.retirement_age_needed(profile, willingness, fr, a, R, TARGET_SUCCESS),
    }


# ------------------------------------------------------------------ sidebar: the client's situation
with st.sidebar:
    st.header("Your situation")
    st.button("Load example: 30-year-old retiring at 67", on_click=load_example, width="stretch")

    st.subheader("About you")
    c1, c2 = st.columns(2)
    c1.number_input("Age", 18, 79, key="age")
    # keep dependent inputs consistent before their widgets render
    st.session_state.retire_age = min(max(int(st.session_state.retire_age), int(st.session_state.age) + 1), 80)
    st.session_state.later_from_age = min(max(int(st.session_state.later_from_age), int(st.session_state.age)), 80)
    st.session_state.plan_age = min(max(int(st.session_state.plan_age), int(st.session_state.retire_age) + 1), 110)
    c2.number_input("Retirement age", int(st.session_state.age) + 1, 80, key="retire_age")
    st.selectbox("Sex (used only for life expectancy)", list(planner.GOMPERTZ_MODE), key="sex")
    auto_plan = planner.planning_age(st.session_state.age, st.session_state.sex)
    st.checkbox(f"Override plan-to age (default {auto_plan}: 10% chance of living longer)", key="plan_override")
    if st.session_state.plan_override:
        st.slider("Plan to age", int(st.session_state.retire_age) + 1, 110, key="plan_age")
    plan_age = int(st.session_state.plan_age) if st.session_state.plan_override else auto_plan
    plan_age = max(plan_age, int(st.session_state.retire_age) + 1)

    st.subheader("Money")
    st.number_input("Investable assets today ($)", 0, 50_000_000, step=5_000, key="savings")
    st.number_input("Annual income before tax ($)", 0, 5_000_000, step=5_000, key="income")
    st.slider("Real income growth (% per year)", 0.0, 4.0, step=0.25, key="income_growth",
              help="Raises above inflation. 1% is a typical long-run assumption.")
    c1, c2 = st.columns(2)
    c1.slider("Savings rate now (%)", 0.0, 50.0, step=0.5, key="savings_rate")
    c2.slider("Employer match (%)", 0.0, 15.0, step=0.5, key="employer_match")
    c1, c2 = st.columns(2)
    c1.slider("Future savings rate (%)", 0.0, 50.0, step=0.5, key="later_savings_rate")
    c2.number_input("...starting at age", int(st.session_state.age), 80, key="later_from_age")

    st.subheader("Retirement spending")
    st.radio("Spending goal", ["% of final salary", "Fixed amount"], horizontal=True, key="spending_mode")
    if st.session_state.spending_mode == "% of final salary":
        st.slider("Replace this % of final salary", 40, 120, step=5, key="replacement")
    else:
        st.number_input("Annual spending in today's dollars ($)", 0, 1_000_000, step=5_000, key="fixed_spending")
    st.slider("Social Security claiming age", 62, 70, key="ss_claim_age")
    est = planner.social_security_estimate(st.session_state.income, st.session_state.ss_claim_age)
    st.checkbox(md(f"Override Social Security estimate ({money(est)}/yr)"), key="ss_override",
                help="Rough estimate from the 2025 benefit formula assuming a full career at today's "
                     "real income. Your own statement at ssa.gov/myaccount is better.")
    if st.session_state.ss_override:
        st.number_input("Social Security, today's dollars per year ($)", 0, 200_000, step=1_000, key="ss_annual")
    st.checkbox("Scenario: Social Security benefits cut 20%", key="ss_haircut",
                help="What happens if the trust-fund shortfall is closed purely by cutting benefits.")

    st.subheader("Other goals")
    st.number_input("Children to put through college", 0, 4, key="n_kids")
    kids = []
    for i in range(int(st.session_state.n_kids)):
        c1, c2 = st.columns(2)
        c1.number_input(f"Child {i+1} age", 0, 17, key=f"kid_age_{i}")
        c2.number_input("Cost / yr ($)", 0, 150_000, step=5_000, key=f"kid_cost_{i}")
        kids.append(planner.Child(age=int(st.session_state[f"kid_age_{i}"]),
                                  annual_cost=float(st.session_state[f"kid_cost_{i}"])))
    st.number_input("Bequest goal at plan-to age, today's dollars ($)", 0, 50_000_000, step=25_000, key="bequest")

    st.subheader("Costs and stress test")
    st.slider("All-in annual cost (%)", 0.0, 1.5, step=0.05, key="fee",
              help="Fund expenses plus any advisory fee. Index ETFs cost about 0.03-0.10%.")
    st.toggle("Stress test: 2022 repeats in your first year of retirement", key="stress",
              help="Keeps your recommended portfolio fixed and re-runs the simulation with (1) stocks and "
                   "bonds moving together as in 2022-26 and (2) 2022's actual returns and inflation in the "
                   "first year of retirement, when losses do the most damage.")

ss = st.session_state
profile = planner.Profile(
    age=int(ss.age), retire_age=int(ss.retire_age), plan_age=plan_age, sex=ss.sex,
    savings=float(ss.savings), income=float(ss.income), income_growth=ss.income_growth / 100,
    savings_rate=ss.savings_rate / 100, later_savings_rate=ss.later_savings_rate / 100,
    later_from_age=int(ss.later_from_age), employer_match=ss.employer_match / 100,
    spending_mode="replacement" if ss.spending_mode == "% of final salary" else "fixed",
    replacement=ss.replacement / 100, fixed_spending=float(ss.fixed_spending),
    ss_annual=float(ss.ss_annual) if ss.ss_override else None, ss_claim_age=int(ss.ss_claim_age),
    ss_haircut=0.20 if ss.ss_haircut else 0.0, children=tuple(kids), bequest=float(ss.bequest),
    fee=ss.fee / 100, income_stability=ss.income_stability, emergency_fund=ss.emergency_fund,
)
stress = bool(ss.stress)
a, fr = model()

# ------------------------------------------------------------------ header
st.title("Robo-Advisor")
st.caption(f"Goals-based retirement planning with forward-looking market assumptions (as of {a.as_of}). "
           "Educational tool for MSFO 6831; not investment advice.")

tab_risk, tab_rec, tab_proj, tab_how, tab_lim = st.tabs(
    ["1 · Risk profile", "2 · Recommendation", "3 · Projections", "How it works", "Limitations"])

# ------------------------------------------------------------------ tab 1: risk profile
with tab_risk:
    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("Capacity: how much risk you can afford")
        st.selectbox("How stable is your income?", list(risk.INCOME_STABILITY), key="income_stability")
        st.selectbox("Emergency savings (in cash, separate from this plan)", list(risk.EMERGENCY_FUND), key="emergency_fund")
        yrs_to = profile.retire_age - profile.age
        yrs_in = profile.plan_age - profile.retire_age
        st.markdown(md(
            f"- **Time until withdrawals:** {yrs_to} years\n"
            f"- **How long withdrawals last:** {yrs_in} years (to age {profile.plan_age})\n"
            f"- **Dependents:** {profile.dependents_at(profile.age)} (children entered in the sidebar)\n"
            f"- **Guaranteed income in retirement:** Social Security covers "
            f"{planner.guaranteed_share(profile)*100:.0f}% of your spending goal"))
        st.caption("In the last 10 years before retirement, capacity shifts from job-related factors to "
                   "your remaining horizon and how much of your spending is guaranteed.")
    with right:
        st.subheader("Willingness: how much risk you're comfortable with")
        for q in risk.WILLINGNESS_QUESTIONS:
            if q.key == "outcomes":
                bal = max(profile.savings, 10_000)
                opts = []
                for lab, sig in zip(OUTCOME_LABELS, risk.OUTCOME_SIGMAS):
                    s = a.portfolio_stats(fr.at_sigma(sig))
                    mu = s["real_arith"] + a.inflation
                    opts.append(md(f"{lab}: average {money(bal*mu)} · bad year {money(bal*(mu-1.645*s['vol']))} · "
                                   f"good year +{money(bal*(mu+1.645*s['vol']))}"))
                st.radio(md(f"{q.text} (on {money(bal)}; 1-in-20 bad and good years)"), range(5),
                         format_func=lambda i, o=opts: o[i], key="q_outcomes")
            else:
                st.radio(q.text, range(len(q.options)), format_func=lambda i, o=q.options: o[i], key=f"q_{q.key}")

answers = {q.key: int(ss[f"q_{q.key}"]) for q in risk.WILLINGNESS_QUESTIONS}
will = risk.willingness_score(answers)
cap = planner.capacity_at(profile, profile.age)
comb = risk.combined_score(cap, will)

with tab_risk:
    st.divider()
    c1, c2 = st.columns([3, 2], gap="large")
    c1.plotly_chart(charts.score_bars(cap, will, comb), theme=None, config={"displayModeBar": False})
    with c2:
        stat(st, "Risk tolerance", risk.profile_label(comb), f"Combined score {comb:.0f} / 100")
        st.caption("Combined score = the more conservative of the two scores, moved 25% of the way toward the other.")
        note = risk.conflict_note(cap, will)
        if note:
            st.warning(note)

# ------------------------------------------------------------------ run the plan
with st.spinner("Simulating 2,000 market scenarios..."):
    ages, scores, W, res, res_stress = run_plan(profile, will, stress)
    sol = run_solvers(profile, will)
w_now = W[0]
stats_now = a.portfolio_stats(w_now)
ret_idx = min(profile.retire_age - profile.age, len(W) - 1)
flows = planner.cash_flows(profile)
need = float(flows["need"])

# Schwab Intelligent Portfolios "Investor 1" (30-year-old, aggressive) mapped to our classes; 2% gold excluded
schwab = np.array([45.0, 27.0, 16.0, 3.1, 0.0, 6.9])
schwab = schwab / schwab.sum()


def levers_card() -> None:
    """The 'robo moment': plan success and the three ways to reach the target."""
    with st.container(border=True):
        head = (f"**Plan success: {res.success*100:.0f}%** of 2,000 simulated markets fully fund your goal "
                f"to age {profile.plan_age}")
        if res_stress is not None:
            head += f" · **{res_stress.success*100:.0f}% in the 2022 stress test**"
        st.markdown(md(head))
        if res.success >= TARGET_SUCCESS:
            st.markdown(f"You're above the {TARGET_SUCCESS*100:.0f}% confidence target. "
                        "Room to spare could fund earlier retirement or more spending:")
        else:
            st.markdown(f"To reach **{TARGET_SUCCESS*100:.0f}%**, make **any one** of these changes:")
        c = st.columns(3)
        if sol["savings_rate"] is not None:
            stat(c[0], "Save", f"{sol['savings_rate']*100:.1f}% of pay",
                 f"vs. {profile.savings_rate*100:.0f}% now, {profile.later_savings_rate*100:.0f}% from {profile.later_from_age} (+{profile.employer_match*100:.0f}% match)")
        else:
            stat(c[0], "Save", "> 60% of pay", "Saving alone can't reach the target")
        if sol["spending"] is not None:
            stat(c[1], "Spend", f"{money(sol['spending'])}/yr", f"vs. a goal of {money(need)}/yr")
        else:
            stat(c[1], "Spend", "—", "Even zero spending misses the target (check goals)")
        if sol["retire_age"] is not None:
            stat(c[2], "Retire at", f"{sol['retire_age']}", f"vs. {profile.retire_age} planned")
        else:
            stat(c[2], "Retire at", "after 75", "Retiring later alone can't reach the target")


# ------------------------------------------------------------------ tab 2: recommendation
with tab_rec:
    st.markdown(f"#### {risk.portfolio_label(stats_now['equity'])} portfolio · risk tolerance "
                f"{risk.profile_label(comb).lower()} ({comb:.0f}/100)")
    levers_card()
    m = st.columns(4)
    stat(m[0], "Stocks", f"{stats_now['equity']*100:.0f}%", f"{W[ret_idx, :3].sum()*100:.0f}% at retirement")
    stat(m[1], "Expected return", f"{stats_now['geo']*100:.1f}%/yr", f"{stats_now['real_geo']*100:.1f}% after inflation",
         help="10-year expected compound return, net of volatility drag, before fees.")
    stat(m[2], "Volatility", f"{stats_now['vol']*100:.1f}%", "after inflation")
    bad = (stats_now["real_arith"] + a.inflation - 1.645 * stats_now["vol"]) * profile.savings
    stat(m[3], "1-in-20 bad year", money(bad), f"on today's {money(profile.savings)}",
         help="5th percentile one-year return applied to today's balance.")

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.plotly_chart(charts.allocation_bar(a, w_now), theme=None, config={"displayModeBar": False})
    with c2:
        st.markdown("**What to buy**")
        buy = pd.DataFrame({"Asset class": a.names, "Weight": [f"{x*100:.1f}%" for x in w_now],
                            "Example ETFs": a.etfs})
        st.table(buy[w_now > 0.0005].set_index("Asset class"))
        st.caption("Rebalance once a year or when any holding drifts 5 points from target. "
                   "Hold bonds and TIPS in tax-deferred accounts where possible.")

    st.plotly_chart(charts.glide_path_area(a, ages, W, profile.retire_age, profile.age), theme=None,
                    config={"displayModeBar": False})
    st.caption("Your risk *capacity* is recomputed every year. The mix holds steady while your spending horizon "
               "is 30+ years away, shifts toward bonds as retirement approaches, and keeps easing through "
               "retirement; the TIPS share of bonds rises from 15% to 40%. "
               "Black dots: Vanguard's target-date glide path (90% stocks at 25, 50% at 65, 30% from 72).")

    c1, c2 = st.columns([3, 2], gap="large")
    with c1:
        st.plotly_chart(charts.frontier_chart(a, fr, {"Your portfolio": w_now, "Schwab 'Aggressive Growth' example": schwab}),
                        theme=None, config={"displayModeBar": False})
    with c2:
        st.markdown("**Compared with Schwab Intelligent Portfolios**")
        s_sch = a.portfolio_stats(schwab)
        comp = pd.DataFrame({
            "": ["Stocks", "Cash", "Expected return", "Volatility"],
            "This robo": [f"{stats_now['equity']*100:.0f}%", f"{w_now[-1]*100:.1f}%", f"{stats_now['geo']*100:.2f}%", f"{stats_now['vol']*100:.1f}%"],
            "Schwab": ["88%", "6.9%", f"{s_sch['geo']*100:.2f}%", f"{s_sch['vol']*100:.1f}%"],
        }).set_index("")
        st.table(comp)
        j50 = int(np.argmin(np.abs(fr.weights[:, :3].sum(1) - 0.5)))
        jmax = int(np.argmax(fr.geo))
        st.caption(
            "Schwab's published example for an aggressive 30-year-old: 88% stocks, 3.1% bonds, 2% gold, 6.9% cash. "
            "Its return and risk use this robo's assumptions (gold left out, the rest rescaled). "
            f"At today's valuations the frontier is flat: going from {fr.weights[j50,:3].sum()*100:.0f}% to "
            f"{fr.weights[jmax,:3].sum()*100:.0f}% stocks adds only {(fr.geo[jmax]-fr.geo[j50])*100:.2f} points of "
            "expected compound return, so this robo never goes past the highest-compound-return portfolio.")

# ------------------------------------------------------------------ tab 3: projections
with tab_proj:
    ri = min(ret_idx, len(res.pct[50]) - 1)
    m = st.columns(4)
    if res_stress is None:
        stat(m[0], "Plan success", f"{res.success*100:.0f}%", f"target {TARGET_SUCCESS*100:.0f}%",
             help=f"Share of 2,000 simulated markets in which spending is fully funded to age {profile.plan_age}.")
        stat(m[1], f"Median at {profile.retire_age}", money(res.pct[50][ri]), "today's dollars")
        stat(m[2], "Spending goal", f"{money(need)}/yr", f"Social Security covers {money(profile.social_security())}")
        stat(m[3], "Run-out risk", f"{res.ruin_while_alive*100:.0f}%", "while still alive",
             help="Chance of running out of money while still alive (each scenario weighted by survival odds).")
        st.plotly_chart(charts.fan_chart(res.ages, res.pct, profile.retire_age,
                                         "Projected savings by age, in today's dollars (2,000 simulated markets)"),
                        theme=None, config={"displayModeBar": False})
    else:
        # every number shows base -> stress, so metrics and charts never disagree
        end = len(res.pct[50]) - 1
        stat(m[0], "Plan success", f"{res.success*100:.0f}% → {res_stress.success*100:.0f}%", "base → 2022 stress",
             help=f"Share of 2,000 simulated markets in which spending is fully funded to age {profile.plan_age}.")
        stat(m[1], f"Median at {profile.plan_age}", f"{money(res.pct[50][end])} → {money(res_stress.pct[50][end])}",
             "base → stress, today's dollars")
        stat(m[2], "Spending goal", f"{money(need)}/yr", f"Social Security covers {money(profile.social_security())}")
        stat(m[3], "Run-out risk", f"{res.ruin_while_alive*100:.0f}% → {res_stress.ruin_while_alive*100:.0f}%",
             "base → stress, while still alive",
             help="Chance of running out of money while still alive (each scenario weighted by survival odds).")
        st.warning(md(
            f"**2022 stress test:** with your portfolio unchanged, a repeat of 2022 in your first year of retirement "
            f"(real losses: U.S. stocks {a.replay_2022[0]*100:.0f}%, bonds {a.replay_2022[3]*100:.0f}%, "
            f"TIPS {a.replay_2022[4]*100:.0f}%) plus stocks and bonds moving together cuts plan success from "
            f"{res.success*100:.0f}% to **{res_stress.success*100:.0f}%** "
            f"({(res_stress.success-res.success)*100:+.0f} points). Sequence risk is largest right at retirement."))
        y_max = 1.05 * max(float(res.pct[90].max()), float(res_stress.pct[90].max()))
        c1, c2 = st.columns(2, gap="large")
        c1.plotly_chart(charts.fan_chart(res.ages, res.pct, profile.retire_age, "Base case", y_max),
                        theme=None, config={"displayModeBar": False})
        c2.plotly_chart(charts.fan_chart(res_stress.ages, res_stress.pct, profile.retire_age,
                                         "2022 stress test (same portfolio)", y_max),
                        theme=None, config={"displayModeBar": False})
        st.caption("Projected savings by age in today's dollars, 2,000 simulated markets each, on the same scale.")

    st.subheader("Advice")
    levers_card()
    tips = [f"- **Stay invested:** your mix is {stats_now['equity']*100:.0f}% stocks today and "
            f"{W[ret_idx, :3].sum()*100:.0f}% at retirement. Selling after a crash locks in losses."]
    if profile.bequest > 0:
        tips.append(f"- **Bequest:** {res.bequest_prob*100:.0f}% chance of leaving at least {money(profile.bequest)} "
                    f"while funding all spending.")
    if profile.ss_claim_age < 70:
        tips.append("- **Social Security:** each year you delay claiming (up to 70) raises the benefit about 8%, "
                    "an inflation-protected annuity that reduces how much your portfolio must cover.")
    st.markdown(md("\n".join(tips)))

    with st.expander("Details: milestones, cash flows and longevity"):
        rows = []
        for age_ in sorted({profile.retire_age, 75, 85, profile.plan_age}):
            if profile.age <= age_ <= profile.plan_age:
                i = age_ - profile.age
                rows.append({"Age": age_, "10th percentile": money(res.pct[10][i]), "Median": money(res.pct[50][i]),
                             "90th percentile": money(res.pct[90][i]),
                             "Chance alive": f"{float(planner.survival(profile.age, age_, profile.sex))*100:.0f}%"})
        st.table(pd.DataFrame(rows).set_index("Age"))
        st.markdown(md(
            f"- Life expectancy (Gompertz approximation): **{planner.life_expectancy(profile.age, profile.sex):.0f}**. "
            f"Plan runs to **{profile.plan_age}**.\n"
            f"- Contributions this year: **{money(flows['contrib'][0])}** "
            f"({(profile.savings_rate+profile.employer_match)*100:.1f}% of income including match).\n"
            f"- Retirement withdrawals: **{money(flows['withdraw'][ret_idx])}/yr** from savings after Social Security "
            f"of {money(profile.social_security())}/yr (claimed at {profile.ss_claim_age}).\n"
            f"- College costs total **{money(flows['college'].sum())}** (today's dollars, +1%/yr real)."))

# ------------------------------------------------------------------ tab 4: how it works
with tab_how:
    st.subheader("1. Expected returns are forward-looking")
    st.markdown(
        "Each asset class's 10-year expected return is built from **today's market prices**, not past averages: "
        "bond yields for bonds, and dividend yield + buybacks + earnings growth + inflation ± valuation change "
        "(Grinold–Kroner) for stocks. Volatilities and correlations blend 26 years of monthly history with the "
        "Horizon Actuarial 2026 survey of 43 investment advisors.")
    tbl = pd.DataFrame({"Asset class": a.names, "Expected return": [f"{x*100:.2f}%" for x in a.geo],
                        "Volatility": [f"{x*100:.1f}%" for x in a.vol], "How it was estimated": a.methods})
    st.table(tbl.set_index("Asset class"))
    st.markdown("**Correlations** (base case)")
    st.table(pd.DataFrame(a.corr, index=a.names, columns=a.names).map(lambda x: f"{x:.2f}"))
    st.subheader("2. Inflation risk, so TIPS earn their place")
    st.markdown(
        f"Everything is planned in today's dollars, so inflation surprises matter. Inflation follows a persistent "
        f"random process (volatility {a.infl_vol*100:.2f}%, persistence {a.infl_persistence:.1f}). A surprise lowers the "
        "real return of stocks and nominal bonds one-for-one in the short run, T-bills by 30% (their yields reset), "
        "and TIPS not at all. The optimizer uses this real-return risk, and the TIPS share of bonds never falls "
        "below 15%, rising to 40% by retirement.")
    st.subheader("3. Two risk scores, combined conservatively")
    st.markdown(
        "- **Capacity** (objective, 0–100). Working years: remaining horizon (50%), income stability (20%), "
        "emergency savings (15%), dependents (15%). Retirement: remaining horizon (60%) and the share of spending "
        "covered by Social Security (40%), phased in over the 10 years before retirement. Horizon = years until "
        "withdrawals start + half the years they last (full credit at 30).\n"
        "- **Willingness** (subjective, 0–100): knowledge, objective, reaction to a 25% crash, choice among "
        "one-year outcome ranges drawn from the actual frontier, and maximum tolerable loss.\n"
        "- **Combined** = lower score + 25% × (higher − lower), mapped linearly onto the efficient frontier between "
        "the minimum-risk portfolio and the portfolio with the highest expected compound return.")
    st.subheader("4. Optimization with guardrails")
    st.markdown(
        "Portfolios come from a mean-variance efficient frontier in real terms, inside guardrails: U.S. ≥ 50% of "
        "stocks, developed international ≤ 35%, emerging ≤ 15%, TIPS ≤ 40% of bonds, cash 2–30%, stocks ≤ 95%. "
        "Unconstrained optimizers turn small forecast errors into extreme portfolios; our pension analysis (Q5) "
        "showed weights swinging from 25% to 51% on a 0.5-point change in expected returns.")
    st.subheader("5. Monte Carlo projections and the stress test")
    st.markdown(
        "Each of 2,000 scenarios draws correlated returns for every asset class and an inflation path, every "
        "year, rebalances to that year's glide-path weights and subtracts fees. A plan *works* if spending is "
        "fully funded to the plan-to age. The advice levers are found by bisection on the same scenarios.\n\n"
        "The **stress test never changes your portfolio.** It re-runs the same plan with 2022–26 correlations "
        "(stocks and bonds falling together) and replays 2022's actual returns and 6.4% inflation in the first "
        "year of retirement.")
    st.caption("Sources: " + "; ".join(a.raw["sources"]))

# ------------------------------------------------------------------ tab 5: limitations
with tab_lim:
    st.subheader("Important features not included (yet)")
    st.markdown(
        "- **Taxes and account location:** no distinction between 401(k), Roth and taxable accounts, no tax drag, "
        "no required minimum distributions or Roth-conversion advice.\n"
        "- **Marital status and spouse:** single-life planning; no spousal Social Security, survivor benefits or "
        "joint life expectancy.\n"
        "- **Real estate and debt:** home equity, mortgages and other debts are ignored.\n"
        "- **Annuities and pensions:** no guaranteed income products or defined-benefit pensions beyond Social Security.\n"
        "- **Human capital:** future earnings are not treated as a bond-like asset, which would justify more stocks "
        "for young savers; job loss, disability and health costs are not simulated.\n"
        "- **Return model:** lognormal and independent from year to year (apart from inflation persistence); no fat "
        "tails or valuation mean reversion; market assumptions are held constant for the whole horizon.\n"
        "- **Behavior:** assumes the client rebalances and never panic-sells.\n"
        "- **Life expectancy:** a Gompertz approximation, not a full actuarial table; no health adjustments.")
    st.caption("Educational project for MSFO 6831 (Georgetown University). Not investment, tax or legal advice.")
