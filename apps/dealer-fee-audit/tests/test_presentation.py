"""Disclaimers and copy rules, plus a smoke run of the Streamlit app in local demo mode."""

import os
import re
from pathlib import Path

import pytest

import copy_text
from copy_text import (
    AVOID_WORDS,
    CHECKOUT_DISCLAIMER,
    LANDING_STRIP,
    RESULTS_DISCLAIMER,
    SHORT_DISCLAIMER,
    privacy_markdown,
    terms_markdown,
)

APP_DIR = Path(__file__).resolve().parents[1]
INTERFACE = (APP_DIR / "interface.py").read_text(encoding="utf-8")


def test_disclaimers_say_the_key_things():
    for text in (LANDING_STRIP, SHORT_DISCLAIMER):
        assert "not legal" in text.lower()
        assert "not" in text and ("dealer" in text.lower())
    assert "not a finding" in RESULTS_DISCLAIMER
    assert "attorney" in RESULTS_DISCLAIMER
    assert "No subscription" in CHECKOUT_DISCLAIMER
    assert "guarantee" in CHECKOUT_DISCLAIMER


def test_footer_and_results_screens_render_disclaimers():
    footer = INTERFACE[INTERFACE.index("def _footer"):INTERFACE.index("def _rules")]
    assert "SHORT_DISCLAIMER" in footer
    results = INTERFACE[INTERFACE.index("def _results"):INTERFACE.index("def _paid_report")]
    assert "_full_disclaimer()" in results
    fuller = INTERFACE[INTERFACE.index("def _full_disclaimer"):INTERFACE.index("def _sidebar")]
    assert "RESULTS_DISCLAIMER" in fuller
    assert "CHECKOUT_DISCLAIMER" in INTERFACE[INTERFACE.index("def _checkout_panel"):INTERFACE.index("def _results")]
    assert "SCRIPT_DISCLAIMER" in INTERFACE[INTERFACE.index("def _paid_report"):INTERFACE.index("def _save_panel")]
    run = INTERFACE[INTERFACE.index("def run("):]
    assert run.rstrip().endswith("_footer()")


def test_marketing_copy_avoids_risky_claims():
    marketing = " ".join(
        [copy_text.HEADLINE, copy_text.TAGLINE, copy_text.ALT_TAGLINE, *copy_text.BULLETS, copy_text.CTA]
    ).lower()
    for word in AVOID_WORDS:
        assert word not in marketing
    assert "illegal" not in INTERFACE.lower()


def test_legal_drafts_keep_placeholders_visible():
    terms = terms_markdown()
    privacy = privacy_markdown()
    assert "[LEGAL ENTITY NAME, LLC]" in terms and "[LEGAL ENTITY NAME, LLC]" in privacy
    assert "DRAFT" in terms and "DRAFT" in privacy
    assert "arbitration" in terms.lower()
    assert "not a motor vehicle dealer" in terms
    assert "don't sell" in privacy.lower()


@pytest.fixture
def demo_env(monkeypatch):
    monkeypatch.setenv("DEALER_FEE_AUDIT_LOCAL_DEMO", "1")
    yield


def _app(query=None):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP_DIR / "app.py"), default_timeout=30)
    for key, value in (query or {}).items():
        at.query_params[key] = value
    return at


def _all_markdown(at):
    return " ".join(m.value for m in at.markdown)


def test_app_landing_renders_with_disclaimer(demo_env):
    at = _app().run()
    assert not at.exception
    text = _all_markdown(at)
    assert "Dealer Fee Check" in text
    assert "Not legal, financial, or tax advice" in text
    assert "not legal, financial, or tax advice" in text  # footer


def test_app_free_results_show_preview_and_paywall(demo_env):
    at = _app({"demo_sample": "1"}).run()
    assert not at.exception
    text = _all_markdown(at)
    assert "Free preview" in text
    assert "Full report — one-time $7" in text
    assert "not a finding" in text
    assert "Message you can edit" not in text


def test_app_paid_results_show_full_report(demo_env):
    at = _app({"demo_sample": "1", "demo_user": "paid"}).run()
    assert not at.exception
    text = _all_markdown(at)
    assert "Every line" in text
    assert "Message you can edit and send" in text
    assert any("Template only" in c.value for c in at.caption)


def test_app_missing_price_shows_setup_error(demo_env):
    at = _app({"demo_sample": "1", "demo_missing_price": "1"}).run()
    assert any("STRIPE_PRICE_ID_DEALERFEE" in e.value for e in at.error)


def test_app_terms_page(demo_env):
    at = _app({"view": "terms"}).run()
    assert not at.exception
    assert "Terms of Service" in _all_markdown(at)


def test_demo_refuses_live_keys():
    from demo import demo_active

    os.environ["DEALER_FEE_AUDIT_LOCAL_DEMO"] = "1"
    try:
        assert demo_active("sk_live_x") is False
        assert demo_active("sk_test_x") is True
    finally:
        del os.environ["DEALER_FEE_AUDIT_LOCAL_DEMO"]


def test_app_entry_form_to_free_result(demo_env):
    at = _app().run()
    at.sidebar.radio[0].set_value("Check a quote").run()
    at.number_input[0].set_value(28_000.0).run()
    next(b for b in at.button if b.label == "Check my quote").click().run()
    assert not at.exception
    text = _all_markdown(at)
    assert "Free preview" in text
    assert "not a finding" in text


def test_app_entry_form_requires_a_price(demo_env):
    at = _app().run()
    at.sidebar.radio[0].set_value("Check a quote").run()
    next(b for b in at.button if b.label == "Check my quote").click().run()
    assert any("vehicle price" in e.value for e in at.error)
