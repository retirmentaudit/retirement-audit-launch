"""Local-only stubs so screenshots can run without Stripe or Supabase.

Turn it on with LOAN_PLAN_AUDIT_LOCAL_DEMO=1. It refuses to run when the Stripe
secret is a live key. Do not set the variable on Streamlit Cloud.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

DEMO_USER_ID = "demo-local-user"
DEMO_EMAIL = "demo@example.com"
PAID_DEMO_SESSION_ID = "cs_demo_paid"
DEMO_UNLOCK_TOKEN = "local-demo-unlock-token"

_PLACEHOLDERS = {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_KEY": "local-demo-not-a-key",
    "STRIPE_SECRET_KEY": "sk_test_local_demo_not_a_key",
    "STRIPE_PRICE_ID_LOANAUDIT": "price_local_demo_loanaudit",
    "APP_URL": "http://localhost:8501",
}


def demo_requested() -> bool:
    return os.environ.get("LOAN_PLAN_AUDIT_LOCAL_DEMO") == "1"


def read_secret(secrets, name: str):
    try:
        if secrets is not None and name in secrets and secrets[name]:
            return secrets[name]
    except Exception:
        pass
    if demo_requested():
        return _PLACEHOLDERS.get(name)
    return None


def demo_active(stripe_secret_key: str | None) -> bool:
    if not demo_requested():
        return False
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

    def select(self, *_args, **_kwargs):
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

    def order(self, *_args, **_kwargs):
        return self

    def delete(self):
        self.op = "delete"
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
        if self.op == "delete":
            self.store[self.table] = [row for row in rows if row not in matched]
            return _Result([dict(row) for row in matched])
        return _Result([dict(row) for row in matched])


class FakeSupabase:
    """In-memory stand-in. It never opens a network connection."""

    def __init__(self, store=None):
        self.store = store if store is not None else {}
        self.auth = self._Auth()

    def table(self, name: str):
        return _Query(self.store, name)

    class _Auth:
        def get_user(self):
            return None

        def sign_out(self):
            return None

        def set_session(self, _access, _refresh):
            return None

        def sign_in_with_password(self, _credentials):
            raise RuntimeError("Local demo does not contact Supabase.")

        def sign_up(self, _credentials):
            raise RuntimeError("Local demo does not contact Supabase.")


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
    paid = session_id == PAID_DEMO_SESSION_ID
    return {
        "id": session_id,
        "payment_status": "paid" if paid else "unpaid",
        "mode": "payment",
        "client_reference_id": user_id or DEMO_USER_ID,
        "customer_email": email or DEMO_EMAIL,
        "customer": "cus_demo_local" if paid else None,
        "metadata": {
            "user_id": user_id or DEMO_USER_ID,
            "product": "loan_plan_audit",
            "price_id": _PLACEHOLDERS["STRIPE_PRICE_ID_LOANAUDIT"],
            "purchase": "one_time",
        },
    }


def query_param(query_params, name: str):
    if query_params is None:
        return None
    try:
        value = query_params.get(name)
    except Exception:
        return None
    if isinstance(value, list):
        return value[0] if value else None
    return value
