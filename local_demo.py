"""Local-only stubs so the app can be screenshotted without Stripe or Supabase.

Turn it on with RETIREMENT_AUDIT_LOCAL_DEMO=1. It does nothing unless that
variable is set, and it refuses to run when the Stripe secret is a live key.
Do not set the variable on Streamlit Cloud.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

DEMO_USER_ID = "demo-local-user"
DEMO_EMAIL = "demo@example.com"
PAID_DEMO_SESSION_ID = "cs_demo_paid"

_PLACEHOLDERS = {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_KEY": "local-demo-not-a-key",
    "STRIPE_SECRET_KEY": "sk_test_local_demo_not_a_key",
    "STRIPE_PRICE_ID_ONETIME": "price_local_demo_onetime",
    "APP_URL": "http://localhost:8501",
}


def demo_requested() -> bool:
    return os.environ.get("RETIREMENT_AUDIT_LOCAL_DEMO") == "1"


def read_secret(secrets, name: str):
    """Read one secret. Missing values become placeholders only in local demo mode."""
    try:
        if secrets is not None and name in secrets:
            value = secrets[name]
            if value:
                return value
    except Exception:
        pass
    if demo_requested():
        return _PLACEHOLDERS.get(name)
    return None


def demo_active(stripe_secret_key: str | None) -> bool:
    if not demo_requested():
        return False
    # A live key means this process is not a screenshot sandbox.
    return not str(stripe_secret_key or "").startswith("sk_live")


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, store: dict, table: str):
        self.store = store
        self.table = table
        self.payload = None
        self.filters = []
        self.op = "select"

    def select(self, *args, **kwargs):
        self.op = "select"
        return self

    def insert(self, payload):
        self.op = "insert"
        self.payload = dict(payload)
        return self

    def update(self, payload):
        self.op = "update"
        self.payload = dict(payload)
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def order(self, *args, **kwargs):
        return self

    def execute(self):
        rows = self.store.setdefault(self.table, [])
        if self.op == "insert":
            row = dict(self.payload or {})
            row.setdefault("id", f"row-{len(rows) + 1}")
            rows.append(row)
            return _Result([row])
        matched = [row for row in rows if all(row.get(key) == value for key, value in self.filters)]
        if self.op == "update":
            for row in matched:
                row.update(self.payload or {})
            return _Result([dict(row) for row in matched])
        return _Result([dict(row) for row in matched])


class FakeSupabase:
    """In-memory stand-in. It never opens a network connection."""

    def __init__(self):
        self.store = {}
        self.auth = self._Auth()

    def table(self, name: str):
        return _Query(self.store, name)

    class _Auth:
        def get_user(self):
            return None

        def sign_out(self):
            return None

        def set_session(self, access_token, refresh_token):
            return None

        def sign_in_with_password(self, credentials):
            raise RuntimeError("Local demo does not contact Supabase. Log in is unavailable in this mode.")

        def sign_up(self, credentials):
            raise RuntimeError("Local demo does not contact Supabase. Sign up is unavailable in this mode.")


def use_fake_supabase(url: str | None) -> bool:
    host = str(url or "")
    return "example.supabase.co" in host or host.startswith("http://127.0.0.1")


def demo_checkout_session(user_id: str, email: str | None):
    return SimpleNamespace(
        id="cs_demo_local",
        url="https://example.com/demo-checkout-not-stripe",
        client_reference_id=str(user_id),
        customer_email=email,
    )


def demo_retrieved_session(session_id: str, user_id: str | None, email: str | None) -> dict:
    """A fake Checkout Session. Only the known demo id is marked paid."""
    paid = session_id == PAID_DEMO_SESSION_ID
    return {
        "id": session_id,
        "payment_status": "paid" if paid else "unpaid",
        "mode": "payment",
        "client_reference_id": user_id or DEMO_USER_ID,
        "customer_email": email or DEMO_EMAIL,
        "customer": "cus_demo_local" if paid else None,
    }


def demo_identity(query_params) -> SimpleNamespace | None:
    kind = _param(query_params, "demo_user")
    subscriber = _param(query_params, "demo_subscriber")
    checkout = _param(query_params, "checkout")
    if kind in {"free", "paid"} or subscriber == "1" or checkout == "success":
        return SimpleNamespace(id=DEMO_USER_ID, email=DEMO_EMAIL)
    return None


def demo_profile_override(query_params) -> dict | None:
    """Profile fields a screenshot URL is allowed to set on the fake database."""
    used = _param(query_params, "demo_ai_used")
    questions = int(used) if used and used.isdigit() else None
    if _param(query_params, "demo_subscriber") == "1":
        payload = {
            "is_paid_user": True,
            "subscription_status": "active",
            "paid_via": "subscription",
        }
    elif _param(query_params, "demo_user") == "paid":
        payload = {
            "is_paid_user": True,
            "subscription_status": "one_time",
            "paid_via": "one_time",
        }
    elif _param(query_params, "demo_user") == "free":
        payload = {}
    else:
        return None
    if questions is not None:
        payload["ai_questions_used"] = questions
    return payload


def demo_sample_inputs() -> dict:
    """A filled-in plan so a screenshot can show a real score without clicking the wizard."""
    return {
        "started": True,
        "planning_for": "Just me",
        "spouse1_age": 35,
        "retirement_age": 65,
        "spouse1_use_traditional_401k": True,
        "spouse1_trad_401k_bal": 50000.0,
        "spouse1_trad_401k_cont": 6000.0,
        "spouse1_trad_401k_match": 3000.0,
        "spouse1_trad_401k_rate": 7.0,
        "avg_earn_sp1": 60000,
        "use_manual_ss": True,
        "ss_start_sp1": 67,
        "ss_ann_sp1": 28150,
    }


def _param(query_params, name: str):
    if query_params is None:
        return None
    try:
        value = query_params.get(name)
    except Exception:
        return None
    if isinstance(value, list):
        return value[0] if value else None
    return value
