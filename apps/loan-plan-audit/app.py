"""Loan Plan Audit. Streamlit entrypoint: apps/loan-plan-audit/app.py."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from demo import demo_active, read_secret, use_fake_supabase, FakeSupabase
from interface import Ctx, run

st.set_page_config(page_title="Loan Plan Audit", page_icon="🧮", layout="wide")

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
PRICE_ID = read_secret(_secrets, "STRIPE_PRICE_ID_LOANAUDIT")
OPENAI_API_KEY = read_secret(_secrets, "OPENAI_API_KEY")
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

openai_client = None
if OPENAI_API_KEY:
    try:
        from openai import OpenAI

        openai_client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception:
        openai_client = None

run(
    Ctx(
        supabase=supabase,
        stripe=stripe,
        price_id=PRICE_ID or None,
        app_url=APP_URL,
        local_sandbox=LOCAL_SANDBOX,
        openai_client=openai_client,
    )
)
