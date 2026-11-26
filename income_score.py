"""Retirement Score based on a livable income, not only on whether a withdrawal outruns growth.

The income target starts at 80% of current household income (a common replacement
rate, in the same range Ramsey and other planners use) unless the person enters
a monthly spending number. That target is inflated to the retirement year and
keeps growing with inflation through retirement.

Sustainable income is a 4% withdrawal from the projected portfolio plus Social
Security and any pension. Ramsey has talked about withdrawal rates well above
that, including figures around 8%. This score stays at 4% so a high score means
the plan still works at a conservative rate. None of these figures is a promise
of investment returns or of a benefit amount.
"""

from __future__ import annotations

REPLACEMENT_RATE = 0.80
DEFAULT_INFLATION = 0.025
# Conservative on purpose. See the module docstring for the higher rates
# sometimes quoted in Ramsey-style commentary.
SAFE_WITHDRAWAL_RATE = 0.04
TARGET_END_AGE = 95
SAVINGS_RATE_BENCHMARK = 0.15
# Used only to illustrate extra monthly savings. Not a forecast.
GAP_SAVINGS_GROWTH = 0.07

# Points: coverage is the majority of the score. Longevity, the 15% savings
# benchmark, and debt (only when a mortgage was entered) make up the rest.
COVERAGE_POINTS = 70
LONGEVITY_POINTS = 10
SAVINGS_POINTS = 15
DEBT_POINTS = 5


def money(amount: float) -> str:
    return f"${amount:,.0f}"


def default_monthly_spending(household_income_today: float) -> float:
    """80% of current household income, expressed per month in today's dollars."""
    return max(float(household_income_today or 0), 0.0) * REPLACEMENT_RATE / 12.0


def _inflate(amount: float, rate: float, years: int) -> float:
    years = max(int(years or 0), 0)
    if years == 0 or rate == 0:
        return float(amount or 0)
    return float(amount or 0) * (1 + rate) ** years


def _extra_annual_savings(portfolio_gap: float, years: int, annual_rate: float = GAP_SAVINGS_GROWTH) -> float | None:
    if portfolio_gap <= 0 or years <= 0:
        return None
    if annual_rate == 0:
        return portfolio_gap / years
    return portfolio_gap * annual_rate / ((1 + annual_rate) ** years - 1)


def years_portfolio_covers_gap(
    balance: float,
    needed_first: float,
    ss_first: float,
    pension_first: float,
    growth: float,
    inflation: float,
    pension_cola: float,
    years_needed: int,
) -> int:
    """Years the portfolio can fund the gap after Social Security and pension.

    The income need and Social Security both rise with inflation each year.
    The pension rises with its own COLA. A gap of zero means other income
    already covers the need, so the portfolio is not required.
    """
    years_needed = max(int(years_needed or 0), 0)
    bal = max(float(balance or 0), 0.0)
    if years_needed == 0:
        return 0
    for year in range(years_needed):
        need = _inflate(needed_first, inflation, year)
        ss = _inflate(ss_first, inflation, year)
        pension = _inflate(pension_first, pension_cola, year)
        gap = max(0.0, need - ss - pension)
        bal = bal * (1 + growth)
        if gap <= 0:
            continue
        if bal < gap:
            return year
        bal -= gap
    return years_needed


def _coverage_points(ratio: float | None) -> int:
    if ratio is None:
        return 0
    return int(round(COVERAGE_POINTS * max(0.0, min(float(ratio), 1.0))))


def _longevity_points(years_lasted: int, years_needed: int, has_target: bool) -> int:
    if not has_target:
        return 0
    if years_needed <= 0:
        return LONGEVITY_POINTS
    share = years_lasted / years_needed
    if share >= 1:
        return LONGEVITY_POINTS
    if share >= 0.75:
        return 6
    if share >= 0.5:
        return 3
    return 0


def _savings_points(savings_rate: float | None, years_to_retirement: int, ratio: float | None) -> int:
    if years_to_retirement <= 0:
        # Too late to judge a savings rate. Give full credit only when the
        # income target is already covered.
        return SAVINGS_POINTS if ratio is not None and ratio >= 1 else 5
    if savings_rate is None:
        return 0
    if savings_rate >= SAVINGS_RATE_BENCHMARK:
        return SAVINGS_POINTS
    if savings_rate >= 0.10:
        return 10
    if savings_rate >= 0.05:
        return 6
    if savings_rate > 0:
        return 2
    return 0


def _debt_points(debt_collected: bool, mortgage_at_retirement: float, needed_annual_future: float) -> int:
    if not debt_collected:
        return DEBT_POINTS
    remaining = max(float(mortgage_at_retirement or 0), 0.0)
    if remaining <= 0:
        return DEBT_POINTS
    if needed_annual_future > 0 and remaining < needed_annual_future:
        return 3
    return 0


def score_label(score: int) -> tuple[str, str]:
    if score >= 80:
        return "Strong", "green"
    if score >= 60:
        return "Moderate", "yellow"
    return "Needs attention", "red"


