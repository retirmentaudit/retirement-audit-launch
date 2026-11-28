"""Monthly repayment estimates for Loan Plan Audit.

Pure functions. No Streamlit, Stripe, or network calls.

Payments under RAP are rounded to the nearest dollar so published examples
match ($53,000 of AGI → $221; one dependent → $171). Brackets follow the
statute at exact multiples of $10,000: $20,000 is 1%, $100,000 is 9%, and
amounts above $100,000 are 10%. A published table may differ by one bracket
at those exact amounts.

The interest rate used for every plan is the balance-weighted average APR.
Auto-pay, when the toggle is on, subtracts one percentage point. The toggle
defaults off. IBR's payment cap is the 10-year standard payment on the
starting balance. Unpaid IBR interest is added to the balance. RAP unpaid
interest is not added, and the principal match is modeled on the combined
balance once a month.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from states import normalize_state, poverty_region

RULES_LAST_CHECKED = date(2026, 11, 26)
RULES_LAST_CHECKED_LABEL = "November 26, 2026"
PAYE_SUNSET = date(2028, 7, 1)
DEFAULT_START = date(2026, 12, 1)
DISCOUNT_RATE = 0.03
PSLF_PAYMENTS = 120
RAP_PAYMENTS = 360
DUST = 0.05

# 2026 HHS poverty guidelines. Contiguous figures are from the spec.
# Alaska and Hawaii are the same Federal Register notice (2026-00755).
_POVERTY = {
    "contiguous": (15_960, 5_680),
    "AK": (19_950, 7_100),
    "HI": (18_360, 6_530),
}

LOAN_TYPES = (
    "Direct Subsidized",
    "Direct Unsubsidized",
    "Grad PLUS",
    "Consolidation",
    "Parent PLUS",
    "FFEL",
    "Not sure",
)

PLAN_STANDARD = "standard_10"
PLAN_GRADUATED = "graduated"
PLAN_EXTENDED = "extended"
PLAN_TIERED = "tiered_standard"
PLAN_RAP = "rap"
PLAN_IBR15 = "ibr_15"
PLAN_IBR10 = "ibr_10"
PLAN_PAYE = "paye_bridge"
PLAN_ICR = "icr"

LABELS = {
    PLAN_STANDARD: "Standard (10-year)",
    PLAN_GRADUATED: "Graduated",
    PLAN_EXTENDED: "Extended (25-year)",
    PLAN_TIERED: "Tiered Standard",
    PLAN_RAP: "RAP",
    PLAN_IBR15: "IBR (15%)",
    PLAN_IBR10: "IBR (10%)",
    PLAN_PAYE: "PAYE until July 1, 2028",
    PLAN_ICR: "ICR until July 1, 2028",
}

# Income percentage factors for July 1, 2026 through June 30, 2027.
# Federal Register notice 2026-11540 (June 9, 2026), Attachment 1.
_ICR_SINGLE = (
    (13_717, 55.00),
    (18_873, 57.79),
    (24_285, 60.57),
    (29_819, 66.23),
    (35_104, 71.89),
    (41_769, 80.33),
    (52_462, 88.77),
    (65_798, 100.00),
    (79_138, 100.00),
    (95_112, 111.80),
    (121_787, 123.50),
    (172_492, 141.20),
    (197_779, 150.00),
    (352_277, 200.00),
)
_ICR_MARRIED = (
    (13_717, 50.52),
    (21_641, 56.68),
    (25_790, 59.56),
    (33_717, 67.79),
    (41_769, 75.22),
    (52_462, 87.61),
    (65_797, 100.00),
    (79_138, 100.00),
    (99_146, 109.40),
    (132_481, 125.00),
    (179_158, 140.60),
    (250_560, 150.00),
    (409_433, 200.00),
)


def money(value: float) -> float:
    """Round half up to the cent."""
    return float(Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def rap_percent_points(agi: float) -> int | None:
    """Statute percentage points, or None for the flat $120 bracket (AGI ≤ $10,000)."""
    cents = int(Decimal(str(agi)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) * 100)
    if cents <= 1_000_000:
        return None
    bracket = (cents + 1_000_000 - 1) // 1_000_000
    return min(10, int(bracket - 1))


def rap_unrounded_monthly(agi: float, dependents: int) -> Decimal:
    points = rap_percent_points(agi)
    if points is None:
        base = Decimal("120")
    else:
        base = Decimal(str(agi)) * Decimal(points) / Decimal("100")
    monthly = base / Decimal("12") - Decimal(50) * Decimal(max(0, int(dependents)))
    if monthly < Decimal("10"):
        return Decimal("10")
    return monthly


def rap_payment_dollars(agi: float, dependents: int) -> int:
    """Nearest dollar, half up, after the $10 floor."""
    return int(rap_unrounded_monthly(agi, dependents).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def amort_payment(principal: float, monthly_rate: float, months: int) -> float:
    """Fixed payment. A zero rate returns principal / months."""
    if months <= 0 or principal <= 0:
        return 0.0
    if abs(monthly_rate) < 1e-15:
        return principal / months
    return principal * monthly_rate / (1 - (1 + monthly_rate) ** (-months))


def tiered_term_months(balance: float) -> int:
    """Term by total principal. $24,999 → 10 years. $25,000 → 15 years."""
    if balance < 25_000:
        return 120
    if balance < 50_000:
        return 180
    if balance < 100_000:
        return 240
    return 300


def consolidation_term_months(balance: float) -> int:
    """Long-standing Direct Consolidation term. Not reprinted on the SAVE article."""
    if balance < 7_500:
        return 120
    if balance < 10_000:
        return 144
    if balance < 20_000:
        return 180
    if balance < 40_000:
        return 240
    if balance < 60_000:
        return 300
    return 360


def income_percentage_factor(agi: float, filing_status: str) -> float:
    """2026–27 ICR factor as a decimal. AGI outside the table uses the end factor."""
    table = _ICR_MARRIED if filing_status in {"mfj", "hoh"} else _ICR_SINGLE
    income = float(agi)
    if income <= table[0][0]:
        percent = table[0][1]
    elif income >= table[-1][0]:
        percent = table[-1][1]
    else:
        percent = table[-1][1]
        for (low_agi, low_factor), (high_agi, high_factor) in zip(table, table[1:]):
            if low_agi <= income <= high_agi:
                span = high_agi - low_agi
                share = 0.0 if span == 0 else (income - low_agi) / span
                raw = low_factor + share * (high_factor - low_factor)
                percent = float(Decimal(str(raw)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
                break
    return percent / 100


def icr_monthly(agi: float, scenario: ScenarioInput, year_offset: int, twelve_year_base: float) -> float:
    """Lesser of 20% of (AGI − 100% of poverty) / 12 and the 12-year payment times the factor."""
    poverty = poverty_guideline(scenario.family_size, scenario.state, year_offset, scenario.poverty_inflation)
    discretionary = max(0.0, agi - poverty)
    income_side = 0.20 * discretionary / 12
    factor = income_percentage_factor(agi, scenario.filing_status)
    return min(income_side, max(0.0, twelve_year_base) * factor)


def graduated_schedule(balance: float, monthly_rate: float, term_months: int) -> list[float]:
    """Payments rise every 24 months. The last step is three times the first, and the first covers opening interest."""
    term_months = max(1, int(term_months))
    steps: list[int] = []
    left = term_months
    while left > 0:
        steps.append(min(24, left))
        left -= steps[-1]
    count = len(steps)

    def ending(first: float) -> float:
        remaining = max(0.0, balance)
        for index, length in enumerate(steps):
            fraction = 0.0 if count == 1 else index / (count - 1)
            payment = first * (1 + 2 * fraction)
            for _ in range(length):
                if remaining <= DUST:
                    return 0.0
                interest = remaining * monthly_rate
                due = min(payment, remaining + interest)
                remaining = remaining + interest - due
                if remaining <= DUST:
                    remaining = 0.0
        return remaining

    low, high = 0.0, max(balance, 1.0)
    for _ in range(64):
        mid = (low + high) / 2
        if ending(mid) > DUST:
            low = mid
        else:
            high = mid
    first = max(high, balance * monthly_rate)
    payments: list[float] = []
    for index, length in enumerate(steps):
        fraction = 0.0 if count == 1 else index / (count - 1)
        payments.extend([first * (1 + 2 * fraction)] * length)
    return payments


def poverty_guideline(family_size: int, state: str, year_offset: int = 0, inflation: float = 0.0) -> float:
    """Annual guideline. year_offset 0 is the 2026 table. Later years grow by `inflation`."""
    size = max(1, int(family_size))
    base, increment = _POVERTY[poverty_region(state)]
    amount = base + increment * (size - 1)
    if year_offset:
        amount *= (1 + inflation) ** year_offset
    return amount


def discretionary_income(agi: float, family_size: int, state: str, year_offset: int, inflation: float) -> float:
    return max(0.0, agi - 1.5 * poverty_guideline(family_size, state, year_offset, inflation))


def add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + int(months)
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def months_until(start: date, deadline: date) -> int:
    """How many first-of-month payment dates fall strictly before `deadline`."""
    count = 0
    cursor = date(start.year, start.month, 1)
    limit = date(deadline.year, deadline.month, 1)
    while cursor < limit and count < 1200:
        count += 1
        cursor = add_months(cursor, 1)
    return count


def format_duration(months: int) -> str:
    months = max(0, int(months))
    years, rem = divmod(months, 12)
    return f"{years}y {rem}m"


def present_value(payments: list[float], annual_rate: float = DISCOUNT_RATE) -> float:
    monthly = annual_rate / 12
    total = 0.0
    for index, amount in enumerate(payments, start=1):
        total += amount / ((1 + monthly) ** index)
    return total


@dataclass(frozen=True)
class LoanInput:
    balance: float
    rate_pct: float
    loan_type: str
    disbursed_on_or_after_july_2026: str = "no"
    repaid_parent_plus: bool = False


@dataclass(frozen=True)
class ScenarioInput:
    loans: tuple[LoanInput, ...]
    agi: float
    filing_status: str
    spouse_agi: float
    dependents: int
    family_size: int
    state: str
    pslf_job: bool = False
    annual_raise: float = 0.03
    poverty_inflation: float = 0.025
    autopay: bool = False
    federal_tax_pct: float = 0.22
    state_tax_pct: float = 0.0
    extra_monthly: float = 0.0
    pslf_months_credited: int = 0
    idr_months_credited: int = 0
    new_borrower_after_2014: str = "no"
    on_save: bool = False
    start_date: date = DEFAULT_START


@dataclass
class MonthRecord:
    payment: float
    interest_accrued: float
    interest_paid: float
    principal: float
    waived: float
    matched: float
    balance: float


@dataclass
class PlanResult:
    plan_id: str
    label: str
    eligible: bool
    chips: list[str]
    counts_for_pslf: bool
    first_year_monthly: float | None = None
    total_paid: float | None = None
    total_paid_pv: float | None = None
    interest_paid: float | None = None
    interest_waived: float | None = None
    principal_matched: float | None = None
    end_month: int | None = None
    end_date: str | None = None
    end_reason: str | None = None
    forgiven_amount: float | None = None
    estimated_tax: float | None = None
    pslf_date: str | None = None
    term_months: int | None = None
    yearly: list = field(default_factory=list)
    notes: list = field(default_factory=list)


@dataclass
class AuditResult:
    ok: bool
    errors: list[str]
    total_balance: float
    weighted_rate_pct: float
    modeled_rate_pct: float
    agi_used: float
    uncertain: bool
    worlds: dict[str, list[PlanResult]]
    notes: list[str]
    on_save: bool
    state: str
    start_date: str


def combined_agi(scenario: ScenarioInput) -> float:
    """MFJ uses both incomes. Every other status uses the borrower's AGI only."""
    if scenario.filing_status == "mfj":
        return float(scenario.agi) + float(scenario.spouse_agi or 0)
    return float(scenario.agi)


