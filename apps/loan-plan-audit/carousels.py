"""Hypothetical sample posts. Every deck ends on the disclaimer. Numbers come from the engine."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageDraw

from copy_text import BRAND_KICKER, PUBLIC_URL, SHORT_DISCLAIMER
from engine import PLAN_IBR15, PLAN_RAP, PLAN_STANDARD, LoanInput, build_audit, make_scenario
from share_card import _font, _wrap

NAVY = "#0B1F3A"
MINT = "#2BD9A0"
PAPER = "#F7F5F0"


@dataclass(frozen=True)
class Slide:
    kicker: str
    title: str
    body: str


def _disclaimer() -> Slide:
    return Slide("disclaimer", "Estimate. Not advice.", SHORT_DISCLAIMER + " " + PUBLIC_URL)


def _money(amount: float) -> str:
    if abs(amount - round(amount)) < 0.005:
        return f"${amount:,.0f}"
    return f"${amount:,.2f}"


def save_deck() -> list[Slide]:
    return [
        Slide("studentaid.gov", "SAVE ended in March 2026", "A court order ended it. It is not a plan in this calculator. Source: studentaid.gov."),
        Slide("studentaid.gov", "What the page describes", "Borrowers who were on SAVE choose another plan they can use. This calculator does not offer SAVE. Source: studentaid.gov."),
        Slide("studentaid.gov", "Notices", "Servicers have been sending notices since July 1, 2026. Read the date on yours. Source: studentaid.gov."),
        Slide("studentaid.gov", "If no plan is chosen", "Public descriptions say placement can be Standard, or Tiered Standard when a loan was first disbursed on or after July 1, 2026. Source: studentaid.gov."),
        Slide("hypothetical", "See your numbers free", "The first disbursement date chooses the plans. Compare them with the loans you enter. " + PUBLIC_URL),
        _disclaimer(),
    ]


def rap_deck() -> list[Slide]:
    return [
        Slide("studentaid.gov", "RAP in 30 seconds", "The share of AGI steps up about one point per $10,000, from 1 percent through $20,000 up to 10 percent above $100,000."),
        Slide("studentaid.gov", "$50 and a $10 floor", "The model subtracts $50 a month for each dependent. The payment does not go under $10."),
        Slide("studentaid.gov", "Interest and a principal match", "Unpaid interest is not added to the balance. If principal paid that month is under $50, the formula matches up to $50."),
        Slide("hypothetical", "$53,000 example", "Hypothetical example, cited from a published illustration: $53,000 of AGI is $221 a month. One dependent is $171. Source: studentaid.gov."),
        _disclaimer(),
    ]


def salary_deck() -> list[Slide]:
    audit = build_audit(
        make_scenario(
            loans=(LoanInput(35_000, 6, "Direct Unsubsidized", "no"),),
            agi=60_000,
            annual_raise=0.03,
            filing_status="single",
            dependents=0,
            family_size=1,
            state="TX",
        )
    )
    plans = {plan.plan_id: plan for plan in audit.worlds["primary"]}
    monthly = (
        f"Hypothetical example. Not a real person. $60,000 income, $35,000 balance, 6 percent rate. "
        f"Standard {_money(plans[PLAN_STANDARD].first_year_monthly)} a month. "
        f"IBR {_money(plans[PLAN_IBR15].first_year_monthly)} a month. "
        f"RAP {_money(plans[PLAN_RAP].first_year_monthly)} a month."
    )
    totals = (
        f"Estimated total paid in this hypothetical: "
        f"Standard {_money(plans[PLAN_STANDARD].total_paid)}, "
        f"IBR {_money(plans[PLAN_IBR15].total_paid)}, "
        f"RAP {_money(plans[PLAN_RAP].total_paid)}."
    )
    ends = (
        f"Modeled end dates: Standard {plans[PLAN_STANDARD].end_date}, "
        f"IBR {plans[PLAN_IBR15].end_date}, RAP {plans[PLAN_RAP].end_date}."
    )
    return [
        Slide("hypothetical", "Same $60,000 income, 3 plans", "Hypothetical example. Not a real person. Labeled so it is not mistaken for a result."),
        Slide("studentaid.gov", "Monthly estimates", monthly + " Rules described at studentaid.gov."),
        Slide("hypothetical", "Estimated total paid", totals),
        Slide("hypothetical", "Run yours", ends + " See your own numbers free at " + PUBLIC_URL + "."),
        _disclaimer(),
    ]


def pslf_deck() -> list[Slide]:
    return [
        Slide("studentaid.gov", "The plan that does not count", "Tiered Standard does not count toward PSLF. Source: studentaid.gov."),
        Slide("studentaid.gov", "Who can be placed there", "A loan first disbursed on or after July 1, 2026 can be placed on Tiered Standard. Source: studentaid.gov."),
        Slide("studentaid.gov", "What this calculator marks as counting", "RAP, IBR, PAYE, ICR, and 10-year Standard are marked as counting in this estimate. Tiered Standard, Graduated, and Extended are not."),
        Slide("studentaid.gov", "Check the help tool", "Confirm your own count with the PSLF Help Tool on StudentAid.gov."),
        _disclaimer(),
    ]


def tax_deck() -> list[Slide]:
    return [
        Slide("studentaid.gov", "Tax on a 2026 discharge", "IDR and RAP discharges on or after January 1, 2026 are federally taxable. Source: studentaid.gov."),
        Slide("studentaid.gov", "PSLF is different", "A PSLF discharge is not federally taxable. Source: studentaid.gov."),
        Slide("hypothetical", "States vary", "Hypothetical note, not tax advice. State treatment varies, including in states with no income tax. Confirm with a tax professional."),
        Slide("hypothetical", "See the estimate", "The full report shows an estimated tax at the rate you enter. " + PUBLIC_URL),
        _disclaimer(),
    ]


def all_decks() -> list[tuple[str, list[Slide]]]:
    return [
        ("save-is-over", save_deck()),
        ("rap-in-30-seconds", rap_deck()),
        ("same-salary-three-plans", salary_deck()),
        ("plan-that-does-not-count", pslf_deck()),
        ("tax-on-a-2026-discharge", tax_deck()),
    ]


def render_slide(slide: Slide) -> Image.Image:
    image = Image.new("RGB", (1080, 1350), NAVY)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1080, 18), fill=MINT)
    kicker = _font("Inter-SemiBold.ttf", 28)
    title = _font("SpaceGrotesk-Bold.ttf", 72)
    body = _font("Inter-Regular.ttf", 36 if slide.kicker != "disclaimer" else 28)
    draw.text((72, 80), BRAND_KICKER, font=kicker, fill=MINT)
    draw.text((72, 130), slide.kicker.upper(), font=kicker, fill="#8FA0B8")
    y = 200
    for line in _wrap(draw, slide.title, title, 936):
        draw.text((72, y), line, font=title, fill=PAPER)
        y += 84
    y += 24
    font = body
    for line in _wrap(draw, slide.body, font, 936):
        draw.text((72, y), line, font=font, fill=PAPER)
        y += 48
    draw.text((72, 1260), "Estimate. Not advice.  ·  " + PUBLIC_URL, font=_font("Inter-Regular.ttf", 24), fill=MINT)
    return image


def render_slide_png(slide: Slide) -> bytes:
    buffer = BytesIO()
    render_slide(slide).save(buffer, format="PNG")
    return buffer.getvalue()
