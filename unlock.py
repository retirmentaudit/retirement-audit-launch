"""Paid-status and one-time Checkout rules.

These functions do not call Stripe or Supabase. The app passes in a Checkout
Session (or a plain dict with the same fields) and the profile row it already
loaded, then writes the returned update itself.

An active or trialing subscription still counts as paid. New purchases use
mode="payment" and a one-time price.
"""

from __future__ import annotations

FREE_AI_QUESTION_LIMIT = 3
PAID_AI_QUESTION_LIMIT = 50
ACTIVE_SUBSCRIPTION_STATUSES = frozenset({"active", "trialing"})


def _get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def profile_is_paid(profile: dict | None) -> bool:
    """True for a one-time unlock and for an existing active subscription.

    `is_paid_user` is the flag the app writes after a $5 payment. Subscription
    status is checked too so a subscriber stays unlocked even if that flag was
    never set, which is how the old subscription path recorded some rows.
    """
    if not profile:
        return False
    status = str(profile.get("subscription_status") or "").strip().lower()
    if status in ACTIVE_SUBSCRIPTION_STATUSES:
        return True
    return bool(profile.get("is_paid_user"))


def ai_question_limit(is_paid: bool) -> int:
    return PAID_AI_QUESTION_LIMIT if is_paid else FREE_AI_QUESTION_LIMIT


def merged_question_count(session_count, profile_count) -> int:
    """Keep the higher count so a refresh cannot hand the free questions back."""
    return max(int(session_count or 0), int(profile_count or 0))


def user_can_ask(used, is_paid: bool, logged_in: bool) -> tuple[bool, str | None]:
    """Return (allowed, reason).

    reason is None when another question is allowed. Otherwise it is "limit"
    (paid cap reached), "login" (anonymous free cap), or "paywall".
    """
    if int(used or 0) < ai_question_limit(is_paid):
        return True, None
    if is_paid:
        return False, "limit"
    if not logged_in:
        return False, "login"
    return False, "paywall"


def onetime_checkout_params(user_id: str, email: str | None, price_id: str, app_url: str) -> dict:
    """Arguments for stripe.checkout.Session.create in payment mode.

    The success URL must contain the literal {CHECKOUT_SESSION_ID} placeholder.
    Stripe replaces it when it redirects the buyer back.
    """
    if not user_id:
        raise ValueError("User must be logged in before checkout.")
    if not price_id:
        raise ValueError("STRIPE_PRICE_ID_ONETIME is not set.")
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

    client_reference_id is the check when Stripe sent one. A matching email
    must not override a reference id for a different user, or someone could
    open another person's paid session while logged into their own account.
    Email is the fallback when the reference id is missing. metadata.user_id
    is a last resort because checkout also stores it.
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


def fulfillment_decision(session, user_id: str | None, email: str | None, profile: dict | None, now_iso: str) -> dict:
    """Decide whether a returned Checkout Session unlocks this profile.

    The result is safe to apply more than once. A session id that is already
    stored on a paid profile produces no further update.
    """
    if not user_id:
        return {"ok": False, "reason": "login_required", "update": None}

    profile = profile or {}
    session_id = str(_get(session, "id") or "")
    if (
        session_id
        and profile.get("stripe_checkout_session_id") == session_id
        and profile_is_paid(profile)
    ):
        return {"ok": True, "reason": "already_unlocked", "update": None}

    if str(_get(session, "payment_status") or "") != "paid":
        return {"ok": False, "reason": "unpaid", "update": None}
    if str(_get(session, "mode") or "") != "payment":
        return {"ok": False, "reason": "not_one_time", "update": None}
    if not session_matches_user(session, user_id, email):
        return {"ok": False, "reason": "user_mismatch", "update": None}

    update = {
        "is_paid_user": True,
        "paid_via": "one_time",
        "stripe_checkout_session_id": session_id,
    }
    status = str(profile.get("subscription_status") or "").strip().lower()
    # Leave an active subscription status alone. One-time unlock is not a cancellation.
    if status not in ACTIVE_SUBSCRIPTION_STATUSES:
        update["subscription_status"] = "one_time"
    if not profile.get("paid_at"):
        update["paid_at"] = now_iso
    customer = _get(session, "customer")
    if isinstance(customer, str) and customer:
        update["stripe_customer_id"] = customer
    return {"ok": True, "reason": "unlocked", "update": update}