def weighted_rate_pct(loans: tuple[LoanInput, ...]) -> float:
    total = sum(max(0.0, loan.balance) for loan in loans)
    if total <= 0:
        return 0.0
    return sum(max(0.0, loan.balance) * loan.rate_pct for loan in loans) / total


def modeled_rate_pct(weighted: float, autopay: bool) -> float:
    rate = max(0.0, weighted)
    if autopay:
        rate = max(0.0, rate - 1.0)
    return rate


def _blocks_rap(loan: LoanInput) -> str | None:
    if loan.loan_type == "Parent PLUS":
        return "Parent PLUS"
    if loan.loan_type == "FFEL":
        return "FFEL"
    if loan.loan_type == "Consolidation" and loan.repaid_parent_plus:
        return "Parent PLUS"
    return None


def rap_block_reason(loans: tuple[LoanInput, ...]) -> str | None:
    reasons = []
    for loan in loans:
        reason = _blocks_rap(loan)
        if reason and reason not in reasons:
            reasons.append(reason)
    if not reasons:
        return None
    if reasons == ["Parent PLUS"]:
        return "Not modeled for Parent PLUS"
    if reasons == ["FFEL"]:
        return "Not modeled for FFEL"
    return "Not modeled for Parent PLUS or FFEL"


def _has_parent(loans: tuple[LoanInput, ...]) -> bool:
    return any(loan.loan_type == "Parent PLUS" for loan in loans)


