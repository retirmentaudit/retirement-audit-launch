"""Checkout rules. These tests do not call Stripe."""

import pytest

from checkout import (
    PRICE_SETUP_ERROR,
    PRODUCT,
    PriceNotConfigured,
    checkout_block_reason,
    fulfillment_decision,
    onetime_checkout_params,
)

NOW = "2026-11-27T00:00:00+00:00"


def _paid(user_id="user-1", email="a@example.com", session_id="cs_123", price="price_car"):
    return {
        "id": session_id,
        "payment_status": "paid",
        "mode": "payment",
        "client_reference_id": user_id,
        "customer_email": email,
        "customer": "cus_123",
        "metadata": {
            "user_id": user_id,
            "product": PRODUCT,
            "price_id": price,
            "purchase": "one_time",
        },
    }


def test_every_state_can_check_out_once_requirements_are_met():
    for state in ("CA", "California", "IL", "TX", "NY"):
        assert checkout_block_reason(state=state, agreed_to_terms=True, price_id="price_car", logged_in=True) is None
    assert checkout_block_reason(state="", agreed_to_terms=True, price_id="price_car", logged_in=True) == "state_required"
    assert checkout_block_reason(state="TX", agreed_to_terms=False, price_id="price_car", logged_in=True) == "terms_required"
    assert checkout_block_reason(state="TX", agreed_to_terms=True, price_id="", logged_in=True) == "price_missing"
    assert checkout_block_reason(state="TX", agreed_to_terms=True, price_id="price_car", logged_in=False) == "login_required"


def test_product_and_secret_names_are_separate_from_other_apps():
    import checkout

    assert PRODUCT == "dealer_fee_audit"
    assert checkout.PRICE_SECRET == "STRIPE_PRICE_ID_DEALERFEE"
    assert checkout.UNLOCK_TOKEN_SECRET == "DEALERFEE_UNLOCK_RECORD_TOKEN"
    assert checkout.PRICE_DOLLARS == 7


def test_checkout_is_one_time_and_names_the_secret_when_missing():
    params = onetime_checkout_params("user-1", "a@example.com", "price_car", "https://car.example/", state="TX")
    assert params["mode"] == "payment"
    assert params["line_items"] == [{"price": "price_car", "quantity": 1}]
    assert params["success_url"] == "https://car.example?checkout=success&session_id={CHECKOUT_SESSION_ID}"
    assert "{CHECKOUT_SESSION_ID}" in params["success_url"]
    assert params["metadata"]["product"] == PRODUCT
    assert params["metadata"]["price_id"] == "price_car"
    assert "customer_email" in params
    with pytest.raises(PriceNotConfigured, match="STRIPE_PRICE_ID_DEALERFEE"):
        onetime_checkout_params("user-1", "a@example.com", "", "https://car.example", state="TX")
    assert "does not create Stripe products or prices" in PRICE_SETUP_ERROR


def test_fulfillment_writes_an_unlock_row_for_this_product_only():
    unlocked = fulfillment_decision(_paid(), "user-1", "a@example.com", None, NOW, "price_car")
    assert unlocked["ok"] is True
    assert unlocked["reason"] == "unlocked"
    assert unlocked["update"]["product"] == PRODUCT
    assert unlocked["update"]["user_id"] == "user-1"
    assert unlocked["update"]["stripe_checkout_session_id"] == "cs_123"
    assert unlocked["update"]["terms_accepted_at"] == NOW
    assert "is_paid_user" not in unlocked["update"]

    again = fulfillment_decision(_paid(), "user-1", "a@example.com", unlocked["update"], NOW, "price_car")
    assert again["reason"] == "already_unlocked"
    assert again["update"] is None

    loan = _paid()
    loan["metadata"] = {"user_id": "user-1", "product": "loan_plan_audit", "price_id": "price_car"}
    assert fulfillment_decision(loan, "user-1", "a@example.com", None, NOW, "price_car")["reason"] == "product_mismatch"

    retirement = _paid()
    retirement["metadata"] = {"user_id": "user-1", "product": "retirement_audit"}
    assert fulfillment_decision(retirement, "user-1", "a@example.com", None, NOW, "price_car")["reason"] == "product_mismatch"

    other_price = _paid(price="price_other")
    assert fulfillment_decision(other_price, "user-1", "a@example.com", None, NOW, "price_car")["reason"] == "price_mismatch"

    unpaid = dict(_paid(), payment_status="unpaid")
    assert fulfillment_decision(unpaid, "user-1", "a@example.com", None, NOW, "price_car")["reason"] == "unpaid"
    assert fulfillment_decision(_paid(), None, "a@example.com", None, NOW, "price_car")["reason"] == "login_required"
    assert fulfillment_decision(_paid(user_id="other"), "user-1", "a@example.com", None, NOW, "price_car")["reason"] == "user_mismatch"


def test_price_matches_everywhere():
    from pathlib import Path

    import checkout
    import copy_text

    assert copy_text.PRICE_DOLLARS == checkout.PRICE_DOLLARS
    sql = (Path(__file__).resolve().parents[3] / "supabase" / "migrations" / "20261129_dealer_fee_audit.sql").read_text()
    assert f"now(), now(), {checkout.PRICE_DOLLARS * 100}" in sql
