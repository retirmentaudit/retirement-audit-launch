"""Copy, share card, PDF, and sample posts. No network."""

import ast
from pathlib import Path

from copy_text import (
    CHECKOUT_DISCLAIMER,
    INPUT_LABELS,
    LANDING_STRIP,
    RESULTS_DISCLAIMER,
    SHORT_DISCLAIMER,
    privacy_markdown,
    terms_markdown,
)
from engine import make_scenario, build_audit
from pdf_report import build_report_pdf, report_sections
from share_card import card_lines, render_share_card
from carousels import all_decks, render_slide
from PIL import Image
import io

ROOT = Path(__file__).resolve().parents[1]
BANNED = (
    "best plan for you",
    "you should",
    "we recommend",
    "debt relief",
    "erase your",
    "cancel your loans",
    "official",
    "federal program",
    "guaranteed",
    "you qualify",
    "advisor",
    "counselor",
    "consultant",
    "act now",
    "expert",
)


def test_disclaimers_match_the_legal_text_and_placeholders_stay():
    assert SHORT_DISCLAIMER.startswith("Educational estimates only — not financial, legal, or tax advice.")
    assert "Not affiliated with the U.S. Department of Education or any loan servicer." in SHORT_DISCLAIMER
    assert "You never have to pay for help with federal student loans." in SHORT_DISCLAIMER
    assert "November 26, 2026" in RESULTS_DISCLAIMER
    assert "we don't recommend any plan" in RESULTS_DISCLAIMER
    assert CHECKOUT_DISCLAIMER.startswith("You're buying access to a software report.")
    assert "One-time charge of $9." in CHECKOUT_DISCLAIMER
    assert "Not affiliated with the U.S. Department of Education." in LANDING_STRIP
    terms = terms_markdown()
    privacy = privacy_markdown()
    for token in ("[DATE]", "[LEGAL ENTITY NAME, LLC]", "[ADDRESS]", "[CONTACT EMAIL]", "[EMAIL]", "[STATE]", "[AAA/JAMS]"):
        assert token in terms
    for token in ("[DATE]", "[LEGAL ENTITY NAME, LLC]", "[CONTACT EMAIL]", "[PROVIDER]", "[AI provider]", "[EMAIL]", "[ADDRESS]"):
        assert token in privacy
    assert "[No advertising pixels on the app.]" in privacy


def test_share_card_hides_balances_and_income_by_default():
    audit = build_audit(make_scenario())
    plans = audit.worlds["primary"]
    hidden = "\n".join(card_lines(audit, plans, show_private=False))
    shown = "\n".join(card_lines(audit, plans, show_private=True))
    assert "40,000" not in hidden
    assert "53,000" not in hidden
    assert "Balance" not in hidden
    assert "Income" not in hidden
    assert "40,000" in shown
    assert "53,000" in shown
    assert "221" in hidden
    assert "https://loanplanaudit.streamlit.app" in hidden
    assert "Estimate. Not advice." in hidden
    assert SHORT_DISCLAIMER in hidden
    image = Image.open(io.BytesIO(render_share_card(audit, plans, show_private=False)))
    assert image.size == (1080, 1350)


def test_pdf_includes_the_method_and_disclaimers():
    audit = build_audit(make_scenario())
    plans = audit.worlds["primary"]
    sections = "\n".join(report_sections(audit, plans, generated_on="2026-11-27"))
    assert RESULTS_DISCLAIMER in sections
    assert SHORT_DISCLAIMER in sections
    assert "How we calculated" in sections
    assert "studentaid.gov" in sections
    pdf = build_report_pdf(audit, plans, generated_on="2026-11-27")
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


def test_sample_posts_end_on_the_disclaimer_and_cite_studentaid():
    decks = all_decks()
    assert len(decks) == 5
    assert [len(slides) for _name, slides in decks] == [6, 5, 5, 5, 5]
    for _name, slides in decks:
        text = "\n".join(slide.title + "\n" + slide.body for slide in slides)
        assert "studentaid.gov" in text.lower()
        assert slides[-1].kicker == "disclaimer"
        assert "Educational estimates only" in slides[-1].body
        assert "https://loanplanaudit.streamlit.app" in slides[-1].body
        assert render_slide(slides[-1]).size == (1080, 1350)
    salary = dict(decks)["same-salary-three-plans"]
    assert "Hypothetical example" in salary[0].body


def test_inputs_do_not_ask_for_credentials_and_source_stays_clean():
    labels = " ".join(INPUT_LABELS).lower()
    assert "social security" not in labels
    assert "fsa" not in labels
    assert "servicer" not in labels
    source = ""
    for path in ROOT.rglob("*.py"):
        if "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        source += text
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                lowered = node.value.lower()
                for phrase in BANNED:
                    assert phrase not in lowered, f"{phrase} in {path.name}: {node.value[:80]}"
    assert "Product.create" not in source
    assert "Price.create" not in source
    assert "Subscription.create" not in source
    assert "fbq(" not in source
    assert "googletagmanager" not in source
    assert "facebook.com/tr" not in source
