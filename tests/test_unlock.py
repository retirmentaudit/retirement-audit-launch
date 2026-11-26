"""Rules for the $5 unlock. These tests do not call Stripe, Supabase, or OpenAI."""

from action_plan import (
    EDUCATIONAL_NOTE,
    action_plan_prompt,
    deterministic_action_plan,
    four_percent_gap,
    generate_action_plan,
    illustrated_extra_annual_savings,
)
from pdf_report import build_audit_pdf
from types import SimpleNamespace

from unlock import (
    FREE_AI_QUESTION_LIMIT,
    PAID_AI_QUESTION_LIMIT,
    ai_question_limit,
    fulfillment_decision,
    login_failure_message,
    merged_question_count,
    onetime_checkout_params,
    profile_is_paid,
    signup_needs_email_confirmation,
    user_can_ask,
)

NOW = "2026-11-26T00:00:00+00:00"


def _paid_session(user_id="user-1", email="a@example.com", session_id="cs_123"):
    return {
        "id": session_id,
        "payment_status": "paid",
        "mode": "payment",
        "client_reference_id": user_id,
        "customer_email": email,
        "customer": "cus_123",
    }


def test_active_and_trialing_subscribers_stay_paid():
    assert profile_is_paid({"is_paid_user": False, "subscription_status": "active"}) is True
    assert profile_is_paid({"is_paid_user": False, "subscription_status": "trialing"}) is True
    assert profile_is_paid({"is_paid_user": True, "subscription_status": "one_time", "paid_via": "one_time"}) is True
    assert profile_is_paid({"is_paid_user": True, "subscription_status": "canceled"}) is True
    assert profile_is_paid({"is_paid_user": False, "subscription_status": "canceled"}) is False
    assert profile_is_paid({"is_paid_user": False, "subscription_status": "free"}) is False
    assert profile_is_paid(None) is False


def test_checkout_is_one_time_payment_and_keeps_the_session_placeholder():
    params = onetime_checkout_params("user-1", "a@example.com", "price_123", "https://audit.example/")
    assert params["mode"] == "payment"
    assert params["line_items"] == [{"price": "price_123", "quantity": 1}]
    assert params["client_reference_id"] == "user-1"
    assert params["customer_email"] == "a@example.com"
    assert params["success_url"] == "https://audit.example?checkout=success&session_id={CHECKOUT_SESSION_ID}"
    assert "{CHECKOUT_SESSION_ID}" in params["success_url"]
    no_email = onetime_checkout_params("user-1", None, "price_123", "https://audit.example")
    assert "customer_email" not in no_email


def test_fulfillment_requires_paid_status_and_the_logged_in_user():
    unlocked = fulfillment_decision(_paid_session(), "user-1", "a@example.com", {}, NOW)
    assert unlocked["ok"] is True
    assert unlocked["reason"] == "unlocked"
    assert unlocked["update"]["is_paid_user"] is True
    assert unlocked["update"]["paid_via"] == "one_time"
    assert unlocked["update"]["stripe_checkout_session_id"] == "cs_123"
    assert unlocked["update"]["subscription_status"] == "one_time"
    assert unlocked["update"]["paid_at"] == NOW
    assert unlocked["update"]["stripe_customer_id"] == "cus_123"

    unpaid = dict(_paid_session(), payment_status="unpaid")
    assert fulfillment_decision(unpaid, "user-1", "a@example.com", {}, NOW)["reason"] == "unpaid"

    subscription = dict(_paid_session(), mode="subscription")
    assert fulfillment_decision(subscription, "user-1", "a@example.com", {}, NOW)["reason"] == "not_one_time"

    assert fulfillment_decision(_paid_session(), None, "a@example.com", {}, NOW)["reason"] == "login_required"


def test_reference_id_wins_over_a_matching_email():
    stolen = _paid_session(user_id="attacker", email="victim@example.com")
    decision = fulfillment_decision(stolen, "victim", "victim@example.com", {}, NOW)
    assert decision["ok"] is False
    assert decision["reason"] == "user_mismatch"
    assert decision["update"] is None


def test_email_matches_when_the_reference_id_is_missing():
    session = _paid_session()
    session["client_reference_id"] = None
    session["customer_email"] = "A@Example.com"
    decision = fulfillment_decision(session, "user-1", "a@example.com", {}, NOW)
    assert decision["ok"] is True
    assert decision["update"]["paid_via"] == "one_time"


def test_second_visit_with_the_same_session_does_not_write_again():
    profile = {
        "is_paid_user": True,
        "paid_via": "one_time",
        "subscription_status": "one_time",
        "stripe_checkout_session_id": "cs_123",
        "paid_at": NOW,
    }
    decision = fulfillment_decision(_paid_session(), "user-1", "a@example.com", profile, "2026-11-27T00:00:00+00:00")
    assert decision == {"ok": True, "reason": "already_unlocked", "update": None}