def _has_parent_consolidation(loans: tuple[LoanInput, ...]) -> bool:
    return any(loan.loan_type == "Consolidation" and loan.repaid_parent_plus for loan in loans)


def _has_ffel(loans: tuple[LoanInput, ...]) -> bool:
    return any(loan.loan_type == "FFEL" for loan in loans)


def _sunset_successor(scenario: ScenarioInput, rap_reason: str | None) -> tuple[str, int | None, str, float | None]:
    """Plan to continue after July 1, 2028. The StudentAid page does not name the successor."""
    if rap_reason is None:
        return "rap", RAP_PAYMENTS, "RAP", None
    if _has_parent(scenario.loans) or _has_parent_consolidation(scenario.loans):
        return "fixed", None, "Standard", None
    if scenario.new_borrower_after_2014 == "yes":
        return "ibr10", 240, "IBR", None
    return "ibr15", 300, "IBR", None


def disbursement_status(loans: tuple[LoanInput, ...]) -> str:
    """post, pre, or uncertain. Any confirmed on-or-after date selects post for every loan."""
    flags = [loan.disbursed_on_or_after_july_2026 for loan in loans]
    if any(flag == "yes" for flag in flags):
        return "post"
    if any(flag == "not_sure" for flag in flags):
        return "uncertain"
    return "pre"


def validate_scenario(scenario: ScenarioInput) -> list[str]:
    errors = []
    if not scenario.loans:
        errors.append("Add at least one loan.")
    elif sum(loan.balance for loan in scenario.loans) <= 0:
        errors.append("Enter a balance greater than zero.")
    for loan in scenario.loans:
        if loan.balance < 0:
            errors.append("Balances cannot be negative.")
            break
        if loan.rate_pct < 0 or loan.rate_pct > 20:
            errors.append("Enter an interest rate from 0 to 20 percent.")
            break
        if loan.disbursed_on_or_after_july_2026 not in {"yes", "no", "not_sure"}:
            errors.append("Choose whether each loan was first disbursed before or after July 1, 2026.")
            break
    if scenario.agi < 0 or scenario.spouse_agi < 0:
        errors.append("Enter income as zero or a positive amount.")
    if scenario.filing_status not in {"single", "hoh", "mfj", "mfs"}:
        errors.append("Choose a filing status.")
    if scenario.dependents < 0 or scenario.dependents > 15:
        errors.append("Enter dependents from 0 to 15.")
    if scenario.family_size < 1 or scenario.family_size > 15:
        errors.append("Enter a family size from 1 to 15.")
    if normalize_state(scenario.state) is None:
        errors.append("Choose your state of residence.")
    if scenario.new_borrower_after_2014 not in {"yes", "no", "not_sure"}:
        errors.append("Choose whether your first loan was after July 1, 2014.")
    if scenario.pslf_months_credited < 0 or scenario.idr_months_credited < 0:
        errors.append("Credited months cannot be negative.")
    if scenario.extra_monthly < 0:
        errors.append("Extra monthly amount cannot be negative.")
    if scenario.federal_tax_pct < 0 or scenario.state_tax_pct < 0:
        errors.append("Tax rates cannot be negative.")
    return errors


def apply_rap_month(balance: float, monthly_rate: float, scheduled: float, extra: float = 0.0) -> tuple[MonthRecord, float]:
    """One RAP month. Unpaid interest is not added. Principal match is aggregate."""
    balance = max(0.0, balance)
    if balance <= DUST:
        return MonthRecord(0, 0, 0, 0, 0, 0, 0), 0.0
    interest = balance * monthly_rate
    payoff = balance + interest
    if scheduled + extra >= payoff - 1e-9:
        paid = payoff
        return (
            MonthRecord(paid, interest, interest, balance, 0.0, 0.0, 0.0),
            0.0,
        )
    if scheduled >= interest:
        principal = scheduled - interest
        waived = 0.0
        interest_paid = interest
    else:
        principal = 0.0
        waived = interest - scheduled
        interest_paid = scheduled
    matched = 0.0
    if principal < 50:
        matched = min(50.0, scheduled) - principal
    room = balance
    principal = min(principal, room)
    room -= principal
    matched = min(max(0.0, matched), room)
    room -= matched
    extra_applied = min(max(0.0, extra), room)
    room -= extra_applied
    if room <= DUST:
        room = 0.0
    paid = scheduled + extra_applied
    return (
        MonthRecord(paid, interest, interest_paid, principal, waived, matched, room),
        room,
    )


