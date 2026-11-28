"""User-facing copy. Legal blocks are exact. Marketing lines are checked against the avoid list."""

from __future__ import annotations

from pathlib import Path

RULES_DATE = "November 26, 2026"
RULES_CHECKED_LINE = "Rules last checked: Nov 2026"

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
QUIET_LINE = "Educational estimates only, not financial or legal advice."
BRAND_KICKER = "STUDENT LOAN PLAN PICKER"
PUBLIC_URL = "https://loanplanaudit.streamlit.app"
TAGLINE = "The plans that fit your disbursement date, with the math beside them."
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
    f"{RULES_CHECKED_LINE}. Confirm with your servicer and StudentAid.gov before acting."
)

SAVE_ENDED = "SAVE ended in March 2026. It is not a plan in this estimate."

AI_INSTRUCTIONS = """
You explain publicly described repayment rules and the words used in this calculator.
You do not tell the person which plan to choose, whether a plan fits them, or what to do next.
If asked for a personal recommendation, refuse and describe the formulas only.
Do not give tax, legal, or investment instructions.
Use only the plan names and monthly figures provided. Do not invent balances, income, or personal facts.
End every answer with: General info only. I can't tell you which plan to choose.
""".strip()

SERVICER_QUESTIONS = (
    "Which of my loans were first disbursed before July 1, 2026, and which were disbursed on or after that date?",
    "How many qualifying payments are already credited toward PSLF, and how many toward an IDR payment count?",
    "Were any months spent in a SAVE forbearance, and does your system count them?",
    "What monthly payment does your system show for RAP, IBR, ICR, PAYE, and Standard on these loans?",
    "Does your system treat Tiered Standard, Graduated, or Extended as counting toward PSLF?",
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
    ("2026 ICR income percentage factors", "https://www.govinfo.gov/content/pkg/FR-2026-06-09/html/2026-11540.htm"),
    ("2026 HHS poverty guidelines", "https://www.federalregister.gov/documents/2026/01/15/2026-00755/annual-update-of-the-hhs-poverty-guidelines"),
    ("Loan Simulator", "https://studentaid.gov/loan-simulator"),
)

