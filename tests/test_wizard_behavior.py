"""Behavior checks for the retirement wizard and the $5 unlock.

RETIREMENT_AUDIT_LOCAL_DEMO stubs Stripe and Supabase. These tests do not call
OpenAI, Stripe, or a real Supabase project.
"""

import os
from pathlib import Path

os.environ["RETIREMENT_AUDIT_LOCAL_DEMO"] = "1"

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = str(ROOT / "app.py")


def _markdown_text(at: AppTest) -> str:
    parts = [getattr(el, "value", "") or "" for el in at.markdown]
    parts.extend(getattr(el, "value", "") or "" for el in at.caption)
    return "\n".join(parts)


def _labels(widgets) -> list[str]:
    return [getattr(widget, "label", "") or "" for widget in widgets]


def _boot(**state) -> AppTest:
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.session_state["started"] = True
    for key, value in state.items():
        at.session_state[key] = value
    at.run()
    assert not at.exception, at.exception
    return at


def test_just_me_hides_spouse_fields_and_ignores_spouse_balances():
    at = _boot(wizard_step=2, planning_for="Just me", spouse2_age=70)
    labels = _labels(at.number_input)
    assert "Your current age" in labels
    assert "Target retirement age" in labels
    assert not any("Spouse" in label for label in labels)

    at.session_state["wizard_step"] = 4
    at.run()
    assert not at.exception, at.exception
    labels = _labels(at.number_input)
    assert "Your average annual earnings" in labels
    assert not any(label.startswith("Spouse") for label in labels)

    at.session_state["wizard_step"] = 7
    at.session_state["spouse2_use_traditional_401k"] = True
    at.session_state["spouse2_trad_401k_bal"] = 250000
    at.session_state["spouse2_trad_401k_cont"] = 10000
    at.session_state["avg_earn_sp2"] = 120000
    at.session_state["pen_sp2"] = 40000
    at.session_state["use_pension"] = True
    at.run()
    assert not at.exception, at.exception
    text = _markdown_text(at)
    assert "Enter a balance or income to see your score" in text
    assert "41 / 100" not in text
    assert "$250,000" not in text


def test_me_plus_spouse_shows_spouse_fields_and_uses_spouse_balance():
    at = _boot(wizard_step=2, planning_for="Me + spouse")
    labels = _labels(at.number_input)
    assert "Spouse's current age" in labels

    at.session_state["wizard_step"] = 4
    at.run()
    assert not at.exception, at.exception
    labels = _labels(at.number_input)
    assert any(label.startswith("Spouse") for label in labels)

    at.session_state["wizard_step"] = 7
    at.session_state["spouse1_use_traditional_401k"] = True
    at.session_state["spouse1_trad_401k_bal"] = 10000
    at.run()
    assert not at.exception, at.exception
    text = _markdown_text(at)
    assert "Retirement Score:" in text
    assert "41 / 100" not in text
    assert "Enter a balance or income to see your score" not in text


def test_blank_plan_does_not_show_baseline_score():
    at = _boot(wizard_step=7, planning_for="Just me", avg_earn_sp1=0)
    text = _markdown_text(at)
    assert "Enter a balance or income to see your score" in text
    assert "41 / 100" not in text
    assert "Retirement Score:" not in text


def test_signed_in_audit_is_listed_in_my_scenarios():
    at = _boot(
        wizard_step=7,
        started=True,
        user_logged_in=True,
        user_id="user-1",
        user_email="a@example.com",
        planning_for="Just me",
        avg_earn_sp1=60000,
        spouse1_use_traditional_401k=True,
        spouse1_trad_401k_bal=50000,
    )
    assert not at.exception, at.exception
    at.session_state["show_my_scenarios"] = True
    at.run()
    assert not at.exception, at.exception
    text = _markdown_text(at)
    assert "My scenarios" in text
    assert "/ 100" in text
    labels = _labels(at.button)
    assert "Open" in labels
    assert "Rename" in labels
    assert "Delete" in labels


def test_landing_has_login_and_does_not_require_an_account():
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.session_state["started"] = False
    at.run()
    assert not at.exception, at.exception
    text = _markdown_text(at)
    info = "\n".join(getattr(el, "value", "") or "" for el in at.info)
    assert "Already have an account? Log in" in text
    assert "No account needed to start" in text or "No account needed to start" in info
    assert "Start My Free Retirement Audit" in _labels(at.button)
    assert "Log in" in _labels(at.button)


def test_results_show_livable_income_and_keep_the_score_free():
    at = _boot(
        wizard_step=7,
        planning_for="Just me",
        avg_earn_sp1=60000,
        spouse1_use_traditional_401k=True,
        spouse1_trad_401k_bal=250000,
    )
    text = _markdown_text(at)
    assert "Retirement Score:" in text
    assert "You'll need about" in text
    assert "in today's dollars" in text
    assert "Your plan covers about" in text
    assert "Unlock your full Retirement Audit" in text
    assert "41 / 100" not in text


def test_earnings_alone_show_score_with_explanation():
    at = _boot(wizard_step=7, planning_for="Just me", avg_earn_sp1=60000)
    text = _markdown_text(at)
    joined = text + "\n" + "\n".join(el.value for el in at.info)
    assert "Retirement Score:" in text
    assert "no investment balance" in joined


def test_target_retirement_age_cannot_default_below_current_age():
    at = _boot(
        wizard_step=2,
        planning_for="Just me",
        spouse1_age=72,
        retirement_age=65,
    )
    target = next(widget for widget in at.number_input if widget.label == "Target retirement age")
    assert target.min == 72
    assert target.max == 80
    assert int(at.session_state["retirement_age"]) >= 72
    assert "Your current age" in _labels(at.number_input)
    assert not any(widget.label == "Target retirement age" and widget.min == 40 for widget in at.number_input)