def apply_accrual_month(balance: float, monthly_rate: float, scheduled: float, extra: float = 0.0) -> tuple[MonthRecord, float]:
    """One IBR or PAYE month. Unpaid interest is added to the balance."""
    balance = max(0.0, balance)
    if balance <= DUST:
        return MonthRecord(0, 0, 0, 0, 0, 0, 0), 0.0
    interest = balance * monthly_rate
    payoff = balance + interest
    due = min(max(0.0, scheduled) + max(0.0, extra), payoff)
    new_balance = balance + interest - due
    if new_balance <= DUST:
        new_balance = 0.0
    interest_paid = min(due, interest)
    principal = max(0.0, due - interest)
    return (
        MonthRecord(due, interest, interest_paid, principal, 0.0, 0.0, new_balance),
        new_balance,
    )


def apply_fixed_month(balance: float, monthly_rate: float, scheduled: float, extra: float = 0.0) -> tuple[MonthRecord, float]:
    """Standard or Tiered Standard month. Same cash mechanics as accrual, without a $0-payment story."""
    return apply_accrual_month(balance, monthly_rate, scheduled, extra)


def _payment_date(start: date, end_month: int) -> date:
    if end_month <= 0:
        return date(start.year, start.month, 1)
    return add_months(date(start.year, start.month, 1), end_month - 1)


def _yearly(records: list[MonthRecord], start: date) -> list[dict]:
    rows = []
    for offset in range(0, len(records), 12):
        chunk = records[offset : offset + 12]
        end_index = offset + len(chunk)
        rows.append(
            {
                "year_index": offset // 12 + 1,
                "date": _payment_date(start, end_index).isoformat(),
                "payment": chunk[0].payment,
                "balance": chunk[-1].balance,
                "paid": sum(item.payment for item in chunk),
                "waived": sum(item.waived for item in chunk),
                "matched": sum(item.matched for item in chunk),
                "interest_paid": sum(item.interest_paid for item in chunk),
            }
        )
    return rows


def _tax(amount: float, scenario: ScenarioInput, tax_free: bool) -> float:
    if tax_free or amount <= DUST:
        return 0.0
    rate = max(0.0, scenario.federal_tax_pct) + max(0.0, scenario.state_tax_pct)
    return money(amount * rate)


def _idr_payment(kind: str, agi: float, scenario: ScenarioInput, year_offset: int, std_cap: float) -> float:
    disc = discretionary_income(agi, scenario.family_size, scenario.state, year_offset, scenario.poverty_inflation)
    if kind == "ibr10":
        pct = 0.10
    elif kind == "ibr15":
        pct = 0.15
    elif kind == "paye":
        pct = 0.10
    else:
        raise ValueError(kind)
    return min(pct * disc / 12, std_cap)


def _scheduled(
    kind: str,
    month_index: int,
    scenario: ScenarioInput,
    agi0: float,
    std_cap: float,
    fixed: float | None,
    schedule: list[float] | None = None,
    icr_base: float | None = None,
) -> float:
    if kind == "fixed":
        return float(fixed or 0)
    if kind == "schedule":
        if not schedule:
            return 0.0
        return float(schedule[min(month_index, len(schedule) - 1)])
    year = month_index // 12
    agi = agi0 * ((1 + scenario.annual_raise) ** year)
    if kind == "rap":
        return float(rap_payment_dollars(agi, scenario.dependents))
    if kind == "icr":
        return icr_monthly(agi, scenario, year, float(icr_base or 0))
    return _idr_payment(kind, agi, scenario, year, std_cap)


def simulate(
    *,
    balance: float,
    monthly_rate: float,
    kind: str,
    scenario: ScenarioInput,
    agi0: float,
    std_cap: float,
    fixed_payment: float | None = None,
    max_months: int,
    pslf_counts: bool,
    idr_limit: int | None,
    switch_at: int | None = None,
    switch_kind: str | None = None,
    switch_idr_limit: int | None = None,
    paye_idr_limit: int | None = None,
    schedule: list[float] | None = None,
    icr_base: float | None = None,
) -> tuple[list[MonthRecord], str, float]:
    """Run months. Returns records, end reason, and the forgiven balance (0 when paid off)."""
    records: list[MonthRecord] = []
    remaining = max(0.0, balance)
    extra = max(0.0, scenario.extra_monthly)
    pslf_credited = max(0, scenario.pslf_months_credited)
    idr_credited = max(0, scenario.idr_months_credited)
    active_kind = kind
    limit = max_months
    if limit <= 0 or remaining <= DUST:
        return records, "paid_off", 0.0

    for month_index in range(limit):
        if switch_at is not None and month_index >= switch_at and switch_kind:
            active_kind = switch_kind
        scheduled = _scheduled(
            active_kind,
            month_index,
            scenario,
            agi0,
            std_cap,
            fixed_payment,
            schedule,
            icr_base,
        )
        if active_kind == "rap":
            record, remaining = apply_rap_month(remaining, monthly_rate, scheduled, extra)
        else:
            record, remaining = apply_accrual_month(remaining, monthly_rate, scheduled, extra)
        records.append(record)
        made = len(records)
        if pslf_counts and pslf_credited + made >= PSLF_PAYMENTS and remaining > DUST:
            return records, "pslf", remaining
        if remaining <= DUST:
            return records, "paid_off", 0.0
        qualifying = idr_credited + made
        if switch_at is not None and month_index < switch_at:
            target = paye_idr_limit
        elif switch_at is not None:
            target = switch_idr_limit
        else:
            target = idr_limit
        if target is not None and qualifying >= target and remaining > DUST:
            return records, "idr_discharge", remaining
    if remaining <= DUST:
        return records, "paid_off", 0.0
    return records, "term_complete", remaining


