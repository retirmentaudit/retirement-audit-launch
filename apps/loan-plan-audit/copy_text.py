"""User-facing copy. Legal blocks are exact. Marketing lines are checked against the avoid list."""

from __future__ import annotations

from pathlib import Path

RULES_DATE = "November 26, 2026"

LANDING_STRIP = (
    "Educational estimates. Not financial, legal or tax advice. Not affiliated with the U.S. Department of Education. "
    "You never have to pay for help with federal student loans — free tools at StudentAid.gov."
)

SHORT_DISCLAIMER = (
    "Educational estimates only — not financial, legal, or tax advice. Not affiliated with the U.S. Department of Education "
    "or any loan servicer. Rules change; confirm with your servicer and StudentAid.gov before acting. "
    "You never have to pay for help with federal student loans."
)

RESULTS_DISCLAIMER = (
    "These figures are estimates based only on what you entered and our reading of federal rules as of "
    f"{RULES_DATE}. Actual payments, eligibility, interest, forgiveness, and taxes are determined by the "
    "U.S. Department of Education and your loan servicer and may differ. We don't know your full situation, "
    "so we don't recommend any plan. Before choosing or changing a plan, use the free Loan Simulator at "
    "StudentAid.gov and contact your servicer. For tax effects of forgiveness, consult a tax professional."
)

CHECKOUT_DISCLAIMER = (
    "You're buying access to a software report. It does not enroll you in any plan, change your loans, "
    "or contact your servicer, and it does not guarantee any outcome. One-time charge of $9. 7-day refund on request."
)

AI_LINE = "General info only. I can't tell you which plan to choose."

LOWEST_TOTAL_CAPTION = "Lowest estimated total cost in this scenario"

HEADLINE = "Student Loan Plan Picker"
BRAND_KICKER = "STUDENT LOAN PLAN PICKER"
PUBLIC_URL = "https://loanplanaudit.streamlit.app"
TAGLINE = "RAP, IBR or Standard? See every plan's real math in 60 seconds."
ALT_TAGLINE = "Your loans. Every plan. Zero guesswork."

BULLETS = (
    "See the first-year estimated payment for each plan that fits the loans you enter.",
    "Compare the math side by side in about a minute.",
    "The full report is a one-time $9 software purchase where it is offered. No subscription.",
)

CTA = "Run my numbers (free)"
UNLOCK_BUTTON = "Unlock the full report — $9"
CHECKOUT_BUTTON = "Continue to $9 checkout"
TERMS_CHECKBOX = "I agree to the Terms of Service."

RULES_BANNER = (
    f"Rules last checked: {RULES_DATE}. Rules are reviewed monthly. "
    "Court cases can change timelines. Confirm with your servicer and StudentAid.gov before acting."
)

AI_INSTRUCTIONS = """
You explain publicly described repayment rules and the words used in this calculator.
You do not tell the person which plan to choose, whether a plan fits them, or what to do next.
If asked for a personal recommendation, refuse and describe the formulas only.
Do not give tax, legal, or investment instructions.
Use only the plan names and monthly figures provided. Do not invent balances, income, or personal facts.
End every answer with: General info only. I can't tell you which plan to choose.
""".strip()

SAVE_CHECKLIST = (
    "Read the notice from your servicer and note the date printed on it.",
    "Notices described on StudentAid.gov started July 1, 2026, with everyone notified by the end of 2026, then a shorter final notice.",
    "Compare the estimated payments in this calculator with the figures your servicer shows you.",
    "Use the free Loan Simulator at StudentAid.gov.",
    "If you do not choose, public descriptions say placement can be Standard, or Tiered Standard when a loan was first disbursed on or after July 1, 2026.",
    "Months in a SAVE forbearance are not modeled here as counting toward PSLF or an IDR payment count. PSLF buyback is a separate topic to confirm on StudentAid.gov.",
)

SERVICER_QUESTIONS = (
    "Which of my loans were first disbursed before July 1, 2026, and which were disbursed on or after that date?",
    "How many qualifying payments are already credited toward PSLF, and how many toward an IDR payment count?",
    "Am I in a SAVE forbearance, and what date is on my notice?",
    "What monthly payment does your system show for RAP, IBR, and Standard on these loans?",
    "Does your system treat Tiered Standard as counting toward PSLF?",
    "If a balance would remain at the end of a plan, how do you describe the tax treatment, and where should I confirm it?",
)

LINKS = {
    "Loan Simulator": "https://studentaid.gov/loan-simulator",
    "StudentAid.gov": "https://studentaid.gov",
    "Servicer list": "https://studentaid.gov/manage-loans/repayment/servicers",
    "SAVE article": "https://studentaid.gov/articles/save/",
    "IDR FAQ": "https://studentaid.gov/articles/faqs-idr-plan/",
    "PSLF Help Tool": "https://studentaid.gov/pslf/",
    "MOHELA": "https://www.mohela.com/",
    "Aidvantage": "https://aidvantage.studentaid.gov/",
    "Nelnet": "https://nelnet.studentaid.gov/",
    "Edfinancial": "https://edfinancial.studentaid.gov/",
}

