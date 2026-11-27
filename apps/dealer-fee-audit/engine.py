"""Quote analysis for Dealer Fee Check. Pure functions, no network.

Neutral language only: an item is "optional", "above the limit we found",
"verify", or "ask what this is". Nothing here says a dealer broke the law.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from fees import (
    CA_NO_BENEFIT_PATTERNS,
    CAT_ADDON,
    CAT_DEST,
    CAT_DISCOUNT,
    CAT_DOC,
    CAT_FI,
    CAT_GOV,
    CAT_MARKUP,
    CAT_OTHER,
    CATEGORY_LABELS,
    classify,
    doc_fee_rule,
    normalize_state,
)

V_EXPECTED = "expected"
V_VERIFY = "verify"
V_OPTIONAL = "optional"
V_OVER = "over_limit"
V_ASK = "ask"
V_HIGH = "above_presumed"

VERDICT_LABELS = {
    V_EXPECTED: "Normal charge",
    V_VERIFY: "Check the amount",
    V_OPTIONAL: "Optional — you can ask to remove it",
    V_OVER: "Above the state limit we found",
    V_ASK: "Ask what this is",
    V_HIGH: "Above the amount the state presumes reasonable",
}

FLAGGED = (V_OVER, V_HIGH, V_OPTIONAL, V_ASK)
MAX_ITEMS = 25


@dataclass
class LineItem:
    label: str
    amount: float
    category: str | None = None  # None = auto-detect from the label


@dataclass
class QuoteInput:
    state: str
    condition: str  # "new" or "used"
    vehicle_price: float
    items: list[LineItem] = field(default_factory=list)
    trade_in: float = 0.0
    down_payment: float = 0.0
    apr: float | None = None
    term_months: int | None = None
    is_ev: bool = False
    vehicle: str = ""


@dataclass
class LineResult:
    label: str
    amount: float
    category: str
    category_label: str
    verdict: str
    verdict_label: str
    headline: str
    detail: str
    removable: float = 0.0  # dollars the buyer can ask to drop, by our neutral rules


@dataclass
class QuoteAudit:
    ok: bool
    errors: list[str]
    state: str | None
    lines: list[LineResult]
    out_the_door: float = 0.0
    by_category: dict = field(default_factory=dict)
    flagged_count: int = 0
    removable_total: float = 0.0
    removable_pct_of_price: float = 0.0
    doc_fee_total: float = 0.0
    doc_fee_limit: float | None = None
    doc_fee_rule_kind: str = "none"
    implied_tax_rate: float | None = None
    amount_financed: float = 0.0
    monthly_payment: float | None = None
    monthly_without_removable: float | None = None
    finance_cost_of_removable: float | None = None


def _round(value: float) -> float:
    return round(float(value) + 0.0, 2)


def amortized_payment(principal: float, apr_pct: float, months: int) -> float:
    """Standard loan payment. APR in percent."""
    if months <= 0:
        raise ValueError("term must be positive")
    if principal <= 0:
        return 0.0
    rate = (apr_pct or 0.0) / 100.0 / 12.0
    if rate == 0:
        return _round(principal / months)
    return _round(principal * rate / (1 - (1 + rate) ** -months))


def validate(quote: QuoteInput) -> list[str]:
    errors = []
    if not normalize_state(quote.state):
        errors.append("Pick the state where you will register the car.")
    if quote.condition not in ("new", "used"):
        errors.append("Pick new or used.")
    if quote.vehicle_price is None or quote.vehicle_price <= 0:
        errors.append("Enter the vehicle price before fees (the selling price on the quote).")
    elif quote.vehicle_price > 2_000_000:
        errors.append("That vehicle price looks too high. Check for an extra zero.")
    if len(quote.items) > MAX_ITEMS:
        errors.append(f"Enter up to {MAX_ITEMS} line items.")
    for item in quote.items:
        if abs(item.amount or 0) > 1_000_000:
            errors.append(f"The amount for '{item.label}' looks too high.")
    if quote.trade_in < 0 or quote.down_payment < 0:
        errors.append("Trade-in and down payment cannot be negative.")
    if quote.apr is not None and not (0 <= quote.apr <= 40):
        errors.append("APR should be between 0% and 40%.")
    if quote.term_months is not None and not (6 <= quote.term_months <= 96):
        errors.append("Loan term should be between 6 and 96 months.")
    return errors


def _ca_no_benefit(label: str, is_ev: bool) -> str | None:
    text = label.lower()
    for pattern, name in CA_NO_BENEFIT_PATTERNS:
        if re.search(pattern, text):
            if "oil change" in name.lower() and not is_ev:
                continue
            return name
    return None


def judge_line(item: LineItem, quote: QuoteInput, doc_fee_seen: float) -> LineResult:
    """Verdict for one line. doc_fee_seen = doc fees on earlier lines (limits apply to the total)."""
    category = item.category or classify(item.label)
    amount = _round(item.amount or 0)
    label = (item.label or "").strip() or "Unlabeled charge"
    state = normalize_state(quote.state) or ""
    verdict, headline, detail, removable = V_ASK, "", "", 0.0

    if category == CAT_GOV:
        verdict = V_VERIFY
        headline = "Tax or government fee"
        detail = (
            "Set by your state or county, not the dealer. Check the amount against your state DMV or revenue "
            "department's fee calculator. A dealer can't mark these up."
        )
    elif category == CAT_DOC:
        rule = doc_fee_rule(state)
        limit = rule.limit_for(quote.vehicle_price)
        total = doc_fee_seen + amount
        if rule.kind == "cap" and limit is not None and total > limit + 0.005:
            excess = _round(min(amount, total - limit))
            verdict, removable = V_OVER, excess
            headline = f"About ${excess:,.2f} above the {state} limit we found (${limit:,.2f})"
            detail = (
                f"{rule.note} Source: {rule.citation}. Limits change, often each January, and can depend on how "
                "the dealer files paperwork. Ask the dealer to show the fee is within the current limit, or to lower it. "
                "If you think a dealer overcharged, your state attorney general or dealer licensing board takes complaints."
            ).strip()
        elif rule.kind == "presumed" and limit is not None and total > limit + 0.005:
            verdict = V_HIGH
            headline = f"Above the ${limit:,.0f} amount {state} presumes reasonable"
            detail = f"{rule.note} Source: {rule.citation}. Ask whether the dealer filed for the higher amount."
        else:
            verdict = V_EXPECTED if rule.kind in ("cap", "presumed") else V_VERIFY
            if rule.kind == "none":
                headline = "Dealer-set fee (no state dollar limit found)"
                detail = rule.note
            else:
                headline = f"Within the {state} limit we found"
                detail = f"{rule.note} Source: {rule.citation}.".strip()
    elif category == CAT_DEST:
        if quote.condition == "used":
            verdict, removable = V_ASK, amount
            headline = "Destination charge on a used car"
            detail = "Destination is a new-car charge from the manufacturer. Ask why it appears on a used car."
        else:
            verdict = V_VERIFY
            headline = "Manufacturer destination charge"
            detail = "Should match the destination line on the window sticker (Monroney label). It is usually not negotiable."
    elif category == CAT_MARKUP:
        verdict, removable = V_OPTIONAL, max(amount, 0.0)
        headline = "Dealer markup over the sticker price"
        detail = (
            "This is extra profit set by the dealer, not a fee. It is negotiable. Many buyers ask for it to be removed "
            "or shop another dealer."
        )
    elif category == CAT_ADDON:
        verdict, removable = V_OPTIONAL, max(amount, 0.0)
        headline = "Dealer add-on"
        detail = "Products the dealer adds. Ask for the price without it in writing."
    elif category == CAT_FI:
        verdict, removable = V_OPTIONAL, max(amount, 0.0)
        headline = "Optional finance-office product"
        detail = (
            "Service contracts, GAP and similar plans are optional and not required to get a loan. "
            "You can decline, or compare prices from your bank, credit union or insurer before buying."
        )
    elif category == CAT_DISCOUNT:
        verdict = V_EXPECTED
        headline = "Discount or rebate"
        detail = "Make sure it also appears on the final contract, and ask whether it depends on financing with the dealer."
    else:
        verdict = V_ASK
        headline = "Unclear charge"
        detail = "Ask the dealer what this is, who requires it, and whether you can buy the car without it."

    if state == "CA" and category in (CAT_ADDON, CAT_FI):
        detail += (
            " In California, a dealer must disclose in writing that add-ons are optional (Cal. Civ. Code § 1784.41(b))."
        )
        banned = _ca_no_benefit(label, quote.is_ev)
        if banned:
            headline = "Add-on that California lists as no-benefit"
            detail += (
                f" California does not let a dealer charge for: {banned} (Cal. Civ. Code § 1784.42(a)). "
                "Ask what exactly is included."
            )

    return LineResult(
        label=label,
        amount=amount,
        category=category,
        category_label=CATEGORY_LABELS.get(category, CATEGORY_LABELS[CAT_OTHER]),
        verdict=verdict,
        verdict_label=VERDICT_LABELS[verdict],
        headline=headline,
        detail=detail,
        removable=_round(removable),
    )


def build_audit(quote: QuoteInput) -> QuoteAudit:
    errors = validate(quote)
    state = normalize_state(quote.state)
    if errors:
        return QuoteAudit(ok=False, errors=errors, state=state, lines=[])

    lines: list[LineResult] = []
    doc_seen = 0.0
    for item in quote.items:
        if not (item.label or "").strip() and not item.amount:
            continue
        result = judge_line(item, quote, doc_seen)
        if result.category == CAT_DOC:
            doc_seen += result.amount
        lines.append(result)

    by_category: dict[str, float] = {}
    for line in lines:
        by_category[line.category] = _round(by_category.get(line.category, 0.0) + line.amount)

    fees_total = sum(line.amount for line in lines)
    otd = _round(quote.vehicle_price + fees_total - (quote.trade_in or 0.0))
    removable = _round(sum(line.removable for line in lines))
    flagged = sum(1 for line in lines if line.verdict in FLAGGED)

    rule = doc_fee_rule(state)
    gov_tax = sum(line.amount for line in lines if line.category == CAT_GOV and re.search(r"tax", line.label.lower()))
    implied = round(gov_tax / quote.vehicle_price * 100, 2) if gov_tax > 0 else None

    financed = _round(max(otd - (quote.down_payment or 0.0), 0.0))
    monthly = without = cost = None
    if quote.apr is not None and quote.term_months:
        monthly = amortized_payment(financed, quote.apr, quote.term_months)
        without = amortized_payment(max(financed - removable, 0.0), quote.apr, quote.term_months)
        cost = _round((monthly - without) * quote.term_months)

    return QuoteAudit(
        ok=True,
        errors=[],
        state=state,
        lines=lines,
        out_the_door=otd,
        by_category=by_category,
        flagged_count=flagged,
        removable_total=removable,
        removable_pct_of_price=round(removable / quote.vehicle_price * 100, 1) if quote.vehicle_price else 0.0,
        doc_fee_total=_round(doc_seen),
        doc_fee_limit=rule.limit_for(quote.vehicle_price),
        doc_fee_rule_kind=rule.kind,
        implied_tax_rate=implied,
        amount_financed=financed,
        monthly_payment=monthly,
        monthly_without_removable=without,
        finance_cost_of_removable=cost,
    )


def flagged_lines(audit: QuoteAudit) -> list[LineResult]:
    order = {V_OVER: 0, V_HIGH: 1, V_OPTIONAL: 2, V_ASK: 3, V_VERIFY: 4, V_EXPECTED: 5}
    return sorted(
        [line for line in audit.lines if line.verdict in FLAGGED],
        key=lambda line: (order[line.verdict], -line.amount),
    )


def counter_offer_text(quote: QuoteInput, audit: QuoteAudit) -> str:
    """A plain message the buyer can edit and send themselves. Not legal advice."""
    vehicle = quote.vehicle.strip() or "the vehicle"
    flagged = flagged_lines(audit)
    lines = [
        "Hi,",
        "",
        f"Thanks for the quote on {vehicle}. Before I move forward, could you send an updated itemized "
        "out-the-door price in writing with these changes?",
        "",
    ]
    optional = [line for line in flagged if line.verdict == V_OPTIONAL]
    over = [line for line in flagged if line.verdict == V_OVER]
    ask = [line for line in flagged if line.verdict == V_ASK]
    high = [line for line in flagged if line.verdict == V_HIGH]
    if optional:
        lines.append("Please remove these optional items. I'd like to buy the car without them:")
        lines += [f"  - {line.label} (${line.amount:,.2f})" for line in optional]
        lines.append("")
    if over:
        for line in over:
            lines.append(
                f"The {line.label.lower()} of ${line.amount:,.2f} looks higher than the limit I found for my state "
                f"(${audit.doc_fee_limit:,.2f}). Could you confirm the current limit or adjust it?"
            )
        lines.append("")
    if high:
        for line in high:
            lines.append(
                f"The {line.label.lower()} of ${line.amount:,.2f} is above the ${audit.doc_fee_limit:,.0f} amount my state "
                "presumes reasonable. Could you confirm the dealership filed for a higher amount, or lower it?"
            )
        lines.append("")
    if ask:
        lines.append("Could you explain these charges and whether they are required?")
        lines += [f"  - {line.label} (${line.amount:,.2f})" for line in ask]
        lines.append("")
    if not (optional or over or ask or high):
        lines.append("Could you confirm this is the full out-the-door price, with no other charges at signing?")
        lines.append("")
    lines += [
        "Please also confirm that any rebates shown don't depend on financing through the dealership, "
        "unless that's noted.",
        "",
        "Thanks,",
        "[Your name]",
    ]
    return "\n".join(lines)


def make_sample_quote(state: str = "TX") -> QuoteInput:
    """Hypothetical quote used in demos, screenshots and tests."""
    return QuoteInput(
        state=state,
        condition="new",
        vehicle_price=31_500.0,
        vehicle="2026 compact SUV (sample)",
        items=[
            LineItem("Destination charge", 1_395.0),
            LineItem("Market adjustment", 1_500.0),
            LineItem("Doc fee", 399.0),
            LineItem("Nitrogen-filled tires", 199.0),
            LineItem("VIN etching", 299.0),
            LineItem("Paint & fabric protection", 895.0),
            LineItem("Sales tax", 2_227.0),
            LineItem("Title and registration", 120.0),
            LineItem("Electronic filing fee", 34.0),
            LineItem("Dealer processing", 189.0),
        ],
        apr=7.9,
        term_months=72,
        down_payment=3_000.0,
    )


def quote_to_dict(quote: QuoteInput) -> dict:
    return asdict(quote)


def quote_from_dict(data: dict) -> QuoteInput:
    items = [LineItem(**item) for item in (data.get("items") or [])]
    fields = {key: value for key, value in data.items() if key != "items"}
    return QuoteInput(items=items, **fields)