def _finish(
    *,
    plan_id: str,
    records: list[MonthRecord],
    reason: str,
    forgiven: float,
    scenario: ScenarioInput,
    chips: list[str],
    counts_for_pslf: bool,
    term_months: int | None,
    notes: list[str],
    first_payment: float,
) -> PlanResult:
    start = date(scenario.start_date.year, scenario.start_date.month, 1)
    end_month = len(records)
    tax_free = reason == "pslf"
    forgiven_amount = 0.0 if reason == "paid_off" else max(0.0, forgiven)
    if reason == "term_complete":
        forgiven_amount = max(0.0, forgiven)
    payments = [record.payment for record in records]
    pslf_date = None
    if reason == "pslf":
        pslf_date = _payment_date(start, end_month).isoformat()
    return PlanResult(
        plan_id=plan_id,
        label=LABELS[plan_id],
        eligible=True,
        chips=chips,
        counts_for_pslf=counts_for_pslf,
        first_year_monthly=round(float(first_payment), 2),
        total_paid=money(sum(payments)),
        total_paid_pv=money(present_value(payments)),
        interest_paid=money(sum(record.interest_paid for record in records)),
        interest_waived=money(sum(record.waived for record in records)),
        principal_matched=money(sum(record.matched for record in records)),
        end_month=end_month,
        end_date=_payment_date(start, end_month).isoformat() if end_month else start.isoformat(),
        end_reason=reason,
        forgiven_amount=money(forgiven_amount),
        estimated_tax=_tax(forgiven_amount, scenario, tax_free),
        pslf_date=pslf_date,
        term_months=term_months,
        yearly=_yearly(records, start),
        notes=notes,
    )


def _ineligible(plan_id: str, chip: str, counts: bool, notes: list[str] | None = None) -> PlanResult:
    return PlanResult(
        plan_id=plan_id,
        label=LABELS[plan_id],
        eligible=False,
        chips=[chip],
        counts_for_pslf=counts,
        notes=list(notes or []),
    )


def _empty_immediate(plan_id: str, scenario: ScenarioInput, reason: str, forgiven: float, chips: list[str], counts: bool, term: int | None, notes: list[str], first_payment: float) -> PlanResult:
    """Credited months already reach the payment count, so no new payments are modeled."""
    start = date(scenario.start_date.year, scenario.start_date.month, 1)
    tax_free = reason == "pslf"
    return PlanResult(
        plan_id=plan_id,
        label=LABELS[plan_id],
        eligible=True,
        chips=chips,
        counts_for_pslf=counts,
        first_year_monthly=round(first_payment, 2),
        total_paid=0.0,
        total_paid_pv=0.0,
        interest_paid=0.0,
        interest_waived=0.0,
        principal_matched=0.0,
        end_month=0,
        end_date=start.isoformat(),
        end_reason=reason,
        forgiven_amount=money(forgiven),
        estimated_tax=_tax(forgiven, scenario, tax_free),
        pslf_date=start.isoformat() if reason == "pslf" else None,
        term_months=term,
        yearly=[],
        notes=notes,
    )


def _run_counted_plan(
    *,
    plan_id: str,
    scenario: ScenarioInput,
    balance: float,
    monthly_rate: float,
    agi0: float,
    std_cap: float,
    kind: str,
    fixed_payment: float | None,
    term: int | None,
    pslf_counts: bool,
    idr_limit: int | None,
    chips: list[str],
    notes: list[str],
    switch_at: int | None = None,
    switch_kind: str | None = None,
    switch_idr_limit: int | None = None,
    paye_idr_limit: int | None = None,
    schedule: list[float] | None = None,
    icr_base: float | None = None,
) -> PlanResult:
    first = _scheduled(kind, 0, scenario, agi0, std_cap, fixed_payment, schedule, icr_base)
    if pslf_counts and scenario.pslf_months_credited >= PSLF_PAYMENTS and balance > DUST:
        return _empty_immediate(plan_id, scenario, "pslf", balance, chips, True, term, notes, first)
    if (
        switch_at is None
        and idr_limit is not None
        and scenario.idr_months_credited >= idr_limit
        and balance > DUST
        and not (pslf_counts and scenario.pslf_months_credited >= PSLF_PAYMENTS)
    ):
        return _empty_immediate(plan_id, scenario, "idr_discharge", balance, chips, pslf_counts, term, notes, first)

    max_months = term or RAP_PAYMENTS
    if idr_limit is not None:
        max_months = max(0, idr_limit - scenario.idr_months_credited)
    if switch_at is not None:
        if switch_idr_limit is None:
            max_months = switch_at + 600
        else:
            max_months = max(0, switch_idr_limit - scenario.idr_months_credited)
    if pslf_counts:
        pslf_left = max(0, PSLF_PAYMENTS - scenario.pslf_months_credited)
        max_months = min(max_months, pslf_left) if max_months else pslf_left
    if kind == "fixed" and term:
        max_months = term
        if pslf_counts:
            max_months = min(term, max(0, PSLF_PAYMENTS - scenario.pslf_months_credited))

    records, reason, forgiven = simulate(
        balance=balance,
        monthly_rate=monthly_rate,
        kind=kind,
        scenario=scenario,
        agi0=agi0,
        std_cap=std_cap,
        fixed_payment=fixed_payment,
        max_months=max(max_months, 0),
        pslf_counts=pslf_counts,
        idr_limit=idr_limit,
        switch_at=switch_at,
        switch_kind=switch_kind,
        switch_idr_limit=switch_idr_limit,
        paye_idr_limit=paye_idr_limit,
        schedule=schedule,
        icr_base=icr_base,
    )
    if kind in {"fixed", "schedule"} and reason == "term_complete" and forgiven > DUST:
        # Cent residue on a fixed schedule: one more month clears a payoff, not a discharge.
        tail = fixed_payment if kind == "fixed" else (schedule[-1] if schedule else 0)
        extra_records, reason2, forgiven2 = simulate(
            balance=forgiven,
            monthly_rate=monthly_rate,
            kind="fixed",
            scenario=scenario,
            agi0=agi0,
            std_cap=std_cap,
            fixed_payment=tail,
            max_months=2,
            pslf_counts=False,
            idr_limit=None,
        )
        records.extend(extra_records)
        reason, forgiven = reason2, forgiven2
    return _finish(
        plan_id=plan_id,
        records=records,
        reason=reason,
        forgiven=forgiven,
        scenario=scenario,
        chips=chips,
        counts_for_pslf=pslf_counts,
        term_months=term,
        notes=notes,
        first_payment=first,
    )


