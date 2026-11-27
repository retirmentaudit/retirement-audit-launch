"""1080×1350 result card. Balances and income stay off unless the privacy toggle is on."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from copy_text import SHORT_DISCLAIMER
from engine import AuditResult, PlanResult, soonest_payoff

FONTS = Path(__file__).resolve().parent / "fonts"
NAVY = "#0B1F3A"
MINT = "#2BD9A0"
PAPER = "#F7F5F0"
CORAL = "#FF6B5A"
SKY = "#5AB8FF"
GOLD = "#F5B841"

PLAN_COLORS = {
    "standard_10": "#F7F5F0",
    "tiered_standard": CORAL,
    "rap": SKY,
    "ibr_15": MINT,
    "ibr_10": "#8FF3D2",
    "paye_bridge": GOLD,
}


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = FONTS / name
    if path.is_file():
        return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = word if not current else f"{current} {word}"
        if draw.textlength(trial, font=font) <= width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _money(amount: float | None) -> str:
    if amount is None:
        return "—"
    if abs(amount - round(amount)) < 0.005:
        return f"${amount:,.0f}"
    return f"${amount:,.2f}"


def card_lines(audit: AuditResult, plans: list[PlanResult], show_private: bool) -> list[str]:
    """Text placed on the card. Private figures are omitted unless show_private is true."""
    lines = ["Loan Plan Audit", "My loans, every plan", "First-year estimated monthly payment"]
    for plan in plans:
        if plan.eligible and plan.first_year_monthly is not None:
            lines.append(f"{plan.label}  {_money(plan.first_year_monthly)}")
    payoff = soonest_payoff(plans)
    if payoff and payoff.end_date:
        lines.append(f"Paid off in {payoff.end_date[:4]}")
        lines.append(payoff.label)
    else:
        lines.append("Compare the plan end dates in the full report")
    if show_private:
        lines.append(f"Balance {_money(audit.total_balance)}")
        lines.append(f"Income {_money(audit.agi_used)}")
    lines.append("loanplanaudit.com")
    lines.append("Estimate. Not advice.")
    lines.append(SHORT_DISCLAIMER)
    return lines


def render_share_card(audit: AuditResult, plans: list[PlanResult], show_private: bool = False) -> bytes:
    image = Image.new("RGB", (1080, 1350), NAVY)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1080, 18), fill=MINT)
    title_font = _font("SpaceGrotesk-Bold.ttf", 84)
    sub_font = _font("Inter-Regular.ttf", 32)
    plan_font = _font("Inter-SemiBold.ttf", 34)
    money_font = _font("SpaceGrotesk-Bold.ttf", 48)
    small = _font("Inter-Regular.ttf", 22)
    tiny = _font("Inter-Regular.ttf", 20)

    draw.text((72, 70), "LOAN PLAN AUDIT", font=_font("Inter-SemiBold.ttf", 24), fill=MINT)
    draw.text((72, 120), "My loans, every plan", font=title_font, fill=PAPER)
    draw.text((72, 230), "First-year estimated monthly payment", font=sub_font, fill="#D5DEEA")

    y = 320
    if show_private:
        private = f"Balance {_money(audit.total_balance)}   ·   Income {_money(audit.agi_used)}"
        draw.text((72, y), private, font=small, fill=GOLD)
        y += 48
    else:
        draw.text((72, y), "Balances and income hidden", font=small, fill="#8FA0B8")
        y += 48

    shown = [plan for plan in plans if plan.eligible and plan.first_year_monthly is not None][:6]
    for plan in shown:
        color = PLAN_COLORS.get(plan.plan_id, MINT)
        draw.rounded_rectangle((72, y, 1008, y + 92), radius=18, fill="#132C4E")
        draw.ellipse((96, y + 32, 124, y + 60), fill=color)
        draw.text((148, y + 26), plan.label, font=plan_font, fill=PAPER)
        amount = _money(plan.first_year_monthly)
        width = draw.textlength(amount, font=money_font)
        draw.text((980 - width, y + 18), amount, font=money_font, fill=PAPER)
        y += 108

    payoff = soonest_payoff(plans)
    if payoff and payoff.end_date:
        headline = f"Paid off in {payoff.end_date[:4]}"
        detail = payoff.label
    else:
        headline = "See plan end dates"
        detail = "Estimate. Not advice."
    draw.text((72, 1040), headline, font=_font("SpaceGrotesk-Bold.ttf", 54), fill=MINT)
    draw.text((72, 1110), detail, font=sub_font, fill=PAPER)

    draw.rectangle((0, 1180, 1080, 1350), fill="#081628")
    footer = "loanplanaudit.com    ·    Estimate. Not advice."
    draw.text((72, 1196), footer, font=small, fill=MINT)
    for index, line in enumerate(_wrap(draw, SHORT_DISCLAIMER, tiny, 936)[:4]):
        draw.text((72, 1232 + index * 24), line, font=tiny, fill="#D5DEEA")

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