METHOD_PARAGRAPHS = (
    "This page describes the formulas in the calculator. It is not a plan for any person.",
    "The interest rate is the balance-weighted average of the rates you enter. Auto-pay is off unless you turn it on. When it is on, the estimate subtracts one percentage point from that rate. Confirm any reduction with your servicer before relying on it.",
    "A fixed payment is balance × monthly rate ÷ (1 − (1 + monthly rate) ^ −months). A zero rate uses balance ÷ months.",
    "Standard (10-year) uses 120 months. It is included for loans modeled as disbursed before July 1, 2026.",
    "Graduated, for loans from before July 1, 2026, raises the payment every 24 months. The last step is three times the first, and the first payment is at least the interest due at the start. Non-consolidation loans use 120 months. When every loan is a consolidation, the term follows the balance from 10 years under $7,500 to 30 years at $60,000 or more. Graduated does not count toward PSLF in this estimate.",
    "Extended, for loans from before July 1, 2026, is a fixed 300-month payment when the combined balance is more than $30,000. The October 7, 1998 new-borrower test is not asked, and the graduated option under Extended is not a separate row. It does not count toward PSLF in this estimate.",
    "Tiered Standard uses 120 months under $25,000, 180 months from $25,000 to $49,999, 240 months from $50,000 to $99,999, and 300 months at $100,000 or more. The StudentAid page says 25 years for a balance over $100,000 and does not state the term at exactly $100,000. In this estimate it does not count toward PSLF.",
    "RAP uses a percentage of AGI (borrower plus spouse when married filing jointly; borrower only for other statuses). AGI at or under $10,000 uses a $120 annual amount. Above that, the percentage is 1 for amounts through $20,000 and rises by one point per $10,000, up to 10 percent above $100,000. The monthly amount is that annual figure ÷ 12, minus $50 per dependent, with a $10 floor. Payments in the model are rounded to the nearest dollar.",
    "Each RAP month, unpaid interest above the payment is not added to the balance. If the payment reduces principal by less than $50, the model reduces principal by the lesser of $50 and the payment, minus principal already paid that month. The match is applied to the combined balance once a month, not loan by loan.",
    "The model stops RAP at a zero balance or at 360 payments, minus months you marked as already credited. A remaining balance is labeled a discharge. The tax line multiplies that balance by the federal and state rates you entered. PSLF, when the toggle is on and the plan counts, stops at 120 qualifying payments and the tax line is $0.",
    "IBR discretionary income is AGI minus 150 percent of the 2026 HHS poverty guideline for your family size and state (Alaska and Hawaii use their own tables). The guideline grows by the inflation rate you enter. The share is 10 percent when you mark a first loan after July 1, 2014, and 15 percent otherwise. Not sure shows both. The payment is capped at the 10-year standard payment on the starting balance. Unpaid interest is added to the balance. A subsidized-loan interest benefit of up to 3 years is not modeled. The discharge count is 240 or 300 payments, minus months you marked as credited. A $0 payment still counts as a month in this model.",
    "PAYE is shown for Direct loans disbursed before July 1, 2026, other than Parent PLUS, a consolidation that repaid Parent PLUS, and FFEL. The payment uses 10 percent of discretionary income, capped at the same 10-year standard amount, through July 1, 2028. After that date the model continues under RAP, or under IBR when RAP is not modeled. The page used for this update says PAYE ends by that date and does not name the next plan.",
    "ICR is shown for those same older Direct loans, and also for a consolidation that repaid Parent PLUS. The payment is the lesser of 20 percent of discretionary income and a 12-year fixed payment times the 2026–27 income percentage factor. Discretionary income for ICR is AGI minus 100 percent of the poverty guideline. ICR also ends by July 1, 2028 in this model, then continues under the same successor used for PAYE, or under the 10-year Standard payment when neither RAP nor IBR is modeled.",
    "Income grows once a year by the raise percent, and the RAP, IBR, PAYE, and ICR payments are recalculated then. The ICR factor table itself stays the 2026–27 table. Standard, Graduated, Extended, and Tiered Standard payments stay fixed. Present value discounts the payments you would make at 3 percent a year.",
    "Parent PLUS is not given RAP, IBR, PAYE, or ICR. A consolidation that repaid Parent PLUS is not given RAP or PAYE. FFEL is not given RAP, PAYE, or ICR. Any loan marked on or after July 1, 2026 limits the combined estimate to RAP and Tiered Standard. Not sure shows both sets and points you to the loan list on StudentAid.gov.",
)

METHOD_UNCERTAIN = (
    "At an exact multiple of $10,000, this model follows the statute. A published table may place that amount in the next bracket.",
    "The principal match is an aggregate monthly figure. A servicer may split it across loans differently.",
    "The auto-pay toggle subtracts one point for the whole estimate and defaults off. The StudentAid page describes a 1 point reduction through June 30, 2028 for borrowers enrolled by December 31, 2026.",
    "The IBR cap uses the 10-year standard payment at the start of the estimate.",
    "SAVE ended in March 2026 and is not a plan in this estimate. StudentAid.gov still describes notices for borrowers who were on it.",
    "The income percentage factors are the July 1, 2026 through June 30, 2027 table. Later years reuse it. Income below the first row uses that row's factor, and income above the last row uses 200 percent.",
    "A consolidation that repaid Parent PLUS is not given IBR here. Public descriptions require at least one ICR payment before July 1, 2028 before that consolidation can use IBR.",
    "Married filing jointly and separately are simplified. The result is an estimate.",
)

INPUT_LABELS = (
    "Balance",
    "Interest rate (%)",
    "Loan type",
    "First disbursement date",
    "This consolidation repaid a Parent PLUS loan",
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