def plans_for_world(scenario: ScenarioInput, world: str) -> list[PlanResult]:
    """world is 'pre' or 'post'."""
    post = world == "post"
    balance = sum(max(0.0, loan.balance) for loan in scenario.loans)
    rate_pct = modeled_rate_pct(weighted_rate_pct(scenario.loans), scenario.autopay)
    monthly_rate = rate_pct / 100 / 12
    agi0 = combined_agi(scenario)
    std_cap = amort_payment(balance, monthly_rate, 120)
    rap_reason = rap_block_reason(scenario.loans)
    pslf = bool(scenario.pslf_job)

    rap_notes = [
        "At exact multiples of $10,000, this estimate follows the statute's bracket. A published table may place that amount in the next bracket.",
    ]
    ibr_notes = [
        "The IBR payment cap is the 10-year standard payment at the start of this estimate.",
        "Unpaid interest is added to the balance. A subsidized-loan interest benefit of up to 3 years is not modeled.",
        "Filing-status income rules are simplified in this estimate.",
    ]
    if scenario.new_borrower_after_2014 == "not_sure":
        ibr_notes.append("Both the 10% and 15% IBR estimates are shown because the July 1, 2014 date was left as not sure.")

    plans: list[PlanResult] = []

    if post:
        plans.append(_ineligible(PLAN_STANDARD, "For loans from before July 1, 2026", True))
    else:
        plans.append(
            _run_counted_plan(
                plan_id=PLAN_STANDARD,
                scenario=scenario,
                balance=balance,
                monthly_rate=monthly_rate,
                agi0=agi0,
                std_cap=std_cap,
                kind="fixed",
                fixed_payment=std_cap,
                term=120,
                pslf_counts=pslf,
                idr_limit=None,
                chips=["Eligible in this estimate"],
                notes=["Fixed 10-year estimate on the combined balance and the weighted rate."],
            )
        )

    if post:
        plans.append(_ineligible(PLAN_GRADUATED, "For loans from before July 1, 2026", False))
        plans.append(_ineligible(PLAN_EXTENDED, "For loans from before July 1, 2026", False))
    else:
        if scenario.loans and all(loan.loan_type == "Consolidation" for loan in scenario.loans):
            grad_term = consolidation_term_months(balance)
            grad_note = (
                "Graduated term follows the combined consolidation balance, from 10 years under $7,500 "
                "to 30 years at $60,000 or more. Those dollar breaks are not reprinted on the StudentAid page used for this update."
            )
        else:
            grad_term = 120
            grad_note = (
                "Payments rise every two years. The last step is three times the first, and the first payment covers interest due at the start. "
                "Modeled as 10 years unless every loan is a consolidation."
            )
        grad_schedule = graduated_schedule(balance, monthly_rate, grad_term)
        plans.append(
            _run_counted_plan(
                plan_id=PLAN_GRADUATED,
                scenario=scenario,
                balance=balance,
                monthly_rate=monthly_rate,
                agi0=agi0,
                std_cap=std_cap,
                kind="schedule",
                fixed_payment=None,
                term=grad_term,
                pslf_counts=False,
                idr_limit=None,
                chips=["Eligible in this estimate", "Does not count toward PSLF"],
                notes=[grad_note, "Graduated does not count toward PSLF in this estimate."],
                schedule=grad_schedule,
            )
        )
        if balance > 30_000:
            extended_payment = amort_payment(balance, monthly_rate, 300)
            plans.append(
                _run_counted_plan(
                    plan_id=PLAN_EXTENDED,
                    scenario=scenario,
                    balance=balance,
                    monthly_rate=monthly_rate,
                    agi0=agi0,
                    std_cap=std_cap,
                    kind="fixed",
                    fixed_payment=extended_payment,
                    term=300,
                    pslf_counts=False,
                    idr_limit=None,
                    chips=["Eligible in this estimate", "Does not count toward PSLF"],
                    notes=[
                        "Fixed 25-year payment because the combined balance is more than $30,000.",
                        "The October 7, 1998 new-borrower test is not asked. The graduated option under Extended is not a separate row.",
                        "Extended does not count toward PSLF in this estimate.",
                    ],
                )
            )
        else:
            plans.append(
                _ineligible(
                    PLAN_EXTENDED,
                    "More than $30,000 is required in this estimate",
                    False,
                    ["Extended is described for borrowers who owe more than $30,000."],
                )
            )

    tier_term = tiered_term_months(balance)
    tier_payment = amort_payment(balance, monthly_rate, tier_term)
    tier_notes = ["Fixed payment. Term follows the combined balance: under $25,000 is 10 years, then 15, 20, or 25."]
    if pslf:
        tier_notes.append("Tiered Standard does not count toward PSLF in this estimate.")
    if post:
        chips = ["Eligible in this estimate"]
        if pslf:
            chips.append("Does not count toward PSLF")
        plans.append(
            _run_counted_plan(
                plan_id=PLAN_TIERED,
                scenario=scenario,
                balance=balance,
                monthly_rate=monthly_rate,
                agi0=agi0,
                std_cap=std_cap,
                kind="fixed",
                fixed_payment=tier_payment,
                term=tier_term,
                pslf_counts=False,
                idr_limit=None,
                chips=chips,
                notes=tier_notes,
            )
        )
    else:
        plans.append(
            _ineligible(
                PLAN_TIERED,
                "For loans first disbursed on or after July 1, 2026",
                False,
                tier_notes,
            )
        )

    if rap_reason:
        plans.append(_ineligible(PLAN_RAP, rap_reason, True))
    else:
        rap_chips = ["Eligible in this estimate"]
        plans.append(
            _run_counted_plan(
                plan_id=PLAN_RAP,
                scenario=scenario,
                balance=balance,
                monthly_rate=monthly_rate,
                agi0=agi0,
                std_cap=std_cap,
                kind="rap",
                fixed_payment=None,
                term=RAP_PAYMENTS,
                pslf_counts=pslf,
                idr_limit=RAP_PAYMENTS,
                chips=rap_chips,
                notes=rap_notes,
            )
        )

    def add_ibr(plan_id: str, kind: str, limit: int, note: str, active: bool) -> None:
        if not active:
            plans.append(
                _ineligible(
                    plan_id,
                    "Not used for the July 1, 2014 answer on this estimate",
                    True,
                    [note],
                )
            )
            return
        if post:
            plans.append(_ineligible(plan_id, "For loans from before July 1, 2026", True, [note]))
            return
        if _has_parent(scenario.loans):
            plans.append(_ineligible(plan_id, "Not modeled for Parent PLUS", True, [note]))
            return
        if _has_parent_consolidation(scenario.loans):
            plans.append(
                _ineligible(
                    plan_id,
                    "Not modeled for a consolidation that repaid Parent PLUS",
                    True,
                    [note, "Public descriptions require at least one ICR payment before July 1, 2028 before IBR on that consolidation. This estimate does not apply that step."],
                )
            )
            return
        plans.append(
            _run_counted_plan(
                plan_id=plan_id,
                scenario=scenario,
                balance=balance,
                monthly_rate=monthly_rate,
                agi0=agi0,
                std_cap=std_cap,
                kind=kind,
                fixed_payment=None,
                term=limit,
                pslf_counts=pslf,
                idr_limit=limit,
                chips=["Eligible in this estimate"],
                notes=ibr_notes + [note],
            )
        )

    choice = scenario.new_borrower_after_2014
    add_ibr(
        PLAN_IBR15,
        "ibr15",
        300,
        "15% of discretionary income. Discharge estimate at 300 qualifying payments, minus months you marked as already credited.",
        choice in {"no", "not_sure"},
    )
    add_ibr(
        PLAN_IBR10,
        "ibr10",
        240,
        "10% of discretionary income. Discharge estimate at 240 qualifying payments, minus months you marked as already credited.",
        choice in {"yes", "not_sure"},
    )

    paye_block = None
    if post:
        paye_block = "For loans from before July 1, 2026"
    elif _has_parent(scenario.loans) or _has_parent_consolidation(scenario.loans):
        paye_block = "Not modeled for Parent PLUS"
    elif _has_ffel(scenario.loans):
        paye_block = "Not modeled for FFEL"
    if paye_block:
        plans.append(_ineligible(PLAN_PAYE, paye_block, True))
    else:
        switch_at = months_until(scenario.start_date, PAYE_SUNSET)
        switch_kind, switch_limit, successor, _ignored = _sunset_successor(scenario, rap_reason)
        paye_notes = [
            f"PAYE closes by July 1, 2028. After that date this estimate continues under {successor}. The page used for this update does not name the plan that follows.",
            "The partial-financial-hardship test is not applied.",
        ]
        plans.append(
            _run_counted_plan(
                plan_id=PLAN_PAYE,
                scenario=scenario,
                balance=balance,
                monthly_rate=monthly_rate,
                agi0=agi0,
                std_cap=std_cap,
                kind="paye",
                fixed_payment=std_cap if switch_kind == "fixed" else None,
                term=switch_limit or 120,
                pslf_counts=pslf,
                idr_limit=None,
                chips=["Closing by July 1, 2028", "Eligible in this estimate"],
                notes=paye_notes,
                switch_at=switch_at,
                switch_kind=switch_kind,
                switch_idr_limit=switch_limit,
                paye_idr_limit=240,
            )
        )

    icr_block = None
    if post:
        icr_block = "For loans from before July 1, 2026"
    elif _has_parent(scenario.loans):
        icr_block = "Not modeled for Parent PLUS"
    elif _has_ffel(scenario.loans):
        icr_block = "Not modeled for FFEL"
    if icr_block:
        plans.append(_ineligible(PLAN_ICR, icr_block, True))
    else:
        switch_at = months_until(scenario.start_date, PAYE_SUNSET)
        switch_kind, switch_limit, successor, _ignored = _sunset_successor(scenario, rap_reason)
        twelve_year = amort_payment(balance, monthly_rate, 144)
        icr_notes = [
            "The lesser of 20% of discretionary income and a 12-year payment times the 2026–27 income percentage factor. Discretionary income here is AGI minus 100% of the poverty guideline.",
            f"ICR closes by July 1, 2028. After that date this estimate continues under {successor}. The page used for this update does not name the plan that follows.",
            "The 12-year amount uses the starting balance. A spouse's loans are not prorated into a joint ICR payment.",
        ]
        plans.append(
            _run_counted_plan(
                plan_id=PLAN_ICR,
                scenario=scenario,
                balance=balance,
                monthly_rate=monthly_rate,
                agi0=agi0,
                std_cap=std_cap,
                kind="icr",
                fixed_payment=std_cap if switch_kind == "fixed" else None,
                term=switch_limit or 120,
                pslf_counts=pslf,
                idr_limit=None,
                chips=["Closing by July 1, 2028", "Eligible in this estimate"],
                notes=icr_notes,
                switch_at=switch_at,
                switch_kind=switch_kind,
                switch_idr_limit=switch_limit,
                paye_idr_limit=300,
                icr_base=twelve_year,
            )
        )
    return plans


