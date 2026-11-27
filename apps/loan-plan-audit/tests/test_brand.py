"""User-facing rename. Paths, secrets, and loan_plan_audit identifiers stay."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from copy_text import BRAND_KICKER, HEADLINE, PUBLIC_URL

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / "apps" / "loan-plan-audit"
FONTS = APP / "fonts"

USER_FACING = (
    APP / "copy_text.py",
    APP / "interface.py",
    APP / "app.py",
    APP / "pdf_report.py",
    APP / "share_card.py",
    APP / "carousels.py",
    APP / "checkout.py",
    APP / "legal" / "terms.md",
    APP / "legal" / "privacy.md",
    APP / "README.md",
    ROOT / "README.md",
)


def test_old_brand_and_unowned_domain_are_gone_and_the_page_title_is_the_new_name():
    assert HEADLINE == "Student Loan Plan Picker"
    assert BRAND_KICKER == "STUDENT LOAN PLAN PICKER"
    assert PUBLIC_URL == "https://loanplanaudit.streamlit.app"
    app_source = (APP / "app.py").read_text(encoding="utf-8")
    assert 'page_title="Student Loan Plan Picker"' in app_source
    assert 'file_name="student-loan-plan-picker.pdf"' in (APP / "interface.py").read_text(encoding="utf-8")
    assert 'file_name="student-loan-plan-picker-card.png"' in (APP / "interface.py").read_text(encoding="utf-8")
    for path in USER_FACING:
        text = path.read_text(encoding="utf-8")
        assert "Loan Plan Audit" not in text, path.name
        assert "LOAN PLAN AUDIT" not in text, path.name
        assert "loanplanaudit.com" not in text, path.name


def test_brand_kicker_fits_the_card_and_carousel_header():
    """1080px art with 72px side margins. Shrink the kicker if this fails."""
    draw = ImageDraw.Draw(Image.new("RGB", (1080, 1350)))
    max_width = 1080 - 72 - 72
    for size in (24, 28):
        font = ImageFont.truetype(str(FONTS / "Inter-SemiBold.ttf"), size)
        assert draw.textlength(BRAND_KICKER, font=font) <= max_width
