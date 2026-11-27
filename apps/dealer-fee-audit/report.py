"""Downloadable PDF for the paid report. Core fonts only, so text is Latin-1 safe."""

from __future__ import annotations

from fpdf import FPDF

from copy_text import RESULTS_DISCLAIMER, SCRIPT_DISCLAIMER
from engine import QuoteAudit, QuoteInput, counter_offer_text

_REPLACE = {"—": "-", "–": "-", "“": '"', "”": '"', "’": "'", "‘": "'", "§": "Sec.", "•": "-", "…": "..."}


def _safe(text: str) -> str:
    for key, value in _REPLACE.items():
        text = text.replace(key, value)
    return text.encode("latin-1", "replace").decode("latin-1")


def build_report_pdf(quote: QuoteInput, audit: QuoteAudit) -> bytes:
    pdf = FPDF(format="Letter")
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()
    width = pdf.w - pdf.l_margin - pdf.r_margin

    def para(text, size=10, style=""):
        pdf.set_font("Helvetica", style, size)
        pdf.multi_cell(width, size * 0.5 + 1, _safe(text))
        pdf.ln(1)

    para("Dealer Fee Audit - full report", 16, "B")
    para(f"{quote.vehicle or 'Vehicle'} - {audit.state} - {quote.condition}", 10)
    para(f"Out-the-door total (as entered): ${audit.out_the_door:,.2f}", 12, "B")
    para(f"Optional or above-limit items: ${audit.removable_total:,.2f} ({audit.flagged_count} items flagged)", 11)
    if audit.monthly_payment is not None:
        para(
            f"Estimated payment: ${audit.monthly_payment:,.2f}/mo; without the optional items: "
            f"${audit.monthly_without_removable:,.2f}/mo (about ${audit.finance_cost_of_removable:,.2f} over the loan).",
            10,
        )
    para("Line by line", 13, "B")
    for line in audit.lines:
        para(f"{line.label}  ${line.amount:,.2f}  [{line.verdict_label}]", 10, "B")
        para(f"{line.headline}. {line.detail}", 9)
    para("Message you can edit and send", 13, "B")
    para(counter_offer_text(quote, audit), 9)
    para(SCRIPT_DISCLAIMER, 8, "I")
    para(RESULTS_DISCLAIMER, 8, "I")
    return bytes(pdf.output())