def _world_notes(scenario: ScenarioInput, world_key: str) -> list[str]:
    notes = [
        "Filing-status income rules are simplified. Treat every figure as an estimate.",
    ]
    if _has_parent(scenario.loans):
        notes.append("Parent PLUS is not given a RAP, IBR, PAYE, or ICR estimate. Standard, Graduated, and Extended can still appear for loans from before July 1, 2026.")
    elif _has_parent_consolidation(scenario.loans):
        notes.append(
            "A consolidation that repaid Parent PLUS is not given RAP or PAYE. ICR can appear. IBR is withheld because public descriptions require at least one ICR payment before July 1, 2028, and this estimate does not apply that step."
        )
    if _has_ffel(scenario.loans):
        notes.append("FFEL is not given a RAP, PAYE, or ICR estimate. RAP can apply after a Direct consolidation of a non-parent FFEL loan, which this estimate does not simulate. Parent FFEL loans are not eligible for IBR.")
    if scenario.autopay:
        notes.append(
            "Auto-pay is on in this estimate, so the rate is 1 percentage point lower. The toggle stays off unless you turn it on. Confirm any reduction with your servicer."
        )
    if scenario.extra_monthly:
        notes.append("Totals include the extra monthly amount in this estimate. The first-year plan payment shown above it does not.")
    return notes


