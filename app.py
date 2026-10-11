"""Robo-advisor — MSFO 6831 Unit 3 (Georgetown MSF).

Run locally:  streamlit run app.py
"""
from __future__ import annotations

from dataclasses import replace

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


# ------------------------------------------------------------------ cached model pieces
@st.cache_resource
def model(stress: bool):
    a = assumptions.load()
    return a, optimizer.frontier(a, stress=stress)


@st.cache_data(show_spinner=False)
def run_plan(profile: planner.Profile, willingness: float, stress: bool):
    a, fr = model(stress)
    ages, scores, W = planner.glide_path(profile, willingness, fr)
    R = planner.asset_returns(a, profile.years, paths=2000, stress=stress)
    res = planner.simulate(profile, W, R)
    return ages, scores, W, res


@st.cache_data(show_spinner=False)
def run_solvers(profile: planner.Profile, willingness: float, stress: bool):
    a, fr = model(stress)
    _, _, W = planner.glide_path(profile, willingness, fr)
    R = planner.asset_returns(a, profile.years, paths=1000, stress=stress, seed=11)
    return {
        "savings_rate": planner.required_savings_rate(profile, W, R, TARGET_SUCCESS),
        "spending": planner.sustainable_spending(profile, W, R, TARGET_SUCCESS),
        "retire_age": planner.retirement_age_needed(profile, willingness, fr, R, TARGET_SUCCESS),
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
    st.checkbox("Stress test: Social Security benefits cut 20%", key="ss_haircut",
                help="Scenario if the trust fund shortfall is resolved purely by benefit cuts.")

    st.subheader("Other goals")
    st.number_input("Children to put through college", 0, 4, key="n_kids")
    kids = []
    for i in range(int(st.session_state.n_kids)):
        c1, c2 = st.columns(2)
        c1.number_input(f"Child {i+1} age", 0, 17, key=f"kid_age_{i}")
        c2.number_input(f"Cost / yr ($)", 0, 150_000, step=5_000, key=f"kid_cost_{i}")
        kids.append(planner.Child(age=int(st.session_state[f"kid_age_{i}"]),
                                  annual_cost=float(st.session_state[f"kid_cost_{i}"])))
    st.number_input("Bequest goal at plan-to age, today's dollars ($)", 0, 50_000_000, step=25_000, key="bequest")

    st.subheader("Costs and stress tests")
    st.slider("All-in annual cost (%)", 0.0, 1.5, step=0.05, key="fee",
              help="Fund expenses plus any advisory fee. Index ETFs cost about 0.03-0.10%.")
    st.toggle("Stress test: stocks and bonds fall together (2022–26 correlations)", key="stress")

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
a, fr = model(stress)
lo, hi = planner.sigma_range(fr)

# ------------------------------------------------------------------ header
st.title("Robo-Advisor")
st.caption(f"Goals-based retirement planning with forward-looking market assumptions (as of {a.as_of}). "
           "Educational tool for MSFO 6831; not investment advice.")
if stress:
    st.info("Stress test on: stocks, bonds and TIPS are assumed to move together as they did in 2022–26.")

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
        st.markdown(
            f"- **Time until withdrawals:** {yrs_to} years (from your retirement age)\n"
            f"- **How long withdrawals last:** {yrs_in} years (to age {profile.plan_age})\n"
            f"- **Dependents:** {profile.dependents_at(profile.age)} (children entered in the sidebar)")
    with right:
        st.subheader("Willingness: how much risk you're comfortable with")
        for q in risk.WILLINGNESS_QUESTIONS:
            if q.key == "outcomes":
                bal = max(profile.savings, 10_000)
                opts = []
                for lab, sig in zip(OUTCOME_LABELS, risk.OUTCOME_SIGMAS):
                    s = a.portfolio_stats(fr.at_sigma(sig), stress)
                    opts.append(md(f"{lab}: average {money(bal*s['arith'])} · bad year {money(bal*(s['arith']-1.645*s['vol']))} · "
                                   f"good year +{money(bal*(s['arith']+1.645*s['vol']))}"))
                st.radio(md(f"{q.text} (on {money(bal)}; 1-in-20 bad and good years)"), range(5),
                         format_func=lambda i, o=opts: o[i], key="q_outcomes")
            else:
                st.radio(q.text, range(len(q.options)), format_func=lambda i, o=q.options: o[i], key=f"q_{q.key}")

    answers = {q.key: int(ss[f"q_{q.key}"]) for q in risk.WILLINGNESS_QUESTIONS}
    will = risk.willingness_score(answers)
    cap = planner.capacity_at(profile, profile.age)
    comb = risk.combined_score(cap, will)
    st.divider()
    c1, c2 = st.columns([3, 2], gap="large")
    c1.plotly_chart(charts.score_bars(cap, will, comb), theme=None, config={"displayModeBar": False})
    with c2:
        st.metric("Risk tolerance", risk.profile_label(comb), f"combined score {comb:.0f}/100", delta_color="off")
        st.caption("Combined score = the more conservative of the two scores, moved 25% of the way toward the other.")
        note = risk.conflict_note(cap, will)
        if note:
            st.warning(note)

# ------------------------------------------------------------------ run the plan
answers = {q.key: int(ss[f"q_{q.key}"]) for q in risk.WILLINGNESS_QUESTIONS}
will = risk.willingness_score(answers)
cap = planner.capacity_at(profile, profile.age)
comb = risk.combined_score(cap, will)
with st.spinner("Simulating 2,000 market scenarios..."):
    ages, scores, W, res = run_plan(profile, will, stress)
w_now = W[0]
stats_now = a.portfolio_stats(w_now, stress)

# Schwab Intelligent Portfolios "Investor 1" (30-year-old, aggressive) mapped to our classes; 2% gold excluded
schwab = np.array([45.0, 27.0, 16.0, 3.1, 0.0, 6.9])
schwab = schwab / schwab.sum()

# ------------------------------------------------------------------ tab 2: recommendation
with tab_rec:
    st.markdown(f"#### {risk.portfolio_label(stats_now['equity'])} portfolio · risk tolerance "
                f"{risk.profile_label(comb).lower()} ({comb:.0f}/100)")
    m = st.columns(4)
    m[0].metric("Stocks", f"{stats_now['equity']*100:.0f}%", f"{W[min(profile.retire_age-profile.age, len(W)-1), :3].sum()*100:.0f}% at retirement",
                delta_color="off")
    m[1].metric("Expected return", f"{stats_now['geo']*100:.1f}%/yr",
                f"{stats_now['real_geo']*100:.1f}% after inflation", delta_color="off",
                help="10-year expected compound return, net of volatility drag, before fees.")
    m[2].metric("Volatility", f"{stats_now['vol']*100:.1f}%")
    bad = (stats_now["arith"] - 1.645 * stats_now["vol"]) * profile.savings
    m[3].metric("1-in-20 bad year", money(bad), help="5th percentile one-year return applied to today's balance.")

    c1, c2 = st.columns([3, 2], gap="large")
    with c1:
        st.plotly_chart(charts.allocation_bar(a, w_now), theme=None, config={"displayModeBar": False})
    with c2:
        st.markdown("**What to buy**")
        df = pd.DataFrame({"Asset class": a.names, "Weight": [f"{x*100:.1f}%" for x in w_now],
                           "Example ETFs": a.etfs, "Expected return": [f"{x*100:.2f}%" for x in a.geo],
                           "Volatility": [f"{x*100:.1f}%" for x in a.vol]})
        st.dataframe(df[w_now > 0.0005], hide_index=True)
        st.caption("Rebalance once a year or when any holding drifts 5 points from target. "
                   "Hold bonds and TIPS in tax-deferred accounts where possible.")

    st.plotly_chart(charts.glide_path_area(a, ages, W, profile.retire_age, profile.age), theme=None,
                    config={"displayModeBar": False})
    st.caption("Your risk *capacity* is recomputed every year as retirement approaches, so the allocation "
               "glides toward bonds automatically. Your *willingness* answers stay fixed.")

    c1, c2 = st.columns([3, 2], gap="large")
    with c1:
        st.plotly_chart(charts.frontier_chart(a, fr, {"Your portfolio": w_now, "Schwab 'Aggressive Growth' example": schwab}, stress),
                        theme=None, config={"displayModeBar": False})
    with c2:
        st.markdown("**How this compares with Schwab Intelligent Portfolios**")
        s_sch = a.portfolio_stats(schwab, stress)
        comp = pd.DataFrame({
            "": ["Stocks", "Cash", "Expected compound return", "Volatility"],
            "This robo": [f"{stats_now['equity']*100:.0f}%", f"{w_now[-1]*100:.1f}%", f"{stats_now['geo']*100:.2f}%", f"{stats_now['vol']*100:.1f}%"],
            "Schwab example": ["88%", "6.9%", f"{s_sch['geo']*100:.2f}%", f"{s_sch['vol']*100:.1f}%"],
        })
        st.dataframe(comp, hide_index=True)
        j50 = int(np.argmin(np.abs(fr.weights[:, :3].sum(1) - 0.5)))
        jmax = int(np.argmax(fr.geo))
        st.caption(
            f"Schwab's published example for an aggressive 30-year-old: 88% stocks, 3.1% bonds, 2% gold, 6.9% cash. "
            f"Its expected return and risk use this robo's assumptions, with gold left out and the rest rescaled. "
            f"At today's valuations the frontier is flat: moving from {fr.weights[j50,:3].sum()*100:.0f}% to "
            f"{fr.weights[jmax,:3].sum()*100:.0f}% stocks adds only {(fr.geo[jmax]-fr.geo[j50])*100:.2f} points of expected "
            f"compound return, which is why this robo caps risk at the highest-compound-return portfolio.")

# ------------------------------------------------------------------ tab 3: projections
with tab_proj:
    flows = planner.cash_flows(profile)
    sol = run_solvers(profile, will, stress)
    ret_idx = profile.retire_age - profile.age
    need = float(flows["need"])
    m = st.columns(4)
    m[0].metric("Chance the plan works", f"{res.success*100:.0f}%",
                help=f"Share of 2,000 simulated markets in which spending is fully funded to age {profile.plan_age}.")
    m[1].metric("Median savings at retirement", money(res.pct[50][ret_idx]), "today's dollars", delta_color="off")
    m[2].metric("Spending goal", f"{money(need)}/yr", f"Social Security covers {money(profile.social_security())}", delta_color="off")
    m[3].metric("Chance of outliving your money", f"{res.ruin_while_alive*100:.0f}%",
                help="Runs out of money while still alive, weighting each scenario by the probability of survival.")

    st.plotly_chart(charts.fan_chart(res.ages, res.pct, profile.retire_age,
                                     "Projected savings by age, in today's dollars (2,000 simulated markets)"),
                    theme=None, config={"displayModeBar": False})

    st.subheader("Advice")
    tips = []
    if res.success >= TARGET_SUCCESS:
        tips.append(f"**You're on track:** {res.success*100:.0f}% of simulated markets fully fund your goal "
                    f"(target {TARGET_SUCCESS*100:.0f}%).")
    else:
        tips.append(f"**You're short of the {TARGET_SUCCESS*100:.0f}% confidence target** ({res.success*100:.0f}% today). "
                    "Any one of the changes below closes the gap:")
    if sol["savings_rate"] is not None:
        tips.append(f"- **Save {sol['savings_rate']*100:.1f}% of income** every year until retirement "
                    f"(plus your {profile.employer_match*100:.1f}% match). You plan {profile.savings_rate*100:.1f}% now "
                    f"and {profile.later_savings_rate*100:.1f}% from age {profile.later_from_age}.")
    else:
        tips.append("- Saving alone (up to 60% of income) does not reach the target; combine levers below.")
    if sol["spending"] is not None:
        tips.append(f"- **Spend up to {money(sol['spending'])}/yr in retirement** (vs. your goal of {money(need)}).")
    if sol["retire_age"] is not None:
        tips.append(f"- **Retire at {sol['retire_age']}** instead of {profile.retire_age}.")
    tips.append(f"- **Stay invested:** your recommended mix is {stats_now['equity']*100:.0f}% stocks today and "
                f"{W[min(ret_idx, len(W)-1), :3].sum()*100:.0f}% at retirement. Selling after a crash locks in losses.")
    if profile.bequest > 0:
        tips.append(f"- **Bequest:** {res.bequest_prob*100:.0f}% chance of leaving at least {money(profile.bequest)} "
                    f"while funding all spending.")
    st.markdown(md("\n".join(tips)))

    with st.expander("Details: milestones, cash flows and longevity"):
        rows = []
        for age_ in sorted({profile.retire_age, 75, 85, profile.plan_age}):
            if profile.age <= age_ <= profile.plan_age:
                i = age_ - profile.age
                rows.append({"Age": age_, "10th percentile": money(res.pct[10][i]), "Median": money(res.pct[50][i]),
                             "90th percentile": money(res.pct[90][i]),
                             "Chance alive": f"{float(planner.survival(profile.age, age_, profile.sex))*100:.0f}%"})
        st.dataframe(pd.DataFrame(rows), hide_index=True)
        st.markdown(md(
            f"- Life expectancy (Gompertz approximation): **{planner.life_expectancy(profile.age, profile.sex):.0f}**. "
            f"Plan runs to **{profile.plan_age}**.\n"
            f"- Contributions this year: **{money(flows['contrib'][0])}** "
            f"({(profile.savings_rate+profile.employer_match)*100:.1f}% of income including match).\n"
            f"- Retirement withdrawals: **{money(flows['withdraw'][ret_idx]) if ret_idx < len(flows['withdraw']) else '—'}/yr** "
            f"from savings after Social Security of {money(profile.social_security())}/yr "
            f"(claimed at {profile.ss_claim_age}).\n"
            f"- College costs total **{money(flows['college'].sum())}** (today's dollars, +1%/yr real)."))

# ------------------------------------------------------------------ tab 4: how it works
with tab_how:
    st.subheader("1. Expected returns are forward-looking")
    st.markdown(
        "Each asset class's 10-year expected return is built from **today's market prices**, not past averages: "
        "bond yields for bonds, and dividend yield + buybacks + earnings growth + inflation ± valuation change "
        "(Grinold–Kroner) for stocks. Volatilities and correlations blend 26 years of monthly history with the "
        "Horizon Actuarial 2026 survey of 43 investment advisors.")
    tbl = pd.DataFrame({"Asset class": a.names, "Expected return (compound)": [f"{x*100:.2f}%" for x in a.geo],
                        "Volatility": [f"{x*100:.1f}%" for x in a.vol], "How it was estimated": a.methods})
    st.table(tbl.set_index("Asset class"))
    corr = pd.DataFrame(a.corr_stress if stress else a.corr, index=a.names, columns=a.names).map(lambda x: f"{x:.2f}")
    st.markdown("**Correlations**" + (" (stress test)" if stress else ""))
    st.table(corr)
    st.subheader("2. Two risk scores, combined conservatively")
    st.markdown(
        "- **Capacity** (objective, 0–100): years until withdrawals start and how long they last (50%), income "
        "stability (20%), emergency savings (15%), dependents (15%).\n"
        "- **Willingness** (subjective, 0–100): knowledge, objective, reaction to a 25% crash, choice among "
        "one-year outcome ranges drawn from the actual frontier, and maximum tolerable loss.\n"
        "- **Combined** = lower score + 25% × (higher − lower). The combined score maps linearly onto the efficient "
        "frontier between the minimum-risk portfolio and the portfolio with the highest expected compound return.")
    st.subheader("3. Optimization with guardrails")
    st.markdown(
        "Portfolios come from a mean-variance efficient frontier, but only inside guardrails (U.S. ≥ 50% of stocks, "
        "developed international ≤ 35%, emerging ≤ 15%, TIPS ≤ 40% of bonds, cash 2–30%, stocks ≤ 95%). "
        "Unconstrained optimizers turn small forecast errors into extreme portfolios; our pension analysis "
        "(Q5) showed weights swinging from 25% to 51% on a 0.5-point change in expected returns.")
    st.subheader("4. Monte Carlo projections in today's dollars")
    st.markdown(
        "Each of 2,000 scenarios draws correlated lognormal returns for every asset class, every year, rebalances to "
        "that year's glide-path weights, and subtracts fees. Contributions grow with real income; retirement "
        "withdrawals cover spending minus Social Security. A plan *works* if spending is fully funded to the plan-to "
        "age. The advice levers are found by bisection on the same scenarios.")
    st.caption("Sources: " + "; ".join(a.raw["sources"]))

# ------------------------------------------------------------------ tab 5: limitations
with tab_lim:
    st.subheader("Important features not included (yet)")
    st.markdown(
        "- **Taxes and account location:** no distinction between 401(k), Roth and taxable accounts, no tax drag, "
        "no required minimum distributions or Roth-conversion advice.\n"
        "- **Marital status and spouse:** single-life planning; no spousal Social Security, survivor benefits or joint "
        "life expectancy.\n"
        "- **Real estate and debt:** home equity, mortgages and other debts are ignored.\n"
        "- **Annuities and pensions:** no guaranteed income products or defined-benefit pensions beyond Social Security.\n"
        "- **Inflation is fixed at 2.35%:** real returns are random, but inflation shocks are not modeled separately.\n"
        "- **Returns are lognormal and independent year to year:** no fat tails, momentum or mean reversion in "
        "valuations; capital market assumptions are held constant for the whole horizon.\n"
        "- **Human capital risk:** job loss, disability and health costs are not simulated.\n"
        "- **Behavior:** assumes the client rebalances and never panic-sells.\n"
        "- **Life expectancy:** a Gompertz approximation, not a full actuarial table; no health adjustments.")
    st.caption("Educational project for MSFO 6831 (Georgetown University). Not investment, tax or legal advice.")
