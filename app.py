import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

st.set_page_config(page_title="Retirement Audit App", layout="wide")

# Dark theme
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: white; }
    .stMarkdown, .stText, label { color: white !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("Retirement Audit App 🚀")
st.subheader("Retirement Audit - Accounts, Home Equity & Retirement Income")

# Preferred retirement age
retirement_age = st.slider("Preferred Retirement Age", 50, 80, 65, 1)

tab1, tab2, tab3 = st.tabs(["Spouse 1 / Primary", "Spouse 2 / Partner", "Retirement Income"])

accounts = {"spouse1": {}, "spouse2": {}}

# Spouse tabs - Investment Accounts
for spouse, tab in [("spouse1", tab1), ("spouse2", tab2)]:
    with tab:
        st.markdown(f"### {spouse.replace('spouse1', 'Spouse 1 / Primary').replace('spouse2', 'Spouse 2 / Partner')}")

        spouse_age = st.number_input("Current Age", 18, retirement_age, 30, key=f"{spouse}_age")

        ira_max = 7500
        st.caption(f"Max: ${ira_max:,} (2026)")

        col_l, col_r = st.columns(2)

        with col_l:
            st.markdown("**Traditional IRA**")
            accounts[spouse]["traditional_ira"] = {
                "balance": st.number_input("Current Balance ($)", 0.0, value=0.0, format="%.0f", key=f"{spouse}_trad_ira_bal"),
                "contrib": st.number_input("Annual Contribution ($)", 0.0, float(ira_max), value=0.0, format="%.0f", key=f"{spouse}_trad_ira_cont"),
                "rate": st.slider("Expected Growth Rate (%)", 0.0, 20.0, 10.5, 0.1, key=f"{spouse}_trad_ira_rate")
            }

            st.markdown("**Roth IRA**")
            accounts[spouse]["roth_ira"] = {
                "balance": st.number_input("Current Roth Balance ($)", 0.0, value=0.0, format="%.0f", key=f"{spouse}_roth_bal"),
                "contrib": st.number_input("Annual Roth Contribution ($)", 0.0, float(ira_max), value=0.0, format="%.0f", key=f"{spouse}_roth_cont"),
                "rate": st.slider("Expected Growth Rate (%)", 0.0, 20.0, 10.5, 0.1, key=f"{spouse}_roth_rate")
            }

            st.markdown("**HSA**")
            st.caption("Max: $4,400 individual / $8,750 family (2026)")
            accounts[spouse]["hsa"] = {
                "balance": st.number_input("Current HSA Balance ($)", 0.0, value=0.0, format="%.0f", key=f"{spouse}_hsa_bal"),
                "contrib": st.number_input("Annual HSA Contribution ($)", 0.0, 8750.0, value=0.0, format="%.0f", key=f"{spouse}_hsa_cont"),
                "rate": st.slider("Expected Growth Rate (%)", 0.0, 20.0, 10.5, 0.1, key=f"{spouse}_hsa_rate")
            }

        with col_r:
            k401_max = 24500
            st.caption(f"Max deferral (Traditional + Roth combined): ${k401_max:,} (2026)")

            st.markdown("**Traditional 401(k)**")
            st.caption("Employer match is always Traditional")
            accounts[spouse]["traditional_401k"] = {
                "balance": st.number_input("Current Balance ($)", 0.0, value=0.0, format="%.0f", key=f"{spouse}_trad_401k_bal"),
                "contrib": st.number_input("Your Annual Contribution ($)", 0.0, value=0.0, format="%.0f", key=f"{spouse}_trad_401k_cont"),
                "employer_match": st.number_input("Employer Match ($)", 0.0, value=0.0, format="%.0f", key=f"{spouse}_trad_401k_match"),
                "rate": st.slider("Expected Growth Rate (%)", 0.0, 20.0, 10.5, 0.1, key=f"{spouse}_trad_401k_rate")
            }

            st.markdown("**Roth 401(k)**")
            accounts[spouse]["roth_401k"] = {
                "balance": st.number_input("Current Balance ($)", 0.0, value=0.0, format="%.0f", key=f"{spouse}_roth_401k_bal"),
                "contrib": st.number_input("Your Annual Contribution ($)", 0.0, value=0.0, format="%.0f", key=f"{spouse}_roth_401k_cont"),
                "rate": st.slider("Expected Growth Rate (%)", 0.0, 20.0, 10.5, 0.1, key=f"{spouse}_roth_401k_rate")
            }

            st.markdown("**Brokerage / Taxable**")
            accounts[spouse]["brokerage"] = {
                "balance": st.number_input("Current Balance ($)", 0.0, value=0.0, format="%.0f", key=f"{spouse}_brok_bal"),
                "contrib": st.number_input("Annual Contribution ($)", 0.0, value=0.0, format="%.0f", key=f"{spouse}_brok_cont"),
                "rate": st.slider("Expected Growth Rate (%)", 0.0, 20.0, 10.5, 0.1, key=f"{spouse}_brok_rate")
            }

# ────────────────────────────────────────────────
# Retirement Income (SS + Pension)
# ────────────────────────────────────────────────
with tab3:
    st.markdown("### Income Sources in Retirement")

    st.subheader("Social Security Estimator")
    st.markdown("Enter your average annual earnings over your career to get a rough estimate of your benefit at Full Retirement Age (typically 67).")

    col_est1, col_est2 = st.columns(2)
    with col_est1:
        avg_annual_earnings_sp1 = st.number_input("Spouse 1 Average Annual Earnings ($)", 0, 200000, 60000, step=1000, key="avg_earn_sp1")
    with col_est2:
        avg_annual_earnings_sp2 = st.number_input("Spouse 2 Average Annual Earnings ($)", 0, 200000, 0, step=1000, key="avg_earn_sp2")

    # Simplified SS PIA calculation using 2026 bend points
    def estimate_ss_pia(avg_annual_earnings):
        if avg_annual_earnings == 0:
            return 0
        aime = avg_annual_earnings / 12
        bend1 = 1286
        bend2 = 7749
        pia = (min(aime, bend1) * 0.9 +
               max(0, min(aime - bend1, bend2 - bend1)) * 0.32 +
               max(0, aime - bend2) * 0.15)
        return round(pia * 12)  # Annual benefit

    est_ss_sp1 = estimate_ss_pia(avg_annual_earnings_sp1)
    est_ss_sp2 = estimate_ss_pia(avg_annual_earnings_sp2)

    st.metric("Estimated Annual SS at FRA - Spouse 1", f"${est_ss_sp1:,.0f}")
    st.metric("Estimated Annual SS at FRA - Spouse 2", f"${est_ss_sp2:,.0f}")

    st.info("This is a simplified estimate using the 2026 Primary Insurance Amount (PIA) formula and bend points. Actual benefits depend on 35 highest indexed earnings years, inflation adjustments, and claiming age. For your exact estimate, visit ssa.gov/myaccount.")

    # Manual SS Inputs
    st.subheader("Social Security - Manual Inputs / Override")
    col_ss1, col_ss2 = st.columns(2)
    with col_ss1:
        ss_start_sp1 = st.slider("Claim Age - Spouse 1", 62, 70, 67, key="ss_start_sp1")
        ss_annual_sp1 = st.number_input("Annual SS at Claim Age - Spouse 1 ($)", 0, 60000, est_ss_sp1, step=1000, key="ss_ann_sp1")
    with col_ss2:
        ss_start_sp2 = st.slider("Claim Age - Spouse 2", 62, 70, 67, key="ss_start_sp2")
        ss_annual_sp2 = st.number_input("Annual SS at Claim Age - Spouse 2 ($)", 0, 60000, est_ss_sp2, step=1000, key="ss_ann_sp2")

    st.markdown("### Pension / Defined Benefit (if any)")
    col_pen1, col_pen2 = st.columns(2)
    with col_pen1:
        pension_annual_sp1 = st.number_input("Annual Pension - Spouse 1 ($)", 0, value=0, step=1000, key="pen_sp1")
        pension_cola_sp1 = st.slider("Pension COLA % - Spouse 1", 0.0, 5.0, 2.0, 0.1, key="pen_cola_sp1") / 100
    with col_pen2:
        pension_annual_sp2 = st.number_input("Annual Pension - Spouse 2 ($)", 0, value=0, step=1000, key="pen_sp2")
        pension_cola_sp2 = st.slider("Pension COLA % - Spouse 2", 0.0, 5.0, 2.0, 0.1, key="pen_cola_sp2") / 100

# ────────────────────────────────────────────────
# Home Equity
# ────────────────────────────────────────────────
st.markdown("---")
st.subheader("Home Equity")
home_value = st.number_input("Current Home Value ($)", 0.0, value=0.0, format="%.0f")
mortgage_balance = st.number_input("Remaining Mortgage ($)", 0.0, value=0.0, format="%.0f")
home_appreciation = st.slider("Annual Home Appreciation (%)", 0.0, 10.0, 3.0, 0.1) / 100

include_home = st.checkbox("Include Home Equity in Graph & Net Worth", value=True)

# ────────────────────────────────────────────────
# Mortgage Payoff Calculator
# ────────────────────────────────────────────────
st.markdown("---")
st.subheader("Mortgage Payoff Calculator")

mort_principal = st.number_input("Current Mortgage Balance ($)", 0.0, value=float(mortgage_balance), format="%.2f")
mort_rate_pct = st.number_input("Annual Interest Rate (%)", 0.0, 20.0, 6.5, 0.125)
mort_rate_annual = mort_rate_pct / 100
mort_years = st.number_input("Remaining Term (Years)", 1, 40, 30, 1)
monthly_payment = st.number_input("Standard Monthly Payment ($)", 0.0, value=1500.0, format="%.2f")
extra_monthly = st.number_input("Extra Monthly Payment ($)", 0.0, value=0.0, format="%.2f")

if st.button("Calculate Payoff"):
    monthly_rate = mort_rate_annual / 12

    # No extra payments
    months_no = 0
    bal_no = mort_principal
    interest_no = 0.0
    while bal_no > 0 and months_no < 600:
        interest = bal_no * monthly_rate
        principal = monthly_payment - interest
        if principal <= 0: break
        bal_no -= principal
        interest_no += interest
        months_no += 1
    date_no = datetime.now() + timedelta(days=months_no * 30)

    # With extra payments
    months_yes = 0
    bal_yes = mort_principal
    interest_yes = 0.0
    while bal_yes > 0 and months_yes < 600:
        interest = bal_yes * monthly_rate
        principal = (monthly_payment + extra_monthly) - interest
        if principal <= 0: break
        bal_yes -= principal
        interest_yes += interest
        months_yes += 1
    date_yes = datetime.now() + timedelta(days=months_yes * 30)

    savings = interest_no - interest_yes

    col1, col2, col3 = st.columns(3)
    col1.metric("Payoff Date (no extra)", date_no.strftime("%b %Y"))
    col2.metric("Payoff Date (with extra)", date_yes.strftime("%b %Y"))
    col3.metric("Interest Savings", f"${savings:,.2f}")

# ────────────────────────────────────────────────
# Retirement Projections
# ────────────────────────────────────────────────
total_invest = 0.0
max_years = 0

for spouse in accounts:
    spouse_age = st.session_state.get(f"{spouse}_age", 30)
    years = max(retirement_age - spouse_age, 0)
    max_years = max(max_years, years)

    for acc_type, acc in accounts[spouse].items():
        contrib = acc.get("contrib", 0.0) + acc.get("employer_match", 0.0)
        r = acc.get("rate", 10.5) / 100

        if years > 0:
            if r == 0:
                projected = acc.get("balance", 0.0) + contrib * years
            else:
                projected = (
                    acc.get("balance", 0.0) * (1 + r) ** years +
                    contrib * ((1 + r) ** years - 1) / r
                )
        else:
            projected = acc.get("balance", 0.0)

        total_invest += projected

home_proj_value = home_value * (1 + home_appreciation) ** max_years
home_proj_equity = max(home_proj_value - mortgage_balance, 0)
total_nw = total_invest + (home_proj_equity if include_home else 0)

st.markdown(f"### Projected at Age {retirement_age}")
c1, c2, c3 = st.columns(3)
c1.metric("Investments Total", f"${total_invest:,.0f}")
c2.metric("Home Equity", f"${home_proj_equity:,.0f}" if include_home else "$0")
c3.metric("Total Net Worth", f"${total_nw:,.0f}")

# ────────────────────────────────────────────────
# Growth Graph
# ────────────────────────────────────────────────
st.subheader("Growth Over Time")
years_arr = np.arange(0, max_years + 6)

invest_growth = np.zeros(len(years_arr))
home_growth = np.array([max(home_value * (1 + home_appreciation)**y - mortgage_balance, 0) for y in years_arr])

for y_idx, y in enumerate(years_arr):
    for spouse in accounts:
        spouse_age = st.session_state.get(f"{spouse}_age", 30)
        eff_y = min(y, max(retirement_age - spouse_age, 0))
        for acc_type, acc in accounts[spouse].items():
            contrib = acc.get("contrib", 0.0) + acc.get("employer_match", 0.0)
            r = acc.get("rate", 10.5) / 100
            bal = acc.get("balance", 0.0)
            if r == 0:
                invest_growth[y_idx] += bal + contrib * eff_y
            else:
                invest_growth[y_idx] += bal * (1 + r)**eff_y + contrib * ((1 + r)**eff_y - 1) / r if eff_y > 0 else bal

total_growth = invest_growth + (home_growth if include_home else 0)

fig, ax = plt.subplots(figsize=(12, 6))
ax.plot(years_arr, invest_growth, label="Investments", linewidth=3)
if include_home:
    ax.plot(years_arr, home_growth, label="Home Equity", linewidth=3)
ax.plot(years_arr, total_growth, label="Total Net Worth", linewidth=4, linestyle="--")
ax.set_xlabel("Years from Now")
ax.set_ylabel("Value ($)")
ax.legend()
ax.grid(True, alpha=0.3)
st.pyplot(fig)

# ────────────────────────────────────────────────
# Retirement Withdrawal Simulation
# ────────────────────────────────────────────────
st.markdown("---")
st.subheader("Retirement Withdrawal Simulation (Assumes 10% constant annual growth)")
wd_rate_pct = st.slider("Annual Withdrawal Rate from Investments (%)", 3.0, 12.0, 7.0, 0.1, help="Lower rates are safer for longer retirements.")
wd_rate = wd_rate_pct / 100
wd_years_max = 60
post_growth = 0.10

starting_balance = invest_growth[-1]
if starting_balance <= 0:
    st.warning("No investments projected at retirement — can't simulate withdrawals.")
else:
    annual_wd = starting_balance * wd_rate
    st.write(f"**First-year withdrawal from investments:** ${annual_wd:,.0f} ({wd_rate_pct:.1f}% of starting balance)")

    years_post = np.arange(0, wd_years_max + 1)
    balances = [starting_balance]
    depleted_year = None

    for y in range(1, len(years_post)):
        new_bal = balances[-1] * (1 + post_growth) - annual_wd
        if new_bal <= 0:
            depleted_year = y
            balances.append(0)
            break
        balances.append(new_bal)

    if depleted_year is None:
        depleted_year = wd_years_max + 1
        while len(balances) < len(years_post):
            balances.append(balances[-1])

    fig_wd, ax_wd = plt.subplots(figsize=(12, 6))
    ax_wd.plot(years_post[:len(balances)], balances, label="Portfolio Balance", linewidth=3, color="orange")
    ax_wd.axhline(starting_balance, color="gray", linestyle="--", label="Starting Balance")
    if depleted_year <= wd_years_max:
        ax_wd.axvline(depleted_year, color="red", linestyle="--", label="Depletion Point")
    ax_wd.set_xlabel("Years in Retirement")
    ax_wd.set_ylabel("Balance ($)")
    ax_wd.set_title(f"Withdrawal at {wd_rate_pct:.1f}% – 10% Constant Growth")
    ax_wd.legend()
    ax_wd.grid(True, alpha=0.3)
    st.pyplot(fig_wd)

    # Accurate longevity description
    if depleted_year > 40:
        st.success(f"Your portfolio is projected to last **more than 40 years** (likely well beyond a typical retirement) with money still remaining at the end.")
    elif depleted_year > 30:
        st.success(f"Your portfolio is projected to last **{depleted_year} years** — comfortably covers a standard 30-year retirement with some buffer.")
    elif depleted_year > 25:
        st.info(f"Your portfolio is projected to last **about {depleted_year} years** — covers most 30-year retirements but with limited margin for error.")
    elif depleted_year > 20:
        st.warning(f"Your portfolio is projected to last only {depleted_year} years — may run out before a full 30-year retirement. Consider lowering your withdrawal rate.")
    else:
        st.error(f"Your portfolio is projected to deplete in just {depleted_year} years — high risk of running out early. A lower rate (closer to 4%) is strongly recommended.")

    st.markdown("""
    **Important notes on safe withdrawal rates:**
    - The classic **4% rule** (Trinity Study) targets a high probability of lasting 30 years with inflation-adjusted withdrawals.
    - Recent forward-looking estimates (e.g., Morningstar 2025/2026) suggest around **3.9%** for 90% success over 30 years in current market conditions.
    - This simulation uses constant 10% growth (optimistic long-term average) and no inflation/volatility — real results vary due to sequence risk.
    """)

# Fun part
st.markdown("---")
name = st.text_input("What's your name?")
if name:
    st.write(f"Hello, {name}! Keep building — you're doing great.")
if st.button("Encouragement"):
    st.balloons()
    
