"""One-time $7 Checkout for Dealer Fee Audit.

These functions do not call Stripe. The app retrieves a Checkout Session and
passes it here. A paid, matching session is not enough to write `unlocks`:
the database function also requires DEALERFEE_UNLOCK_RECORD_TOKEN, and it writes only
for auth.uid(). Nothing here creates a Stripe product or price.
No state is blocked for this product; a state is still required.
"""

from __future__ import annotations

import hmac

from fees import residence_gate

PRODUCT = "dealer_fee_audit"
PRICE_SECRET = "STRIPE_PRICE_ID_DEALERFEE"
UNLOCK_TOKEN_SECRET = "DEALERFEE_UNLOCK_RECORD_TOKEN"
PRICE_DOLLARS = 7

PRICE_SETUP_ERROR = (
    "Setup needed: STRIPE_PRICE_ID_DEALERFEE is missing. "
    "Add the Price ID for the existing $7 one-time price (it starts with price_). "
    "Dealer Fee Audit does not create Stripe products or prices."
)

UNLOCK_TOKEN_SETUP_ERROR = (
    "Setup needed: DEALERFEE_UNLOCK_RECORD_TOKEN is missing. "
    "Paid unlocks cannot be recorded until that secret matches the digest in private.dealer_fee_unlock_gate. "
    "This app does not put the token in the repository."
)


class PriceNotConfigured(ValueError):
    """Raised when checkout is asked to start without STRIPE_PRICE_ID_DEALERFEE."""


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


def session_price_ids(session) -> list[str]:
    """Price ids on expanded line items, in order. Metadata is separate."""
    found = []
    line_items = _get(session, "line_items")
    data = _get(line_items, "data") if line_items is not None else None
    if not isinstance(data, list):
        return found
    for item in data:
        price = _get(item, "price")
        if isinstance(price, str) and price:
            found.append(price)
            continue
        price_id = _get(price, "id") if price is not None else None
        if price_id:
            found.append(str(price_id))
    return found


def price_matches(session, expected_price_id: str | None) -> bool:
    """True only when the session's price is the configured Price ID.

    Expanded line items win. A metadata price that disagrees with them is a mismatch.
    A session with no price at all does not match.
    """
    if not expected_price_id:
        return False
    expected = str(expected_price_id)
    metadata = _get(session, "metadata") or {}
    meta_price = str(_get(metadata, "price_id") or "")
    line_prices = session_price_ids(session)
    if line_prices:
        if expected not in line_prices:
            return False
        if meta_price and meta_price != expected:
            return False
        return True
    return meta_price == expected


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
    A Retirement Audit session (no dealer_fee_audit product) is rejected.
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
    if not price_matches(session, expected_price_id):
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


def _token_matches(token, configured_token) -> bool:
    if not isinstance(token, str) or not isinstance(configured_token, str):
        return False
    if len(token) < 16 or len(configured_token) < 16:
        return False
    return hmac.compare_digest(token, configured_token)


def unlock_record_decision(
    *,
    caller_id: str | None,
    session_id: str | None,
    token,
    configured_token,
    existing_rows: list[dict] | None,
) -> dict:
    """Same rules as public.record_dealer_fee_unlock, without trusting the caller for user_id.

    A wrong or missing token is a forged attempt and does not write.
    A Checkout Session id already stored for someone else does not write.
    The caller can only record a row for caller_id, which the database sets from auth.uid().
    """
    if not caller_id:
        return {"ok": False, "reason": "login_required", "write": False}
    if not _token_matches(token, configured_token):
        return {"ok": False, "reason": "forged", "write": False}
    if not session_id or not str(session_id).startswith("cs_") or len(str(session_id)) < 8:
        return {"ok": False, "reason": "invalid_session", "write": False}
    for row in existing_rows or []:
        if row.get("stripe_checkout_session_id") == session_id and str(row.get("user_id")) != str(caller_id):
            return {"ok": False, "reason": "session_reused", "write": False}
    for row in existing_rows or []:
        if str(row.get("user_id")) == str(caller_id) and row.get("product") == PRODUCT:
            return {"ok": True, "reason": "already_unlocked", "write": False}
    return {"ok": True, "reason": "recorded", "write": True}


def commit_unlock(
    *,
    session,
    user_id: str | None,
    email: str | None,
    existing_rows: list[dict] | None,
    now_iso: str,
    expected_price_id: str | None,
    token,
    configured_token,
) -> dict:
    """Stripe check first. The token check runs only after that passes.

    An unpaid session never reaches the write, even with the recording token.
    """
    own = None
    for row in existing_rows or []:
        if user_id and str(row.get("user_id")) == str(user_id) and row.get("product") == PRODUCT:
            own = row
            break
    decision = fulfillment_decision(session, user_id, email, own, now_iso, expected_price_id)
    if decision["reason"] != "unlocked" or not decision.get("update"):
        return {"ok": decision["ok"], "reason": decision["reason"], "recorded": False, "update": None}
    record = unlock_record_decision(
        caller_id=user_id,
        session_id=decision["update"]["stripe_checkout_session_id"],
        token=token,
        configured_token=configured_token,
        existing_rows=existing_rows,
    )
    if not record["ok"] or not record["write"]:
        return {"ok": record["ok"], "reason": record["reason"], "recorded": False, "update": None}
    return {"ok": True, "reason": "recorded", "recorded": True, "update": decision["update"]}
