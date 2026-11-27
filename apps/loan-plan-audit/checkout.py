"""One-time $9 Checkout for Loan Plan Audit.

These functions do not call Stripe. The app passes a Checkout Session
(or a dict with the same fields) and writes the unlock row itself.

The price id comes from the secret STRIPE_PRICE_ID_LOANAUDIT. Nothing here
creates a Stripe product or price. California and Illinois never reach checkout.
"""

from __future__ import annotations

from states import residence_gate

PRODUCT = "loan_plan_audit"
PRICE_SECRET = "STRIPE_PRICE_ID_LOANAUDIT"
PRICE_DOLLARS = 9

PRICE_SETUP_ERROR = (
    "Setup needed: STRIPE_PRICE_ID_LOANAUDIT is missing. "
    "Add the Price ID for the existing $9 one-time price (it starts with price_). "
    "Loan Plan Audit does not create Stripe products or prices."
)


class PriceNotConfigured(ValueError):
    """Raised when checkout is asked to start without STRIPE_PRICE_ID_LOANAUDIT."""


def _get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def checkout_block_reason(*, state: str | None, agreed_to_terms: bool, price_id: str | None, logged_in: bool) -> str | None:
    """None when checkout may start. Otherwise a stable reason code.

    A blocked state wins over every other reason so the paid button never appears.
    """
    gate = residence_gate(state)
    if gate == "missing":
        return "state_required"
    if gate == "blocked":
        return "state_unavailable"
    if not price_id:
        return "price_missing"
    if not agreed_to_terms:
        return "terms_required"
    if not logged_in:
        return "login_required"
    return None


def onetime_checkout_params(
    user_id: str,
    email: str | None,
    price_id: str | None,
    app_url: str,
    state: str | None = None,
) -> dict:
    """Arguments for stripe.checkout.Session.create in payment mode.

    The success URL keeps the literal {CHECKOUT_SESSION_ID} placeholder.
    Stripe replaces it on the way back. Metadata.product keeps this purchase
    off the Retirement Audit profile flag.
    """
    if not user_id:
        raise ValueError("Log in before checkout.")
    if not price_id:
        raise PriceNotConfigured(PRICE_SETUP_ERROR)
    if state is not None and residence_gate(state) != "ok":
        raise ValueError("Checkout is not available for this state of residence.")
    base = app_url.rstrip("/")
    params = {
        "mode": "payment",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": f"{base}?checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{base}?checkout=cancel",
        "allow_promotion_codes": True,
        "client_reference_id": str(user_id),
        "metadata": {
            "user_id": str(user_id),
            "email": email or "",
            "purchase": "one_time",
            "product": PRODUCT,
            "price_id": str(price_id),
        },
    }
    if email:
        params["customer_email"] = email
    return params


def session_email(session) -> str | None:
    email = _get(session, "customer_email")
    if email:
        return str(email)
    details = _get(session, "customer_details")
    if details is not None:
        detailed = _get(details, "email")
        if detailed:
            return str(detailed)
    return None


def session_matches_user(session, user_id: str, email: str | None) -> bool:
    """True when this payment belongs to the logged-in user.

    A client_reference_id for someone else is never overridden by a matching email.
    """
    if not user_id:
        return False
    reference = _get(session, "client_reference_id")
    if reference:
        return str(reference) == str(user_id)
    paid_email = session_email(session)
    if email and paid_email and paid_email.strip().lower() == email.strip().lower():
        return True
    metadata = _get(session, "metadata") or {}
    meta_user = _get(metadata, "user_id")
    if meta_user and str(meta_user) == str(user_id):
        return True
    return False


def fulfillment_decision(
    session,
    user_id: str | None,
    email: str | None,
    existing: dict | None,
    now_iso: str,
    expected_price_id: str | None,
) -> dict:
    """Decide whether a returned Checkout Session writes an unlocks row.

    The same session id on an existing row produces no further update.
    A Retirement Audit session (no loan_plan_audit product) is rejected.
    """
    if not user_id:
        return {"ok": False, "reason": "login_required", "update": None}

    existing = existing or {}
    session_id = str(_get(session, "id") or "")
    if session_id and existing.get("stripe_checkout_session_id") == session_id and existing.get("product") == PRODUCT:
        return {"ok": True, "reason": "already_unlocked", "update": None}

    if str(_get(session, "payment_status") or "") != "paid":
        return {"ok": False, "reason": "unpaid", "update": None}
    if str(_get(session, "mode") or "") != "payment":
        return {"ok": False, "reason": "not_one_time", "update": None}
    if not session_matches_user(session, user_id, email):
        return {"ok": False, "reason": "user_mismatch", "update": None}

    metadata = _get(session, "metadata") or {}
    product = str(_get(metadata, "product") or "")
    if product != PRODUCT:
        return {"ok": False, "reason": "product_mismatch", "update": None}
    price_on_session = str(_get(metadata, "price_id") or "")
    if expected_price_id and price_on_session and price_on_session != str(expected_price_id):
        return {"ok": False, "reason": "price_mismatch", "update": None}

    update = {
        "user_id": str(user_id),
        "product": PRODUCT,
        "stripe_checkout_session_id": session_id,
        "paid_at": now_iso,
        "terms_accepted_at": now_iso,
        "amount_cents": PRICE_DOLLARS * 100,
    }
    customer = _get(session, "customer")
    if isinstance(customer, str) and customer:
        update["stripe_customer_id"] = customer
    return {"ok": True, "reason": "unlocked", "update": update}