def livable_income_assessment(
    *,
    retirement_age: int,
    years_to_retirement: int,
    household_income_today: float,
    monthly_spending_today: float | None,
    inflation_rate: float,
    portfolio_at_retirement: float,
    annual_savings: float,
    ss_annual_today: float,
    pension_annual_at_retirement: float,
    pension_cola: float,
    portfolio_growth_in_retirement: float,
    debt_collected: bool = False,
    mortgage_at_retirement: float = 0.0,
) -> dict:
    """Score and the plain-language income comparison.

    Social Security is treated as today's dollars and inflated to retirement
    with the inflation rate (a COLA). The pension amount is the annual benefit
    at retirement; after that it grows at pension_cola. The portfolio balance
    is already the projected balance at retirement, so the 4% withdrawal is in
    retirement-year dollars.
    """
    years_to_retirement = max(int(years_to_retirement or 0), 0)
    retirement_age = int(retirement_age or 65)
    inflation_rate = float(inflation_rate or 0)
    household_income_today = max(float(household_income_today or 0), 0.0)
    if monthly_spending_today is None:
        monthly_today = default_monthly_spending(household_income_today)
        spending_is_default = True
    else:
        monthly_today = max(float(monthly_spending_today or 0), 0.0)
        spending_is_default = False
    needed_annual_today = monthly_today * 12.0
    needed_annual_future = _inflate(needed_annual_today, inflation_rate, years_to_retirement)
    ss_future = _inflate(max(float(ss_annual_today or 0), 0.0), inflation_rate, years_to_retirement)
    pension_future = max(float(pension_annual_at_retirement or 0), 0.0)
    portfolio = max(float(portfolio_at_retirement or 0), 0.0)
    portfolio_income = portfolio * SAFE_WITHDRAWAL_RATE
    sustainable_annual_future = portfolio_income + ss_future + pension_future
    has_target = needed_annual_future > 0
    ratio = (sustainable_annual_future / needed_annual_future) if has_target else None

    years_needed = max(TARGET_END_AGE - retirement_age, 0)
    years_lasted = years_portfolio_covers_gap(
        balance=portfolio,
        needed_first=needed_annual_future,
        ss_first=ss_future,
        pension_first=pension_future,
        growth=float(portfolio_growth_in_retirement or 0),
        inflation=inflation_rate,
        pension_cola=float(pension_cola or 0),
        years_needed=years_needed,
    )
    savings_rate = None
    if household_income_today > 0:
        savings_rate = max(float(annual_savings or 0), 0.0) / household_income_today

    coverage_pts = _coverage_points(ratio)
    longevity_pts = _longevity_points(years_lasted, years_needed, has_target)
    savings_pts = _savings_points(savings_rate, years_to_retirement, ratio) if has_target else 0
    debt_pts = _debt_points(debt_collected, mortgage_at_retirement, needed_annual_future) if has_target else 0
    score = max(0, min(100, coverage_pts + longevity_pts + savings_pts + debt_pts))
    label, css = score_label(score)

    shortfall_annual = max(0.0, needed_annual_future - sustainable_annual_future) if has_target else 0.0
    extra_portfolio = (shortfall_annual / SAFE_WITHDRAWAL_RATE) if shortfall_annual > 0 else 0.0
    extra_annual = _extra_annual_savings(extra_portfolio, years_to_retirement)
    extra_monthly = (extra_annual / 12.0) if extra_annual else None

    coverage_pct = int(round(ratio * 100)) if ratio is not None else None
    needed_monthly_today = needed_annual_today / 12.0
    needed_monthly_future = needed_annual_future / 12.0
    covered_monthly_future = sustainable_annual_future / 12.0

    if not has_target:
        sentence = (
            "Add household income or a monthly spending amount so this score can judge a livable retirement income."
        )
        next_step = None
    else:
        sentence = (
            f"You'll need about {money(needed_monthly_future)}/month in retirement "
            f"(in future dollars, ~{money(needed_monthly_today)} in today's dollars). "
            f"Your plan covers about {money(covered_monthly_future)}/month ({coverage_pct}%)."
        )
        if ratio is not None and ratio >= 1:
            next_step = None
        elif years_to_retirement <= 0:
            next_step = (
                f"This illustration is short about {money(shortfall_annual / 12.0)}/month at retirement. "
                "With no years left to save, the levers are a lower spending target or a larger balance. "
                "This is not a guarantee."
            )
        elif extra_monthly:
            next_step = (
                f"Saving about {money(extra_monthly)} more each month until retirement would close that gap "
                f"in this illustration, at {GAP_SAVINGS_GROWTH:.0%} growth. That growth is an assumption, not a guarantee."
            )
        else:
            next_step = None

    return {
        "score": score,
        "score_label": label,
        "score_class": css,
        "needed_monthly_today": needed_monthly_today,
        "needed_monthly_future": needed_monthly_future,
        "covered_monthly_future": covered_monthly_future,
        "needed_annual_today": needed_annual_today,
        "needed_annual_future": needed_annual_future,
        "sustainable_annual_future": sustainable_annual_future,
        "ss_annual_future": ss_future,
        "pension_annual_future": pension_future,
        "portfolio_income_future": portfolio_income,
        "coverage_ratio": ratio,
        "coverage_pct": coverage_pct,
        "years_needed_to_95": years_needed,
        "years_portfolio_lasts": years_lasted,
        "lasts_to_95": years_needed <= 0 or years_lasted >= years_needed,
        "savings_rate": savings_rate,
        "extra_monthly_savings": extra_monthly,
        "spending_is_default": spending_is_default,
        "sentence": sentence,
        "next_step": next_step,
        "points": {
            "coverage": coverage_pts,
            "longevity": longevity_pts,
            "savings": savings_pts,
            "debt": debt_pts,
        },
    }
