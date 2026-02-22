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
st.subheader("Retirement Audit - Accounts & Home Equity")

# Preferred retirement age
retirement_age = st.slider("Preferred Retirement Age", 50, 80, 65, 1)

tab1, tab2 = st.tabs(["Spouse 1 / Primary", "Spouse 2 / Partner"])

accounts = {"spouse1": {}, "spouse2": {}}

for spouse, tab in [("spouse1", tab1), ("spouse2", tab2)]:
    with tab:
        st.markdown(f"### {spouse.replace('spouse1', 'Spouse 1 / Primary').replace('spouse2', 'Spouse 2 / Partner')}")

        spouse_age = st.number_input("Age", 18, retirement_age, 30, key=f"{spouse}_age")

        # 2026 IRA limits
        ira_base = 7500
        ira_catchup = 1100 if spouse_age >= 50 else 0
        ira_max = ira_base + ira_catchup
        st.caption(f"IRA Max: ${ira_base:,} (2026) + ${ira_catchup:,} catch-up = **${ira_max:,}**")

        col_l, col_r = st.columns(2)

        with col_l:
            st.markdown("**IRA**")
            accounts[spouse]["ira"] = {
                "balance": st.number_input("Current IRA Balance ($)", 0.0, value=0.0, format="%.0f", key=f"{spouse}_ira_balance"),
                "contrib": st.number_input("Annual IRA Contribution ($)", 0.0, float(ira_max), value=0.0, format="%.0f", key=f"{spouse}_ira_contrib"),
                "rate": st.slider("Growth Rate (%)", 0.0, 20.0, 10.5, 0.1, key=f"{spouse}_ira_rate")
            }

            st.markdown("**HSA**")
            st.caption("Max: $4,400 individual / $8,750 family (2026)")
            accounts[spouse]["hsa"] = {
                "balance": st.number_input("Current HSA Balance ($)", 0.0, value=0.0, format="%.0f", key=f"{spouse}_hsa_balance"),
                "contrib": st.number_input("Annual HSA Contribution ($)", 0.0, 8750.0, value=0.0, format="%.0f", key=f"{spouse}_hsa_contrib"),
                "rate": st.slider("Growth Rate (%)", 0.0, 20.0, 10.5, 0.1, key=f"{spouse}_hsa_rate")
            }

        with col_r:
            st.markdown("**401k**")
            st.caption("Employer match is always Traditional")
            accounts[spouse]["401k"] = {
                "balance": st.number_input("Current 401k Balance ($)", 0.0, value=0.0, format="%.0f", key=f"{spouse}_401k_balance"),
                "contrib": st.number_input("Your Annual 401k Contribution ($)", 0.0, value=0.0, format="%.0f", key=f"{spouse}_401k_contrib"),
                "employer_match": st.number_input("Employer Match ($)", 0.0, value=0.0, format="%.0f", key=f"{spouse}_401k_match"),
                "rate": st.slider("Growth Rate (%)", 0.0, 20.0, 10.5, 0.1, key=f"{spouse}_401k_rate")
            }

            st.markdown("**Brokerage / Taxable**")
            accounts[spouse]["brokerage"] = {
                "balance": st.number_input("Current Brokerage Balance ($)", 0.0, value=0.0, format="%.0f", key=f"{spouse}_brokerage_balance"),
                "contrib": st.number_input("Annual Brokerage Contribution ($)", 0.0, value=0.0, format="%.0f", key=f"{spouse}_brokerage_contrib"),
                "rate": st.slider("Growth Rate (%)", 0.0, 20.0, 10.5, 0.1, key=f"{spouse}_brokerage_rate")
            }

# ────────────────────────────────────────────────
# Home Equity
# ────────────────────────────────────────────────
st.markdown("---")
st.subheader("Home Equity")
home_value = st.number_input("Current Home Value ($)", 0.0, value=400000.0, format="%.0f")
mortgage_balance = st.number_input("Remaining Mortgage ($)", 0.0, value=200000.0, format="%.0f")
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
        if acc_type == "age": continue

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
            if acc_type == "age": continue
            contrib = acc.get("contrib", 0.0) + acc.get("employer_match", 0.0)
            r = acc.get("rate", 10.5) / 100
            if r == 0:
                invest_growth[y_idx] += acc.get("balance", 0.0) + contrib * eff_y
            else:
                invest_growth[y_idx] += acc.get("balance", 0.0) * (1 + r)**eff_y + contrib * ((1 + r)**eff_y - 1) / r if eff_y > 0 else acc.get("balance", 0.0)

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
st.subheader("Retirement Withdrawal Simulation (10% avg annual growth)")
wd_rate_pct = st.slider("Annual Withdrawal Rate (%)", 5.0, 15.0, 7.0, 0.5)
wd_rate = wd_rate_pct / 100
wd_years = 30
post_growth = 0.10

annual_wd = total_invest * wd_rate
st.write(f"**Annual Withdrawal Amount:** ${annual_wd:,.0f} ({wd_rate_pct:.1f}%)")

years_post = np.arange(0, wd_years + 1)
balances = [total_invest]
for y in range(1, len(years_post)):
    new_bal = balances[-1] * (1 + post_growth) - annual_wd
    balances.append(max(new_bal, 0))

fig_wd, ax_wd = plt.subplots(figsize=(12, 6))
ax_wd.plot(years_post, balances, label="Portfolio Balance", linewidth=3, color="orange")
ax_wd.axhline(total_invest, color="gray", linestyle="--", label="Starting Balance")
ax_wd.set_xlabel("Years in Retirement")
ax_wd.set_ylabel("Balance ($)")
ax_wd.set_title(f"Withdrawal at {wd_rate_pct:.1f}% – 10% Growth")
ax_wd.legend()
ax_wd.grid(True, alpha=0.3)
st.pyplot(fig_wd)

if balances[-1] > total_invest * 1.1:
    st.success("Portfolio is projected to **grow** over 30 years.")
elif balances[-1] > total_invest * 0.9:
    st.info("Portfolio is projected to **stay roughly stable** over 30 years.")
else:
    st.warning("Portfolio is projected to **decrease or deplete** over 30 years.")

# Fun section
st.markdown("---")
st.write("What's your name?")
name = st.text_input("Enter here")
if name:
    st.write(f"Hello, {name}! You're building something awesome.")

if st.button("Click me for encouragement"):
    st.balloons()
    