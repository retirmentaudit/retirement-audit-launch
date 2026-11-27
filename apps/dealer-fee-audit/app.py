"""Dealer Fee Audit. Streamlit entrypoint: apps/dealer-fee-audit/app.py."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from demo import DEMO_UNLOCK_TOKEN, FakeSupabase, demo_active, read_secret, use_fake_supabase
from interface import Ctx, run

st.set_page_config(page_title="Dealer Fee Audit", page_icon="🚗", layout="wide")

REQUIRED = ("SUPABASE_URL", "SUPABASE_KEY", "STRIPE_SECRET_KEY", "APP_URL")

try:
    _secrets = st.secrets
except Exception:
    _secrets = None

_missing = [key for key in REQUIRED if not read_secret(_secrets, key)]
if _missing:
    st.error("Missing required secrets in secrets.toml: " + ", ".join(_missing))
    st.stop()

APP_URL = str(read_secret(_secrets, "APP_URL")).rstrip("/")
STRIPE_SECRET_KEY = read_secret(_secrets, "STRIPE_SECRET_KEY")
SUPABASE_URL = read_secret(_secrets, "SUPABASE_URL")
PRICE_ID = read_secret(_secrets, "STRIPE_PRICE_ID_DEALERFEE")
UNLOCK_RECORD_TOKEN = read_secret(_secrets, "DEALERFEE_UNLOCK_RECORD_TOKEN")
LOCAL_DEMO = demo_active(STRIPE_SECRET_KEY)

if LOCAL_DEMO and use_fake_supabase(SUPABASE_URL):
    if "_demo_db" not in st.session_state:
        st.session_state["_demo_db"] = {}
    supabase = FakeSupabase(st.session_state["_demo_db"])
else:
    from supabase import create_client

    supabase = create_client(SUPABASE_URL, read_secret(_secrets, "SUPABASE_KEY"))

import stripe

stripe.api_key = STRIPE_SECRET_KEY
LOCAL_SANDBOX = LOCAL_DEMO and isinstance(supabase, FakeSupabase)
if LOCAL_SANDBOX and not UNLOCK_RECORD_TOKEN:
    UNLOCK_RECORD_TOKEN = DEMO_UNLOCK_TOKEN

run(
    Ctx(
        supabase=supabase,
        stripe=stripe,
        price_id=PRICE_ID or None,
        app_url=APP_URL,
        local_sandbox=LOCAL_SANDBOX,
        unlock_token=UNLOCK_RECORD_TOKEN or None,
    )
)