SOURCES = (
    ("Statute section on repayment (P.L. 119-21 §82001)", "https://onebigbeautifulbill.us/obbba-text/title-viii/sec-82001-loan-repayment/"),
    ("Congressional Research Service IF13075", "https://www.congress.gov/crs-product/IF13075"),
    ("RAP overview", "https://cri.studentaid.gov/content/rap"),
    ("RAP FAQ", "https://cri.studentaid.gov/content/faq/faqrap"),
    ("Tiered Standard", "https://cri.studentaid.gov/content/tieredstandard"),
    ("IDR FAQ", "https://studentaid.gov/articles/faqs-idr-plan/"),
    ("SAVE article", "https://studentaid.gov/articles/save/"),
    ("2026 HHS poverty guidelines", "https://www.federalregister.gov/documents/2026/01/15/2026-00755/annual-update-of-the-hhs-poverty-guidelines"),
    ("Loan Simulator", "https://studentaid.gov/loan-simulator"),
)

METHOD_PARAGRAPHS = (
    "This page describes the formulas in the calculator. It is not a plan for any person.",
    "The interest rate is the balance-weighted average of the rates you enter. Auto-pay is off unless you turn it on. When it is on, the estimate subtracts one percentage point from that rate. Confirm any reduction with your servicer before relying on it.",
    "A fixed payment is balance × monthly rate ÷ (1 − (1 + monthly rate) ^ −months). A zero rate uses balance ÷ months.",
    "Standard (10-year) uses 120 months. It is included for loans modeled as disbursed before July 1, 2026.",
    "Tiered Standard uses 120 months under $25,000, 180 months from $25,000 to $49,999, 240 months from $50,000 to $99,999, and 300 months at $100,000 or more. In this estimate it does not count toward PSLF.",
    "RAP uses a percentage of AGI (borrower plus spouse when married filing jointly; borrower only for other statuses). AGI at or under $10,000 uses a $120 annual amount. Above that, the percentage is 1 for amounts through $20,000 and rises by one point per $10,000, up to 10 percent above $100,000. The monthly amount is that annual figure ÷ 12, minus $50 per dependent, with a $10 floor. Payments in the model are rounded to the nearest dollar.",
    "Each RAP month, unpaid interest above the payment is not added to the balance. If the payment reduces principal by less than $50, the model reduces principal by the lesser of $50 and the payment, minus principal already paid that month. The match is applied to the combined balance once a month, not loan by loan.",
    "The model stops RAP at a zero balance or at 360 payments, minus months you marked as already credited. A remaining balance is labeled a discharge. The tax line multiplies that balance by the federal and state rates you entered. PSLF, when the toggle is on and the plan counts, stops at 120 qualifying payments and the tax line is $0.",
    "IBR discretionary income is AGI minus 150 percent of the 2026 HHS poverty guideline for your family size and state (Alaska and Hawaii use their own tables). The guideline grows by the inflation rate you enter. The share is 10 percent when you mark a first loan after July 1, 2014, and 15 percent otherwise. Not sure shows both. The payment is capped at the 10-year standard payment on the starting balance. Unpaid interest is added to the balance. A subsidized-loan interest benefit of up to 3 years is not modeled. The discharge count is 240 or 300 payments, minus months you marked as credited. A $0 payment still counts as a month in this model.",
    "PAYE is shown only for the pre-July 2026 set. The payment uses 10 percent of discretionary income, capped at the same 10-year standard amount, through July 1, 2028. After that date the model continues under RAP, or under IBR when RAP is not modeled for the loan type.",
    "Income grows once a year by the raise percent, and the RAP or IBR payment is recalculated then. Standard and Tiered Standard payments stay fixed. Present value discounts the payments you would make at 3 percent a year.",
    "Parent PLUS, a consolidation that repaid Parent PLUS, and FFEL are not given a RAP estimate. Any loan marked on or after July 1, 2026 limits the estimate to RAP and Tiered Standard. Not sure shows both sets and points you to the loan list on StudentAid.gov.",
)

METHOD_UNCERTAIN = (
    "At an exact multiple of $10,000, this model follows the statute. A published table may place that amount in the next bracket.",
    "The principal match is an aggregate monthly figure. A servicer may split it across loans differently.",
    "The auto-pay reduction is a toggle and defaults off. Confirm the size of any reduction on a current servicer page.",
    "The IBR cap uses the 10-year standard payment at the start of the estimate.",
    "Pending litigation could change SAVE timelines. The banner date is the last time these rules were checked.",
    "The Parent PLUS route described in public materials is information only. This version does not estimate it.",
    "Married filing jointly and separately are simplified. The result is an estimate.",
)

INPUT_LABELS = (
    "Balance",
    "Interest rate (%)",
    "Loan type",
    "First disbursed",
    "This consolidation repaid a Parent PLUS loan",
    "Currently on SAVE?",
    "Months already credited toward PSLF",
    "Months already credited toward an IDR count",
    "First loan after July 1, 2014?",
    "AGI",
    "Filing status",
    "Spouse AGI",
    "Dependents claimed",
    "Family size",
    "State of residence",
    "Federal tax rate on a discharged balance (%)",
    "State tax rate on a discharged balance (%)",
    "Works full time for a government or 501(c)(3) employer?",
    "Expected annual raise (%)",
    "Poverty-guideline inflation (%)",
    "Auto-pay rate reduction",
    "Email",
    "Password",
    "Scenario name",
)

_LEGAL = Path(__file__).resolve().parent / "legal"


def terms_markdown() -> str:
    return (_LEGAL / "terms.md").read_text(encoding="utf-8")


def privacy_markdown() -> str:
    return (_LEGAL / "privacy.md").read_text(encoding="utf-8")
