"""Downloadable audit PDF. Pure Python via fpdf2; no external PDF service."""

from __future__ import annotations

import io
from pathlib import Path

from fpdf import FPDF

EDUCATIONAL_NOTE = (
    "Educational, not financial advice. This PDF is a simplified illustration from the numbers you entered. "
    "It does not guarantee investment returns, Social Security payments, or how long money will last."
)

_FONT_CANDIDATES = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    Path("/usr/share/fonts/truetype/freefont/FreeSans.ttf"),
)
_BOLD_CANDIDATES = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"),
)


def _money(amount) -> str:
    return f"${float(amount or 0):,.0f}"


def _sanitize(text: str) -> str:
    replacements = {
        "\u2014": "-",
        "\u2013": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text.encode("latin-1", "replace").decode("latin-1")


def _first_existing(paths) -> Path | None:
    for path in paths:
        if path.is_file():
            return path
    return None


def build_audit_pdf(summary: dict, action_plan: str, chart_pngs: list[bytes] | None = None, generated_on: str | None = None) -> bytes:
    """Build a PDF of the score, the main dollar results, the charts, and the action plan."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    regular = _first_existing(_FONT_CANDIDATES)
    bold = _first_existing(_BOLD_CANDIDATES)
    unicode_font = regular is not None
    if unicode_font:
        pdf.add_font("Audit", "", str(regular))
        pdf.add_font("Audit", "B", str(bold or regular))
        family = "Audit"
    else:
        family = "Helvetica"

    def text(value: str) -> str:
        return value if unicode_font else _sanitize(value)

    def write(content: str, size: int, style: str = "", height: float = 6):
        pdf.set_font(family, style, size)
        # fpdf2 leaves the cursor at the right edge unless this is set, so the
        # next paragraph would have no room for a character.
        pdf.multi_cell(0, height, text(content), new_x="LMARGIN", new_y="NEXT")

    write("Retirement Audit", 18, "B", 10)
    when = generated_on or "the day you downloaded it"
    write(f"Results you entered, prepared {when}.", 10, "", 5)
    pdf.ln(1)
    write(EDUCATIONAL_NOTE, 9, "", 5)
    pdf.ln(3)
    score = summary.get("score")
    label = summary.get("score_label") or ""
    write(f"Retirement Score: {score} / 100 ({label})", 14, "B", 8)
    pdf.ln(1)
    rows = [
        ("Retirement age", str(summary.get("retirement_age"))),
        ("Projected investments", _money(summary.get("total_invest"))),
        ("Projected net worth", _money(summary.get("total_nw"))),
        ("First-year withdrawal", _money(summary.get("annual_withdrawal"))),
        ("Withdrawal rate", f"{float(summary.get('withdrawal_rate_pct') or 0):.1f}%"),
        ("Growth in retirement", f"{float(summary.get('growth_pct') or 0):.1f}%"),
        ("Money lasts estimate", str(summary.get("depletion_label") or "")),
        ("Social Security estimate", _money(summary.get("ss_annual"))),
        ("Pension estimate", _money(summary.get("pension_annual"))),
    ]
    for name, value in rows:
        write(f"{name}: {value}", 11, "", 6)

    for png in chart_pngs or []:
        if not png:
            continue
        pdf.add_page()
        write("Projection chart", 14, "B", 8)
        pdf.ln(2)
        pdf.image(io.BytesIO(png), w=pdf.epw)

    pdf.add_page()
    write("Your action plan", 16, "B", 9)
    pdf.ln(1)
    write(action_plan or "", 11, "", 6)
    pdf.ln(4)
    write(EDUCATIONAL_NOTE, 9, "", 5)
    output = pdf.output()
    return bytes(output)
