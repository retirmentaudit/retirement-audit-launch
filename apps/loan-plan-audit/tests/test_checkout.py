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


def _paid(user_id="user-1", email="a@example.com", session_id="cs_123", price="price_loan"):
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


def test_blocked_states_never_reach_checkout():
    for state in ("CA", "California", "ca", "IL", "Illinois"):
        assert checkout_block_reason(state=state, agreed_to_terms=True, price_id="price_loan", logged_in=True) == "state_unavailable"
        with pytest.raises(ValueError, match="not available"):
            onetime_checkout_params("user-1", "a@example.com", "price_loan", "https://loan.example", state=state)
    assert checkout_block_reason(state="TX", agreed_to_terms=True, price_id="price_loan", logged_in=True) is None
    assert checkout_block_reason(state="", agreed_to_terms=True, price_id="price_loan", logged_in=True) == "state_required"
    assert checkout_block_reason(state="TX", agreed_to_terms=False, price_id="price_loan", logged_in=True) == "terms_required"
    assert checkout_block_reason(state="TX", agreed_to_terms=True, price_id="", logged_in=True) == "price_missing"
    assert checkout_block_reason(state="TX", agreed_to_terms=True, price_id="price_loan", logged_in=False) == "login_required"


def test_checkout_is_one_time_and_names_the_secret_when_missing():
    params = onetime_checkout_params("user-1", "a@example.com", "price_loan", "https://loan.example/", state="TX")
    assert params["mode"] == "payment"
    assert params["line_items"] == [{"price": "price_loan", "quantity": 1}]
    assert params["success_url"] == "https://loan.example?checkout=success&session_id={CHECKOUT_SESSION_ID}"
    assert "{CHECKOUT_SESSION_ID}" in params["success_url"]
    assert params["metadata"]["product"] == PRODUCT
    assert params["metadata"]["price_id"] == "price_loan"
    assert "customer_email" in params
    with pytest.raises(PriceNotConfigured, match="STRIPE_PRICE_ID_LOANAUDIT"):
        onetime_checkout_params("user-1", "a@example.com", "", "https://loan.example", state="TX")
    assert "does not create Stripe products or prices" in PRICE_SETUP_ERROR


def test_fulfillment_writes_an_unlock_row_for_this_product_only():
    unlocked = fulfillment_decision(_paid(), "user-1", "a@example.com", None, NOW, "price_loan")
    assert unlocked["ok"] is True
    assert unlocked["reason"] == "unlocked"
    assert unlocked["update"]["product"] == PRODUCT
    assert unlocked["update"]["user_id"] == "user-1"
    assert unlocked["update"]["stripe_checkout_session_id"] == "cs_123"
    assert unlocked["update"]["terms_accepted_at"] == NOW
    assert "is_paid_user" not in unlocked["update"]

    again = fulfillment_decision(_paid(), "user-1", "a@example.com", unlocked["update"], NOW, "price_loan")
    assert again["reason"] == "already_unlocked"
    assert again["update"] is None

    retirement = _paid()
    retirement["metadata"] = {"user_id": "user-1", "product": "retirement_audit"}
    assert fulfillment_decision(retirement, "user-1", "a@example.com", None, NOW, "price_loan")["reason"] == "product_mismatch"

    other_price = _paid(price="price_other")
    assert fulfillment_decision(other_price, "user-1", "a@example.com", None, NOW, "price_loan")["reason"] == "price_mismatch"

    unpaid = dict(_paid(), payment_status="unpaid")
    assert fulfillment_decision(unpaid, "user-1", "a@example.com", None, NOW, "price_loan")["reason"] == "unpaid"
    assert fulfillment_decision(_paid(), None, "a@example.com", None, NOW, "price_loan")["reason"] == "login_required"
    assert fulfillment_decision(_paid(user_id="other"), "user-1", "a@example.com", None, NOW, "price_loan")["reason"] == "user_mismatch"