def build_audit(scenario: ScenarioInput) -> AuditResult:
    errors = validate_scenario(scenario)
    balance = sum(max(0.0, loan.balance) for loan in scenario.loans)
    weighted = weighted_rate_pct(scenario.loans) if scenario.loans else 0.0
    modeled = modeled_rate_pct(weighted, scenario.autopay)
    status = disbursement_status(scenario.loans) if scenario.loans else "pre"
    base = dict(
        ok=not errors,
        errors=errors,
        total_balance=balance,
        weighted_rate_pct=weighted,
        modeled_rate_pct=modeled,
        agi_used=combined_agi(scenario),
        uncertain=status == "uncertain",
        on_save=bool(scenario.on_save),
        state=normalize_state(scenario.state) or "",
        start_date=scenario.start_date.isoformat(),
    )
    if errors:
        return AuditResult(worlds={}, notes=[], **base)
    if status == "uncertain":
        worlds = {
            "pre_july_2026": plans_for_world(scenario, "pre"),
            "on_or_after_july_2026": plans_for_world(scenario, "post"),
        }
        notes = _world_notes(scenario, "pre_july_2026")
        notes.insert(
            0,
            "One or more loans are marked not sure for the July 1, 2026 date. Both sets of results are shown. Check the loan list on StudentAid.gov.",
        )
    elif status == "post":
        worlds = {"primary": plans_for_world(scenario, "post")}
        notes = _world_notes(scenario, "on_or_after_july_2026")
        notes.insert(
            0,
            "A loan first disbursed on or after July 1, 2026 limits this combined estimate to RAP and Tiered Standard. Split older loans into their own scenario to see Standard, Graduated, Extended, IBR, PAYE, and ICR.",
        )
    else:
        worlds = {"primary": plans_for_world(scenario, "pre")}
        notes = _world_notes(scenario, "pre_july_2026")
    return AuditResult(worlds=worlds, notes=notes, **base)


def make_scenario(**overrides) -> ScenarioInput:
    """A complete scenario for tests and the local demo. Override any field."""
    loans = overrides.pop(
        "loans",
        (LoanInput(40_000, 6.5, "Direct Unsubsidized", "no", False),),
    )
    if isinstance(loans, list):
        loans = tuple(loans)
    base = ScenarioInput(
        loans=loans,
        agi=53_000,
        filing_status="single",
        spouse_agi=0,
        dependents=0,
        family_size=1,
        state="TX",
        pslf_job=False,
        annual_raise=0.03,
        poverty_inflation=0.025,
        autopay=False,
        federal_tax_pct=0.22,
        state_tax_pct=0.0,
        extra_monthly=0.0,
        pslf_months_credited=0,
        idr_months_credited=0,
        new_borrower_after_2014="no",
        on_save=False,
        start_date=DEFAULT_START,
    )
    if overrides:
        base = replace(base, **overrides)
    return base


def scenario_to_dict(scenario: ScenarioInput) -> dict:
    payload = asdict(scenario)
    payload["start_date"] = scenario.start_date.isoformat()
    return payload


def scenario_from_dict(payload: dict) -> ScenarioInput:
    data = dict(payload)
    loans = tuple(LoanInput(**loan) for loan in data.pop("loans"))
    data["start_date"] = date.fromisoformat(data["start_date"])
    return ScenarioInput(loans=loans, **data)


def sort_plans(plans: list[PlanResult], key: str) -> list[PlanResult]:
    eligible = [plan for plan in plans if plan.eligible and plan.first_year_monthly is not None]
    rest = [plan for plan in plans if plan not in eligible]

    def monthly(plan: PlanResult):
        return (plan.first_year_monthly if plan.first_year_monthly is not None else 1e18, plan.label)

    def total(plan: PlanResult):
        return (plan.total_paid if plan.total_paid is not None else 1e18, plan.label)

    def soonest(plan: PlanResult):
        return (plan.end_month if plan.end_month is not None else 10**9, plan.label)

    sorters = {"monthly": monthly, "total": total, "soonest": soonest}
    if key not in sorters:
        raise ValueError(key)
    return sorted(eligible, key=sorters[key]) + rest


def lowest_estimated_total(plans: list[PlanResult]) -> PlanResult | None:
    eligible = [plan for plan in plans if plan.eligible and plan.total_paid is not None]
    if not eligible:
        return None
    return min(eligible, key=lambda plan: (plan.total_paid, plan.label))


def soonest_payoff(plans: list[PlanResult]) -> PlanResult | None:
    paid = [plan for plan in plans if plan.eligible and plan.end_reason == "paid_off" and plan.end_date]
    if not paid:
        return None
    return min(paid, key=lambda plan: (plan.end_month or 10**9, plan.label))
