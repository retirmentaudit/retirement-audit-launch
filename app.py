import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

# Make sidebar always open
st.set_page_config(initial_sidebar_state="expanded", layout="wide")

# --- Main App ---
st.title("Retirement Audit App 🚀")

st.subheader("Retirement Audit - Accounts & Home Equity")

# Preferred retirement age
retirement_age = st.slider("Preferred Retirement Age", min_value=50, max_value=80, value=65, step=1, key="retirement_age")

# Tabs for Spouse 1 and Spouse 2
tab_spouse1, tab_spouse2 = st.tabs(["Spouse 1 / Primary", "Spouse 2 / Partner"])

accounts = {"spouse1": {}, "spouse2": {}}

for spouse, tab in [("spouse1", tab_spouse1), ("spouse2", tab_spouse2)]:
    with tab:
        st.markdown(f"### {spouse.replace('spouse1', 'Spouse 1 / Primary').replace('spouse2', 'Spouse 2 / Partner')} Accounts")

        # Single age input for the spouse
        spouse_age = st.number_input("Age (applies to all accounts below)", min_value=18, max_value=100, value=30, key=f"{spouse}_age")

        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("**IRA**")
            st.caption("Max annual contribution: $7,000 (2025 limit)")
            accounts[spouse]["ira"] = {
                "age": spouse_age,
                "balance": st.number_input("Current IRA Balance ($)", min_value=0.0, value=0.0, format="%.0f", key=f"{spouse}_ira_balance"),
                "contrib": st.number_input("Annual IRA Contribution ($)", min_value=0.0, max_value=7000.0, value=0.0, format="%.0f", key=f"{spouse}_ira_contrib"),
                "rate": st.slider("Growth Rate (%)", 0.0, 20.0, value=7.0, step=0.1, key=f"{spouse}_ira_rate")
            }

            st.markdown("**HSA**")
            st.caption("Max annual contribution: $4,150 individual / $8,300 family (2025 limit)")
            accounts[spouse]["hsa"] = {
                "age": spouse_age,
                "balance": st.number_input("Current HSA Balance ($)", min_value=0.0, value=0.0, format="%.0f", key=f"{spouse}_hsa_balance"),
                "contrib": st.number_input("Annual HSA Contribution ($)", min_value=0.0, max_value=8300.0, value=0.0, format="%.0f", key=f"{spouse}_hsa_contrib"),
                "rate": st.slider("Growth Rate (%)", 0.0, 20.0, value=7.0, step=0.1, key=f"{spouse}_hsa_rate")
            }

        with col_right:
            st.markdown("**401k**")
            st.caption("Employer match is always Traditional")
            accounts[spouse]["401k"] = {
                "age": spouse_age,
                "balance": st.number_input("Current 401k Balance ($)", min_value=0.0, value=0.0, format="%.0f", key=f"{spouse}_401k_balance"),
                "contrib": st.number_input("Your Annual 401k Contribution ($)", min_value=0.0, value=0.0, format="%.0f", key=f"{spouse}_401k_contrib"),
                "employer_match": st.number_input("Employer Match ($)", min_value=0.0, value=0.0, format="%.0f", key=f"{spouse}_401k_match"),
                "type": st.selectbox("Your Contribution Type", ["Traditional", "Roth"], key=f"{spouse}_401k_type"),
                "rate": st.slider("Growth Rate (%)", 0.0, 20.0, value=7.0, step=0.1, key=f"{spouse}_401k_rate")
            }

            st.markdown("**Brokerage / Taxable**")
            accounts[spouse]["brokerage"] = {
                "age": spouse_age,
                "balance": st.number_input("Current Brokerage Balance ($)", min_value=0.0, value=0.0, format="%.0f", key=f"{spouse}_brokerage_balance"),
                "contrib": st.number_input("Annual Brokerage Contribution ($)", min_value=0.0, value=0.0, format="%.0f", key=f"{spouse}_brokerage_contrib"),
                "rate": st.slider("Growth Rate (%)", 0.0, 20.0, value=7.0, step=0.1, key=f"{spouse}_brokerage_rate")
            }

st.markdown("### Home Equity")
home_value = st.number_input("Current Home Value ($)", min_value=0.0, value=400000.0, format="%.0f", key="home_value")
mortgage_balance = st.number_input("Remaining Mortgage ($)", min_value=0.0, value=200000.0, format="%.0f", key="mortgage_balance")
home_appreciation = st.slider("Annual Home Appreciation (%)", 0.0, 10.0, value=3.0, step=0.1, key="home_apprec")

# Calculate total investments projection
total_investments_projected = 0
for spouse_accounts in accounts.values():
    for acc_type, acc in spouse_accounts.items():
        years = retirement_age - acc["age"]
        contrib = acc["contrib"]
        if acc_type == "401k":
            contrib += acc["employer_match"]
        if years > 0:
            projected = acc["balance"] * (1 + acc["rate"]/100)**years + contrib * (((1 + acc["rate"]/100)**years - 1) / (acc["rate"]/100 if acc["rate"] > 0 else years))
        else:
            projected = acc["balance"]
        total_investments_projected += projected

# Home equity projection
home_years = retirement_age - 35
if home_years > 0:
    projected_home_value = home_value * (1 + home_appreciation/100)**home_years
    projected_home_equity = max(projected_home_value - mortgage_balance, 0)
else:
    projected_home_equity = max(home_value - mortgage_balance, 0)

total_net_worth = total_investments_projected + projected_home_equity

# Metrics
st.markdown(f"### Projected at Age {retirement_age}")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Investments Total", f"${total_investments_projected:,.0f}")
col2.metric("Projected Home Value", f"${projected_home_value:,.0f}" if 'projected_home_value' in locals() else f"${home_value:,.0f}")
col3.metric("Home Equity", f"${projected_home_equity:,.0f}")
col4.metric("Total Net Worth", f"${total_net_worth:,.0f}")

# Growth Graph
st.subheader("Growth Over Time")

max_years = max((retirement_age - acc["age"] for spouse_accounts in accounts.values() for acc in spouse_accounts.values()), default=30) + 5
years = np.arange(0, max_years + 1)

investment_growth = np.zeros(len(years))
for spouse_accounts in accounts.values():
    for acc_type, acc in spouse_accounts.items():
        contrib = acc["contrib"]
        if acc_type == "401k":
            contrib += acc["employer_match"]
        growth = np.array([acc["balance"] * (1 + acc["rate"]/100)**y + contrib * (((1 + acc["rate"]/100)**y - 1) / (acc["rate"]/100 if acc["rate"] > 0 else y)) for y in years])
        investment_growth += growth

home_growth = np.array([home_value * (1 + home_appreciation/100)**y - mortgage_balance for y in years])
home_growth = np.maximum(home_growth, 0)

total_growth = investment_growth + home_growth

fig, ax = plt.subplots(figsize=(12, 6))
ax.plot(years, investment_growth, label="Investments", linewidth=3)
ax.plot(years, home_growth, label="Home Equity", linewidth=3)
ax.plot(years, total_growth, label="Total Net Worth", linewidth=4, linestyle="--")
ax.set_xlabel("Years from Now")
ax.set_ylabel("Value ($)")
ax.set_title(f"Retirement Growth Projection (to Age {retirement_age})")
ax.legend()
ax.grid(True, alpha=0.3)
st.pyplot(fig)

# Fun test stuff (keep the balloons!)
st.write("What's your name?")
name = st.text_input("Enter here")
if name:
    st.write(f"Hello, {name}! You're building something awesome.")

if st.button("Click me for encouragement"):
    st.balloons()
    