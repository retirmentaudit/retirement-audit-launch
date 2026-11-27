"""User-facing copy. Legal blocks are exact; tests check they appear where required."""

from __future__ import annotations

from pathlib import Path

from fees import RULES_DATE

from checkout import PRICE_DOLLARS  # single source of truth

HEADLINE = "Dealer Fee Audit"
TAGLINE = "Paste your dealer's out-the-door quote. See every fee explained in 60 seconds."
ALT_TAGLINE = "Know which charges are required, which are optional, and which look high."

BULLETS = (
    "Type the line items from any dealer quote, buyer's order, or worksheet. No upload, no login.",
    "Each line is sorted into taxes and government fees, dealer fees, add-ons, and finance-office products.",
    "Doc fees are checked against the state limits we found in 19 states.",
    f"The full line-by-line report and a ready-to-send message are a one-time ${PRICE_DOLLARS}. No subscription.",
)

LANDING_STRIP = (
    "Educational information only. Not legal, financial, or tax advice. We are not a car dealer, broker, or lender, "
    "and we are not affiliated with any dealer, manufacturer, or government agency. Results are based only on what you enter."
)

SHORT_DISCLAIMER = (
    "Educational information only — not legal, financial, or tax advice. Dealer Fee Audit is independent software and is "
    "not a dealer, broker, lender, or law firm. State rules change; confirm with your state agency before acting. "
    "We don't guarantee any price, refund, or savings."
)

RESULTS_DISCLAIMER = (
    "These results are general information based only on the line items you entered and our reading of public "
    f"state rules as of {RULES_DATE}. Labels like “optional” or “above the limit we found” are not a finding that "
    "any dealer acted unlawfully. Fee limits change, often each January, and some depend on how the dealer files "
    "paperwork. Taxes and government fees are set by your state and county; check them with your DMV or revenue "
    "department. We don't know your full situation and don't tell you whether to buy. For legal questions about a "
    "contract, talk to a licensed attorney in your state or your state attorney general's consumer office."
)

CHECKOUT_DISCLAIMER = (
    "You're buying access to a software report. We don't negotiate for you, contact any dealer, or guarantee any "
    f"price, savings, or outcome. One-time charge of ${PRICE_DOLLARS}. No subscription. 7-day refund on request."
)

SCRIPT_DISCLAIMER = (
    "Template only. You choose whether to send it and what it says. It is not legal advice, and we don't send "
    "anything on your behalf."
)

RULES_BANNER = (
    f"State fee limits last checked: {RULES_DATE}. Limits are reviewed monthly and usually change each January."
)

CTA = "Check my quote (free)"
UNLOCK_BUTTON = f"Unlock the full report — ${PRICE_DOLLARS}"
CHECKOUT_BUTTON = f"Continue to ${PRICE_DOLLARS} checkout"
TERMS_CHECKBOX = "I agree to the Terms of Service."

METHOD_PARAGRAPHS = (
    "You type each line from the dealer's quote. We match the line's name to a category with a keyword list "
    "(you can override it). Nothing is uploaded and no dealer is contacted.",
    "Taxes and government fees are marked “Check the amount”: they are set by your state and county, and we don't "
    "estimate them. The implied tax rate is the tax lines divided by the vehicle price, shown so you can compare it "
    "to your state's published rate.",
    "Documentation (doc) fees: 17 states publish a dollar limit and Texas and South Carolina publish a presumed "
    "reasonable amount. If your doc-type lines add up to more than the limit we found, we show the difference. In "
    "other states we found no dollar limit, so we only explain the fee.",
    "Dealer add-ons, market adjustments and finance-office products (service contracts, GAP and similar) are "
    "marked optional. The total of those lines is the amount you can ask to remove. If you add an APR and term, we "
    "show the standard loan payment with and without those lines.",
    "Destination charges on new cars should match the window sticker. A destination charge on a used car is "
    "marked “Ask what this is.” Anything we can't match is also marked “Ask what this is.”",
)

SOURCES = (
    ("California CARS Act (Cal. Civ. Code §§ 1784.41–1784.42)",
     "https://leginfo.legislature.ca.gov/faces/codes_displayText.xhtml?lawCode=CIV&division=3.&title=1.5B.&part=4.&chapter=3."),
    ("FTC: Buying a new car", "https://consumer.ftc.gov/articles/buying-new-car"),
    ("FTC: Buying a used car from a dealer", "https://consumer.ftc.gov/articles/buying-used-car-dealer"),
    ("Pennsylvania 2026 documentary fee notice",
     "https://www.pa.gov/content/dam/copapwp-pagov/en/dos/department-and-offices/bpoa/vehicle/Annual%20Fee.pdf"),
    ("Missouri maximum dealer administrative fee", "https://dor.mo.gov/motor-vehicle/dealers-lienholders/"),
    ("Ohio documentary service charge", "https://autodealers.ohio.gov/resources-for-dealers/resources/documentary-service-charge"),
    ("New York 15 NYCRR § 78.19", "https://www.law.cornell.edu/regulations/new-york/15-NYCRR-78.19"),
    ("Indiana 2026 doc fee memo", "https://www.in.gov/sos/dealer/files/Doc-Fees-in-2026.pdf"),
    ("Iowa Code § 322.19A", "https://www.legis.iowa.gov/docs/code/2026/322.19A.pdf"),
)

QUESTIONS_TO_ASK = (
    "Is this the full out-the-door price, including every tax and fee due at signing?",
    "Which of these items are already installed on the car, and can I buy it without them?",
    "Does any rebate or discount depend on financing with the dealership?",
    "If I finance, what is the APR and is it the rate I was approved for, or a marked-up rate?",
    "Can I see the window sticker (new) or the FTC Buyers Guide (used)?",
    "Will you put this price in writing, valid until a specific date?",
)

_LEGAL = Path(__file__).resolve().parent / "legal"


def terms_markdown() -> str:
    return (_LEGAL / "terms.md").read_text(encoding="utf-8")


def privacy_markdown() -> str:
    return (_LEGAL / "privacy.md").read_text(encoding="utf-8")


# Words the marketing copy must never use (tests enforce this).
AVOID_WORDS = ("guarantee savings", "illegal fee", "scam dealer", "we negotiate", "get your money back", "official")
