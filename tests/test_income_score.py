"""Livable-income score. These tests do not call Stripe, Supabase, or the Streamlit app.

The old score mostly rewarded a long time horizon and a portfolio that did not
hit zero under a flat withdrawal. The numbers below are that old result next
to the new one for the same portfolio.
"""

from income_score import (
    SAFE_WITHDRAWAL_RATE,
    default_monthly_spending,
    livable_income_assessment,
)


def legacy_withdrawal_score(portfolio, years_to_retirement, withdrawal_rate_pct=4.5, growth_pct=6.0):
    """The previous Retirement Score, kept so the persona tests can show the change."""
    withdrawal = portfolio * withdrawal_rate_pct / 100
    growth = growth_pct / 100
    balance = portfolio
    depleted = None
    if portfolio > 0:
        for year in range(1, 61):
            balance = balance * (1 + growth) - withdrawal
            if balance <= 0:
                depleted = year
                break
    years_last = 60 if depleted is None and portfolio > 0 else (0 if depleted is None else depleted)
    score = 30
    if portfolio > 0:
        score += min(30, years_to_retirement + 5)
    if years_last >= 35:
        score += 25
    elif years_last >= 25:
        score += 18
    elif years_last >= 15:
        score += 10
    if withdrawal_rate_pct <= 4.0:
        score += 10
    elif withdrawal_rate_pct <= 5.0:
        score += 6
    if growth_pct <= 7.0:
        score += 5
    else:
        score += 2
    return max(0, min(100, int(score)))


def test_default_spending_is_eighty_percent_of_income():
    assert default_monthly_spending(60000) == 4000
    assert SAFE_WITHDRAWAL_RATE == 0.04


def test_quarter_million_at_a_modest_income_is_not_a_96():
    """$250k at retirement and a $60k income covers about 79%, not a near-perfect score.

    The old formula scored this 71 because a 4.5% withdrawal never ran the
    portfolio to zero. It still was not 96. A younger household with the same
    $250k and many years of growth can score high only when the income need is
    actually covered.
    """
    result = livable_income_assessment(
        retirement_age=65,
        years_to_retirement=0,
        household_income_today=60000,
        monthly_spending_today=None,
        inflation_rate=0.025,
        portfolio_at_retirement=250000,
        annual_savings=0,
        ss_annual_today=28150,
        pension_annual_at_retirement=0,
        pension_cola=0,
        portfolio_growth_in_retirement=0.06,
    )
    assert legacy_withdrawal_score(250000, 0) == 71
    assert result["score"] == 69
    assert result["score_label"] == "Moderate"
    assert result["coverage_pct"] == 79
    assert result["score"] != 96
    assert result["score"] < 80
    assert "You'll need about $4,000/month" in result["sentence"]
    assert "Your plan covers about $3,179/month (79%)" in result["sentence"]
    assert result["next_step"]
    assert "no years left to save" in result["next_step"].lower()


def test_high_income_and_a_small_balance_drops_from_the_old_strong_score():
    """Age 55, $150k income, about $266k at retirement. Old score 81. New score 39."""
    portfolio = 265797
    result = livable_income_assessment(
        retirement_age=65,
        years_to_retirement=10,
        household_income_today=150000,
        monthly_spending_today=None,
        inflation_rate=0.025,
        portfolio_at_retirement=portfolio,
        annual_savings=5000,
        ss_annual_today=47258,
        pension_annual_at_retirement=0,
        pension_cola=0,
        portfolio_growth_in_retirement=0.06,
    )
    assert legacy_withdrawal_score(portfolio, 10) == 81
    assert result["score"] == 39
    assert result["score_label"] == "Needs attention"
    assert result["coverage_pct"] == 46
    assert "Saving about" in result["next_step"]


def test_a_fifteen_percent_saver_with_time_can_score_strong():
    """Age 35, $80k income, saving $12,000 a year (15%), portfolio about $1.51M at 65."""
    portfolio = 1514142
    result = livable_income_assessment(
        retirement_age=65,
        years_to_retirement=30,
        household_income_today=80000,
        monthly_spending_today=None,
        inflation_rate=0.025,
        portfolio_at_retirement=portfolio,
        annual_savings=12000,
        ss_annual_today=34550,
        pension_annual_at_retirement=0,
        pension_cola=0,
        portfolio_growth_in_retirement=0.06,
    )
    assert legacy_withdrawal_score(portfolio, 30) == 96
    assert result["score"] == 99
    assert result["score_label"] == "Strong"
    assert result["coverage_pct"] == 99
    assert result["lasts_to_95"] is True


def test_need_grows_with_inflation_and_custom_spending_overrides_eighty_percent():
    inflated = livable_income_assessment(
        retirement_age=65,
        years_to_retirement=30,
        household_income_today=60000,
        monthly_spending_today=None,
        inflation_rate=0.025,
        portfolio_at_retirement=0,
        annual_savings=0,
        ss_annual_today=0,
        pension_annual_at_retirement=0,
        pension_cola=0,
        portfolio_growth_in_retirement=0.06,
    )
    assert inflated["needed_monthly_today"] == 4000
    assert inflated["needed_monthly_future"] > inflated["needed_monthly_today"]
    custom = livable_income_assessment(
        retirement_age=65,
        years_to_retirement=0,
        household_income_today=60000,
        monthly_spending_today=3000,
        inflation_rate=0.025,
        portfolio_at_retirement=0,
        annual_savings=0,
        ss_annual_today=0,
        pension_annual_at_retirement=0,
        pension_cola=0,
        portfolio_growth_in_retirement=0.06,
    )
    assert custom["needed_monthly_today"] == 3000
    assert custom["spending_is_default"] is False


def test_a_remaining_mortgage_lowers_the_score_only_when_debt_was_entered():
    shared = dict(
        retirement_age=65,
        years_to_retirement=0,
        household_income_today=60000,
        monthly_spending_today=None,
        inflation_rate=0.025,
        portfolio_at_retirement=250000,
        annual_savings=0,
        ss_annual_today=28150,
        pension_annual_at_retirement=0,
        pension_cola=0,
        portfolio_growth_in_retirement=0.06,
    )
    no_debt = livable_income_assessment(**shared, debt_collected=False, mortgage_at_retirement=0)
    with_debt = livable_income_assessment(**shared, debt_collected=True, mortgage_at_retirement=200000)
    assert with_debt["score"] < no_debt["score"]
    assert with_debt["points"]["debt"] == 0
    assert no_debt["points"]["debt"] == 5
