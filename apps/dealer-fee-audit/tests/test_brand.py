"""User-facing rename. Paths, secrets, tables, and the migration stay."""

from pathlib import Path

from copy_text import HEADLINE, PUBLIC_URL

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parents[1]

USER_FACING = (
    APP / "copy_text.py",
    APP / "interface.py",
    APP / "app.py",
    APP / "report.py",
    APP / "checkout.py",
    APP / "engine.py",
    APP / "fees.py",
    APP / "legal" / "terms.md",
    APP / "legal" / "privacy.md",
    APP / "README.md",
    ROOT / "README.md",
)


def test_old_brand_is_gone_and_the_page_title_is_dealer_fee_check():
    assert HEADLINE == "Dealer Fee Check"
    assert PUBLIC_URL == "https://dealerfeecheck.streamlit.app"
    app_source = (APP / "app.py").read_text(encoding="utf-8")
    interface = (APP / "interface.py").read_text(encoding="utf-8")
    assert 'page_title="Dealer Fee Check"' in app_source
    assert 'file_name="dealer-fee-check.pdf"' in interface
    assert 'file_name="dealer-fee-check-message.txt"' in interface
    for path in USER_FACING:
        text = path.read_text(encoding="utf-8")
        assert "Dealer Fee Audit" not in text, path.name
        assert "DEALER FEE AUDIT" not in text, path.name