def test_younger_user_keeps_age_65_default_and_clear_range():
    at = _boot(wizard_step=2, planning_for="Just me", spouse1_age=35, retirement_age=65)
    target = next(widget for widget in at.number_input if widget.label == "Target retirement age")
    assert target.min == 40
    assert target.max == 80
    assert int(at.session_state["retirement_age"]) == 65
    assert "must be from 40 to 80" in _markdown_text(at)


def test_subscription_checkout_and_billing_portal_are_gone():
    import re

    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "billing_portal" not in source
    assert "create_portal_session" not in source
    assert "Upgrade to Pro" not in source
    assert "$1.99" not in source
    assert re.search(r"STRIPE_PRICE_ID(?!_ONETIME)", source) is None
    assert 'mode="subscription"' not in source
    assert "mode='subscription'" not in source


def test_creator_footer_is_spelled_correctly_and_blank_text_rule_is_gone():
    at = _boot(wizard_step=1, planning_for="Just me")
    text = _markdown_text(at)
    assert "Created by retirementaudit" in text
    assert "Created by retirmentaudit" not in text
    assert "div, span { color: white !important; }" not in text
    assert 'toolbarMode = "minimal"' in (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert 'data-testid="stToolbarActions"' in (ROOT / "app.py").read_text(encoding="utf-8")


def test_unlock_button_opens_a_short_signup_and_keeps_the_audit():
    at = _boot(
        wizard_step=7,
        planning_for="Just me",
        spouse1_use_traditional_401k=True,
        spouse1_trad_401k_bal=50000,
    )
    unlock = next(button for button in at.button if button.label == "Unlock my full audit — $5")
    unlock.click()
    at.run()
    assert not at.exception, at.exception
    text = _markdown_text(at)
    assert "Create a free account to unlock — takes 10 seconds. No subscription." in text
    assert "A free account is required before checkout" not in text
    assert "Retirement Score:" in text
    assert int(at.session_state["spouse1_trad_401k_bal"]) == 50000
    assert int(at.session_state["wizard_step"]) == 7
    labels = _labels(at.button)
    assert "Create free account" in labels
    assert "Log in" in labels
    assert labels.index("Create free account") < labels.index("Log in")


def test_pending_checkout_shows_one_continue_button_and_keeps_answers():
    at = _boot(
        wizard_step=7,
        planning_for="Just me",
        spouse1_use_traditional_401k=True,
        spouse1_trad_401k_bal=50000,
        user_logged_in=True,
        user_id="user-1",
        user_email="a@example.com",
        is_paid_user=False,
        _pending_checkout=True,
    )
    text = _markdown_text(at)
    joined = text + "\n" + "\n".join(getattr(el, "value", "") or "" for el in at.success)
    assert "Continue to the $5 checkout" in joined
    assert "Continue to $5 checkout" in _labels(at.link_button)
    assert "A free account is required before checkout" not in text
    assert "Create a free account to keep going" not in text
    assert int(at.session_state["spouse1_trad_401k_bal"]) == 50000
    assert "Retirement Score:" in text


def test_free_results_keep_the_score_and_show_the_one_time_unlock():
    at = _boot(
        wizard_step=7,
        planning_for="Just me",
        spouse1_use_traditional_401k=True,
        spouse1_trad_401k_bal=50000,
    )
    text = _markdown_text(at)
    assert "Retirement Score:" in text
    assert "Unlock your full Retirement Audit — $5 once" in text
    assert "No subscription." in text
    assert "$1.99" not in text
    assert "Upgrade to Pro" not in text
    assert "Unlock my full audit — $5" in _labels(at.button)
    assert at.download_button == []


def test_paid_results_include_the_action_plan_and_pdf_without_hiding_the_score():
    at = _boot(
        wizard_step=7,
        planning_for="Just me",
        is_paid_user=True,
        spouse1_use_traditional_401k=True,
        spouse1_trad_401k_bal=50000,
    )
    text = _markdown_text(at)
    assert "Retirement Score:" in text
    assert "What to change first" in text
    assert "How much to save" in text
    assert "Social Security claiming note" in text
    assert "Educational, not financial advice" in text
    assert "Unlock your full Retirement Audit" not in text
    assert any("PDF" in (button.label or "") for button in at.download_button)


def test_exhausted_free_questions_show_the_same_paywall():
    at = _boot(
        wizard_step=7,
        planning_for="Just me",
        spouse1_use_traditional_401k=True,
        spouse1_trad_401k_bal=50000,
        ai_question_count=3,
    )
    text = _markdown_text(at)
    assert text.count("Unlock your full Retirement Audit — $5 once") >= 2
    assert "You've used your 3 free AI questions." in text or "You've used your 3 free AI questions." in "\n".join(
        getattr(el, "value", "") or "" for el in at.caption
    )


def test_returned_demo_checkout_unlocks_without_calling_stripe():
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.query_params["checkout"] = "success"
    at.query_params["session_id"] = "cs_demo_paid"
    at.query_params["demo_sample"] = "1"
    at.run()
    assert not at.exception, at.exception
    text = _markdown_text(at)
    joined = text + "\n" + "\n".join(getattr(el, "value", "") or "" for el in at.success)
    assert "Payment confirmed" in joined
    assert "Retirement Score:" in text
    assert "What to change first" in text
    assert "one-time" in joined.lower() or "already unlocked" in joined.lower()