def test_one_time_payment_does_not_clear_an_active_subscription():
    profile = {"is_paid_user": True, "subscription_status": "active", "paid_via": "subscription", "paid_at": NOW}
    decision = fulfillment_decision(_paid_session(), "user-1", "a@example.com", profile, NOW)
    assert decision["ok"] is True
    assert "subscription_status" not in decision["update"]
    assert decision["update"]["paid_via"] == "one_time"
    assert "paid_at" not in decision["update"]


def test_email_confirmation_is_detected_and_explained():
    waiting = SimpleNamespace(user=SimpleNamespace(email="a@example.com"), session=None)
    ready = SimpleNamespace(user=SimpleNamespace(email="a@example.com"), session=SimpleNamespace(access_token="token"))
    assert signup_needs_email_confirmation(waiting) is True
    assert signup_needs_email_confirmation(ready) is False
    assert signup_needs_email_confirmation(None) is False
    message = login_failure_message("Email not confirmed")
    assert "Confirm your email" in message
    assert "$5 checkout" in message
    assert "No subscription." in message
    assert login_failure_message("Invalid login credentials").startswith("Login failed:")


def test_question_caps_are_3_free_and_50_paid():
    assert FREE_AI_QUESTION_LIMIT == 3
    assert PAID_AI_QUESTION_LIMIT == 50
    assert ai_question_limit(False) == 3
    assert ai_question_limit(True) == 50
    assert user_can_ask(2, False, False) == (True, None)
    assert user_can_ask(3, False, False) == (False, "login")
    assert user_can_ask(3, False, True) == (False, "paywall")
    assert user_can_ask(49, True, True) == (True, None)
    assert user_can_ask(50, True, True) == (False, "limit")
    assert merged_question_count(2, 5) == 5
    assert merged_question_count(4, 1) == 4


def _sample_inputs():
    return {
        "planning_for": "Just me",
        "current_age": 35,
        "retirement_age": 65,
        "years_to_retirement": 30,
        "total_invest": 500000,
        "annual_contributions": 6000,
        "earnings": 60000,
        "withdrawal_rate_pct": 6.0,
        "growth_pct": 6.0,
        "annual_withdrawal": 30000,
        "depletion_label": "Around age 82",
        "score": 55,
        "score_label": "Needs attention",
        "ss_annual": 28000,
        "pension_annual": 0,
        "ss_claim_age": 62,
        "manual_ss": True,
    }


def test_action_plan_uses_the_audit_numbers_and_does_not_promise_returns():
    inputs = _sample_inputs()
    gap = four_percent_gap(500000, 30000)
    assert gap == 250000
    extra = illustrated_extra_annual_savings(gap, 30)
    text = deterministic_action_plan(inputs)
    assert "What to change first" in text
    assert "How much to save" in text
    assert "Social Security claiming note" in text
    assert EDUCATIONAL_NOTE in text
    assert "does not guarantee" in text.lower()
    assert "$500,000" in text
    assert "$30,000" in text
    assert "$250,000" in text
    assert f"${extra:,.0f}" in text
    assert "62" in text
    instructions, user_message = action_plan_prompt(inputs)
    assert "What to change first" in instructions
    assert "Educational, not financial advice." in instructions
    assert "$500,000" in user_message


def test_openai_plan_uses_temperature_zero_and_falls_back_on_failure():
    inputs = _sample_inputs()
    captured = {}

    class _Response:
        output_text = "What to change first\n\nLower the withdrawal.\n\nHow much to save\n\nSave more.\n\nSocial Security claiming note\n\nCheck ssa.gov."

    class _Responses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _Response()

    class _Client:
        responses = _Responses()

    text, source = generate_action_plan(inputs, _Client())
    assert source == "openai"
    assert captured["model"] == "gpt-4.1-mini"
    assert captured["temperature"] == 0
    assert EDUCATIONAL_NOTE in text
    assert "does not guarantee" in text.lower()

    class _Broken:
        class responses:
            @staticmethod
            def create(**kwargs):
                raise RuntimeError("offline")

    fallback, source = generate_action_plan(inputs, _Broken())
    assert source == "calculator"
    assert "What to change first" in fallback
    assert generate_action_plan(inputs, None)[1] == "calculator"


def test_pdf_contains_the_score_and_the_educational_note():
    import io

    from pypdf import PdfReader

    plan = deterministic_action_plan(_sample_inputs())
    pdf = build_audit_pdf(
        {
            "score": 55,
            "score_label": "Needs attention",
            "retirement_age": 65,
            "total_invest": 500000,
            "total_nw": 500000,
            "annual_withdrawal": 30000,
            "withdrawal_rate_pct": 6,
            "growth_pct": 6,
            "depletion_label": "Around age 82",
            "ss_annual": 28000,
            "pension_annual": 0,
        },
        plan,
        generated_on="2026-11-26",
    )
    assert pdf.startswith(b"%PDF")
    text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf)).pages)
    assert "Retirement Score: 55 / 100" in text
    assert "Educational, not financial advice" in text
    assert "What to change first" in text
    assert "does not guarantee" in text.lower()
    assert "$500,000" in text
