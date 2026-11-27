"""Downloadable report. The sections list is what the PDF draws, in order."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fpdf import FPDF

from copy_text import CHECKOUT_DISCLAIMER, METHOD_PARAGRAPHS, RESULTS_DISCLAIMER, RULES_DATE, SHORT_DISCLAIMER, SOURCES
from engine import AuditResult, PlanResult, lowest_estimated_total

FONTS = Path(__file__).resolve().parent / "fonts"


def _money(amount) -> str:
    if amount is None:
        return "-"
    if abs(float(amount) - round(float(amount))) < 0.005:
        return f"${float(amount):,.0f}"
    return f"${float(amount):,.2f}"


def report_sections(audit: AuditResult, plans: list[PlanResult], generated_on: str | None = None) -> list[str]:
    """Plain-text sections, in the order the PDF prints them."""
    when = generated_on or date.today().isoformat()
    sections = [
        "Student Loan Plan Picker",
        f"Software report prepared {when}. Rules last checked: {RULES_DATE}.",
        RESULTS_DISCLAIMER,
        SHORT_DISCLAIMER,
        f"Combined balance in this estimate: {_money(audit.total_balance)}.",
        f"Weighted rate before any auto-pay toggle: {audit.weighted_rate_pct:.2f} percent.",
        f"Rate used in this estimate: {audit.modeled_rate_pct:.2f} percent.",
        f"Income used in this estimate: {_money(audit.agi_used)}.",
    ]
    for note in audit.notes:
        sections.append(note)
    header = "Plan | Monthly now | Total paid | Interest paid | End | Balance at end | Estimated tax"
    sections.append(header)
    for plan in plans:
        if not plan.eligible:
            sections.append(f"{plan.label}: {plan.chips[0] if plan.chips else 'Not in this estimate'}")
            continue
        sections.append(
            " | ".join(
                [
                    plan.label,
                    _money(plan.first_year_monthly),
                    _money(plan.total_paid),
                    _money(plan.interest_paid),
                    plan.end_date or "",
                    _money(plan.forgiven_amount),
                    _money(plan.estimated_tax),
                ]
            )
        )
        if plan.interest_waived:
            sections.append(f"{plan.label} interest not added: {_money(plan.interest_waived)}.")
        if plan.principal_matched:
            sections.append(f"{plan.label} principal match: {_money(plan.principal_matched)}.")
        for note in plan.notes:
            sections.append(note)
    winner = lowest_estimated_total(plans)
    if winner:
        sections.append(f"{winner.label}: Lowest estimated total cost in this scenario.")
    sections.append("How we calculated")
    sections.extend(METHOD_PARAGRAPHS)
    sections.append("Sources")
    for label, url in SOURCES:
        sections.append(f"{label}: {url}")
    sections.append(CHECKOUT_DISCLAIMER)
    sections.append(SHORT_DISCLAIMER)
    return sections


def build_report_pdf(audit: AuditResult, plans: list[PlanResult], generated_on: str | None = None) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=16)
    regular = FONTS / "Inter-Regular.ttf"
    bold = FONTS / "Inter-Bold.ttf"
    if regular.is_file():
        pdf.add_font("Inter", "", str(regular))
        pdf.add_font("Inter", "B", str(bold if bold.is_file() else regular))
        family = "Inter"
    else:
        family = "Helvetica"
    pdf.add_page()
    pdf.set_fill_color(11, 31, 58)
    pdf.rect(0, 0, 210, 28, "F")
    pdf.set_text_color(247, 245, 240)
    pdf.set_font(family, "B", 18)
    pdf.set_xy(12, 8)
    pdf.cell(0, 12, "Student Loan Plan Picker", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(11, 31, 58)
    pdf.set_y(34)
    pdf.set_font(family, "", 10)
    for section in report_sections(audit, plans, generated_on):
        style = "B" if section in {"How we calculated", "Sources", "Student Loan Plan Picker"} else ""
        size = 14 if section == "How we calculated" else 10
        pdf.set_font(family, style, size)
        pdf.multi_cell(0, 5.5, section, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
    return bytes(pdf.output())
