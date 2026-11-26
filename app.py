import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, timezone
from openai import OpenAI
from supabase import create_client, Client
import stripe
import json
import io

from action_plan import EDUCATIONAL_NOTE, generate_action_plan, plan_fingerprint
from local_demo import (
    DEMO_EMAIL,
    DEMO_USER_ID,
    FakeSupabase,
    demo_active,
    demo_checkout_session,
    demo_identity,
    demo_profile_override,
    demo_retrieved_session,
    demo_sample_inputs,
    read_secret,
    use_fake_supabase,
)
from pdf_report import build_audit_pdf
from unlock import (
    ACTIVE_SUBSCRIPTION_STATUSES,
    FREE_AI_QUESTION_LIMIT,
    ai_question_limit,
    fulfillment_decision,
    merged_question_count,
    onetime_checkout_params,
    profile_is_paid,
    user_can_ask,
)

# ==========================================================
# PAGE CONFIG
# ==========================================================
st.set_page_config(page_title="Retirement Audit", page_icon="📈", layout="wide")

# ==========================================================
# REQUIRED SECRETS
# ==========================================================
REQUIRED_SECRETS = [
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "STRIPE_SECRET_KEY",
    "STRIPE_PRICE_ID",
    "APP_URL",
]

# STRIPE_PRICE_ID_ONETIME is the new $5 price. It is not in REQUIRED_SECRETS so a
# missing value cannot take the free audit offline. Checkout refuses to start
# until the secret is set. STRIPE_PRICE_ID stays required because existing
# deploys already have it; active subscribers are still treated as paid.
_secrets = None
try:
    _secrets = st.secrets
except Exception:
    _secrets = None

missing_secrets = [key for key in REQUIRED_SECRETS if not read_secret(_secrets, key)]
if missing_secrets:
    st.error("Missing required secrets in secrets.toml: " + ", ".join(missing_secrets))
    st.stop()

APP_URL = str(read_secret(_secrets, "APP_URL")).rstrip("/")
STRIPE_PRICE_ID = read_secret(_secrets, "STRIPE_PRICE_ID")
STRIPE_PRICE_ID_ONETIME = read_secret(_secrets, "STRIPE_PRICE_ID_ONETIME")
STRIPE_SECRET_KEY = read_secret(_secrets, "STRIPE_SECRET_KEY")
LOCAL_DEMO = demo_active(STRIPE_SECRET_KEY)
OPENAI_API_KEY = read_secret(_secrets, "OPENAI_API_KEY")
OPENAI_ENABLED = bool(OPENAI_API_KEY)

# ==========================================================
# CLIENTS
# ==========================================================
SUPABASE_URL = read_secret(_secrets, "SUPABASE_URL")
if LOCAL_DEMO and use_fake_supabase(SUPABASE_URL):
    supabase = FakeSupabase()
else:
    supabase: Client = create_client(SUPABASE_URL, read_secret(_secrets, "SUPABASE_KEY"))
stripe.api_key = STRIPE_SECRET_KEY
# Query-param login and stubbed Checkout exist only with the in-memory client.
# A real Supabase URL never takes that path, even if the demo variable is set.
LOCAL_SANDBOX = LOCAL_DEMO and isinstance(supabase, FakeSupabase)

openai_client = None
if OPENAI_ENABLED:
    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception:
        OPENAI_ENABLED = False
        openai_client = None

UNLOCK_TITLE = "Unlock your full Retirement Audit — $5 once"
UNLOCK_BODY = (
    "Get a personalized action plan (what to change first, how much to save, and a Social Security claiming note), "
    "a PDF you can keep, 50 AI questions on your numbers, and saved access anytime you come back. No subscription."
)
UNLOCK_BUTTON = "Unlock my full audit — $5"

# ==========================================================
# STYLING
# ==========================================================
st.markdown(
    """
    <style>
    .stApp {
        background: radial-gradient(circle at top left, #162033 0, #0e1117 35%, #090b10 100%);
        color: #f8fafc;
    }
    /* Light text only on the dark app canvas. Widget surfaces set their own colors below
       so alerts and buttons stay readable in both the light and dark Streamlit themes. */
    [data-testid="stMarkdownContainer"] *,
    [data-testid="stHeading"],
    [data-testid="stHeading"] *,
    [data-testid="stWidgetLabel"],
    [data-testid="stWidgetLabel"] *,
    [data-testid="stMetricLabel"],
    [data-testid="stMetricLabel"] *,
    [data-testid="stMetricValue"],
    [data-testid="stMetricValue"] *,
    [data-testid="stExpander"] details summary,
    [data-testid="stExpander"] details summary *,
    [data-testid="stRadio"] label,
    [data-testid="stCheckbox"] label,
    [data-testid="stTab"] p,
    button[data-baseweb="tab"],
    button[data-baseweb="tab"] p {
        color: #f8fafc !important;
    }
    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] * {
        color: #d5deea !important;
    }
    [data-testid="stSidebar"] { background-color: #0b0f17; }
    .hero-card {
        padding: 34px; border-radius: 24px;
        background: linear-gradient(135deg, rgba(41, 98, 255, .22), rgba(16, 185, 129, .12));
        border: 1px solid rgba(255,255,255,.13);
        box-shadow: 0 18px 50px rgba(0,0,0,.35);
        margin-bottom: 20px;
    }
    .hero-title { font-size: 3rem; line-height: 1.05; font-weight: 800; margin-bottom: 14px; }
    [data-testid="stMarkdownContainer"] .hero-sub { font-size: 1.22rem; color: #d7deea !important; max-width: 820px; }
    .pill { display: inline-block; padding: 7px 12px; border-radius: 999px; background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.14); margin-right: 8px; margin-bottom: 8px; font-size: .92rem; }
    .step-card, .summary-card, .upgrade-card, .unlock-card {
        padding: 22px; border-radius: 18px; background: rgba(21,27,35,.92);
        border: 1px solid rgba(255,255,255,.12); margin-bottom: 16px;
    }
    .unlock-card { border-color: rgba(251, 191, 36, .55); }
    .metric-card {
        padding: 20px; border-radius: 18px; background: rgba(255,255,255,.06);
        border: 1px solid rgba(255,255,255,.11); height: 100%;
    }
    .big-metric { font-size: 2rem; font-weight: 800; margin-top: 6px; }
    [data-testid="stMarkdownContainer"] .muted { color: #b9c2d3 !important; }
    [data-testid="stMarkdownContainer"] .green { color: #34d399 !important; }
    [data-testid="stMarkdownContainer"] .yellow { color: #fbbf24 !important; }
    [data-testid="stMarkdownContainer"] .red { color: #fb7185 !important; }
    [data-testid="stMarkdownContainer"] .small-note { font-size: .9rem; color: #d5deea !important; }
    div.stButton > button, div.stLinkButton > a {
        border-radius: 12px !important; font-weight: 700 !important; min-height: 46px;
    }
    /* Secondary buttons keep a light face and dark label in either theme. */
    div.stButton > button[kind="secondary"],
    div.stButton > button[data-testid="stBaseButton-secondary"] {
        background-color: #f8fafc !important;
        color: #111827 !important;
        border: 1px solid #cbd5e1 !important;
    }
    div.stButton > button[kind="secondary"] *,
    div.stButton > button[data-testid="stBaseButton-secondary"] * {
        color: #111827 !important;
    }
    div.stButton > button[kind="primary"],
    div.stButton > button[data-testid="stBaseButton-primary"] {
        color: #ffffff !important;
    }
    div.stButton > button[kind="primary"] *,
    div.stButton > button[data-testid="stBaseButton-primary"] * {
        color: #ffffff !important;
    }
    div.stLinkButton > a[data-testid="stBaseLinkButton-secondary"],
    div.stLinkButton > a[data-testid="stBaseLinkButton-secondary"] * {
        background-color: #f8fafc !important;
        color: #111827 !important;
    }
    div.stLinkButton > a[data-testid="stBaseLinkButton-primary"],
    div.stLinkButton > a[data-testid="stBaseLinkButton-primary"] * {
        color: #ffffff !important;
    }
    /* Alerts keep a light surface and dark text in both Streamlit themes.
       The inner container carries the theme background, so set that too. */
    div[data-testid="stAlert"] * {
        color: #0f172a !important;
    }
    div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) {
        background-color: #edf5ff !important;
        border: 1px solid #bfdbfe !important;
    }
    div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {
        background-color: #fff1f2 !important;
        border: 1px solid #fecdd3 !important;
    }
    div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) {
        background-color: #ecfdf5 !important;
        border: 1px solid #a7f3d0 !important;
    }
    div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {
        background-color: #fffbeb !important;
        border: 1px solid #fde68a !important;
    }
    /* Community Cloud injects Fork and the GitHub icon as toolbar actions.
       toolbarMode=minimal still shows host toolbar items, so hide that cluster. */
    [data-testid="stToolbarActions"] {
        display: none !important;
    }
    /* The creator-name script should not take up a row. */
    [data-testid="stElementContainer"]:has(#creator-name-fix) {
        height: 0 !important;
        min-height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

def install_creator_name_fix():
    """Correct the visible Community Cloud creator name without touching its URL.

    The profile popup is rendered by Streamlit Community Cloud in the parent page,
    outside this app's CSS. The link still points at the existing profile.
    """
    st.html(
        """
        <script id="creator-name-fix">
        (function () {
          var root = window.parent || window;
          if (root.__retirementAuditCreatorFix) return;
          root.__retirementAuditCreatorFix = true;
          var misspelled = "retirmentaudit";
          var corrected = "retirementaudit";
          function documents() {
            var found = [];
            try { if (window.parent && window.parent.document) found.push(window.parent.document); } catch (e) {}
            try {
              if (window.parent && window.parent.parent && window.parent.parent.document) {
                found.push(window.parent.parent.document);
              }
            } catch (e) {}
            return found;
          }
          function fixDoc(doc) {
            if (!doc || !doc.body) return;
            var walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_TEXT, null);
            var node;
            var pending = [];
            while ((node = walker.nextNode())) {
              if (node.nodeValue && node.nodeValue.indexOf(misspelled) !== -1) pending.push(node);
            }
            pending.forEach(function (textNode) {
              textNode.nodeValue = textNode.nodeValue.split(misspelled).join(corrected);
            });
          }
          function run() { documents().forEach(fixDoc); }
          run();
          documents().forEach(function (doc) {
            try {
              new MutationObserver(run).observe(doc.body, {subtree: true, childList: true, characterData: true});
            } catch (e) {}
          });
        })();
        </script>
        """,
        unsafe_allow_javascript=True,
    )

def render_creator_footer():
    st.markdown(
        "<p class='small-note'>Created by retirementaudit</p>",
        unsafe_allow_html=True,
    )

install_creator_name_fix()

# ==========================================================
# SESSION DEFAULTS
# ==========================================================
DEFAULTS = {
    "started": False,
    "wizard_step": 1,
    "planning_for": "Me + spouse",
    "ai_question_count": 0,
    "ai_chat_history": [],
    "ai_limit": FREE_AI_QUESTION_LIMIT,
    "user_logged_in": False,
    "user_email": None,
    "user_id": None,
    "is_paid_user": False,
    "paid_via": None,
    "subscription_status": "free",
    "_checkout_url": None,
    "_checkout_user_id": None,
    "_scenario_to_apply": None,
    "_scenario_loaded_message": None,
    "scenario_name": "My Retirement Plan",
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

SCENARIO_KEYS = [
    "started", "wizard_step", "planning_for", "scenario_name", "retirement_age", "spouse1_age", "spouse2_age",
    "spouse1_use_traditional_401k", "spouse1_trad_401k_bal", "spouse1_trad_401k_cont", "spouse1_trad_401k_match", "spouse1_trad_401k_rate",
    "spouse1_use_roth_401k", "spouse1_roth_401k_bal", "spouse1_roth_401k_cont", "spouse1_roth_401k_rate",
    "spouse1_use_traditional_ira", "spouse1_trad_ira_bal", "spouse1_trad_ira_cont", "spouse1_trad_ira_rate",
    "spouse1_use_roth_ira", "spouse1_roth_bal", "spouse1_roth_cont", "spouse1_roth_rate",
    "spouse1_use_hsa", "spouse1_hsa_coverage", "spouse1_hsa_bal", "spouse1_hsa_cont", "spouse1_hsa_rate",
    "spouse1_use_brokerage", "spouse1_brok_bal", "spouse1_brok_cont", "spouse1_brok_rate",
    "spouse2_use_traditional_401k", "spouse2_trad_401k_bal", "spouse2_trad_401k_cont", "spouse2_trad_401k_match", "spouse2_trad_401k_rate",
    "spouse2_use_roth_401k", "spouse2_roth_401k_bal", "spouse2_roth_401k_cont", "spouse2_roth_401k_rate",
    "spouse2_use_traditional_ira", "spouse2_trad_ira_bal", "spouse2_trad_ira_cont", "spouse2_trad_ira_rate",
    "spouse2_use_roth_ira", "spouse2_roth_bal", "spouse2_roth_cont", "spouse2_roth_rate",
    "spouse2_use_hsa", "spouse2_hsa_coverage", "spouse2_hsa_bal", "spouse2_hsa_cont", "spouse2_hsa_rate",
    "spouse2_use_brokerage", "spouse2_brok_bal", "spouse2_brok_cont", "spouse2_brok_rate",
    "avg_earn_sp1", "avg_earn_sp2", "use_manual_ss", "ss_start_sp1", "ss_start_sp2", "ss_ann_sp1", "ss_ann_sp2",
    "use_pension", "pen_sp1", "pen_sp2", "pen_cola_sp1", "pen_cola_sp2",
    "use_home_equity", "home_value", "mortgage_balance", "home_appreciation_pct", "include_home",
    "use_mortgage_calc", "mort_principal", "mort_rate_pct", "mort_years", "monthly_payment", "extra_monthly",
    "wd_rate_pct", "post_growth_pct",
]


# ==========================================================
# PERSIST WIZARD INPUTS ACROSS STEPS
# ==========================================================
# Streamlit clears widget state when a widget is not rendered on the current page.
# Because this app uses a multi-step wizard, we intentionally keep these values
# alive so Step 1/2/3 inputs are still available when the user reaches results.
DEFAULT_INPUT_VALUES = {
    "planning_for": "Me + spouse",
    "scenario_name": "My Retirement Plan",
    "retirement_age": 65,
    "spouse1_age": 35,
    "spouse2_age": 35,
    "avg_earn_sp1": 0,
    "avg_earn_sp2": 0,
    "use_manual_ss": False,
    "ss_start_sp1": 67,
    "ss_start_sp2": 67,
    "ss_ann_sp1": 0,
    "ss_ann_sp2": 0,
    "use_pension": False,
    "pen_sp1": 0,
    "pen_sp2": 0,
    "pen_cola_sp1": 2.0,
    "pen_cola_sp2": 2.0,
    "use_home_equity": False,
    "home_value": 0.0,
    "mortgage_balance": 0.0,
    "home_appreciation_pct": 3.0,
    "include_home": True,
    "use_mortgage_calc": False,
    "mort_principal": 0.0,
    "mort_rate_pct": 6.5,
    "mort_years": 30,
    "monthly_payment": 1500.0,
    "extra_monthly": 0.0,
    "wd_rate_pct": 4.5,
    "post_growth_pct": 6.0,
}

for spouse in ["spouse1", "spouse2"]:
    DEFAULT_INPUT_VALUES.update({
        f"{spouse}_use_traditional_401k": False,
        f"{spouse}_trad_401k_bal": 0.0,
        f"{spouse}_trad_401k_cont": 0.0,
        f"{spouse}_trad_401k_match": 0.0,
        f"{spouse}_trad_401k_rate": 7.0,
        f"{spouse}_use_roth_401k": False,
        f"{spouse}_roth_401k_bal": 0.0,
        f"{spouse}_roth_401k_cont": 0.0,
        f"{spouse}_roth_401k_rate": 7.0,
        f"{spouse}_use_traditional_ira": False,
        f"{spouse}_trad_ira_bal": 0.0,
        f"{spouse}_trad_ira_cont": 0.0,
        f"{spouse}_trad_ira_rate": 7.0,
        f"{spouse}_use_roth_ira": False,
        f"{spouse}_roth_bal": 0.0,
        f"{spouse}_roth_cont": 0.0,
        f"{spouse}_roth_rate": 7.0,
        f"{spouse}_use_hsa": False,
        f"{spouse}_hsa_coverage": "Family",
        f"{spouse}_hsa_bal": 0.0,
        f"{spouse}_hsa_cont": 0.0,
        f"{spouse}_hsa_rate": 6.0,
        f"{spouse}_use_brokerage": False,
        f"{spouse}_brok_bal": 0.0,
        f"{spouse}_brok_cont": 0.0,
        f"{spouse}_brok_rate": 6.0,
    })

for key, default_value in DEFAULT_INPUT_VALUES.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

# This line is what prevents Streamlit from deleting hidden-step widget values.
for key in SCENARIO_KEYS:
    if key in st.session_state:
        st.session_state[key] = st.session_state[key]

# ==========================================================
# CALC HELPERS
# ==========================================================
def get_ira_limits(age: int):
    base_limit = 7500
    catch_up = 1100 if age >= 50 else 0
    return base_limit, catch_up, base_limit + catch_up

def get_401k_limits(age: int):
    base_limit = 24500
    if 60 <= age <= 63:
        catch_up = 11250
    elif age >= 50:
        catch_up = 8000
    else:
        catch_up = 0
    return base_limit, catch_up, base_limit + catch_up

def get_hsa_limit(age: int, coverage_type: str):
    base_limit = 4400 if coverage_type == "Self-only" else 8750
    catch_up = 1000 if age >= 55 else 0
    return base_limit, catch_up, base_limit + catch_up

def estimate_ss_pia(avg_annual_earnings: float):
    if avg_annual_earnings <= 0:
        return 0
    aime = avg_annual_earnings / 12
    bend1 = 1286
    bend2 = 7749
    pia_monthly = min(aime, bend1) * 0.90 + max(0, min(aime - bend1, bend2 - bend1)) * 0.32 + max(0, aime - bend2) * 0.15
    pia_monthly = np.floor(pia_monthly * 10) / 10
    return round(pia_monthly * 12)

def future_value(balance: float, annual_contrib: float, annual_rate: float, years: int):
    if years <= 0:
        return float(balance)
    if annual_rate == 0:
        return float(balance) + float(annual_contrib) * years
    return float(balance) * (1 + annual_rate) ** years + float(annual_contrib) * (((1 + annual_rate) ** years - 1) / annual_rate)

def amortization_schedule(principal: float, annual_rate: float, monthly_payment: float, extra_monthly: float = 0.0, max_months: int = 1200):
    principal = float(principal)
    if principal <= 0:
        return {"amortizes": True, "months": 0, "interest": 0.0, "balances": [0.0]}
    monthly_rate = float(annual_rate) / 12
    balance = principal
    total_interest = 0.0
    month = 0
    balances = [balance]
    while balance > 0.005 and month < max_months:
        interest = balance * monthly_rate
        actual_payment = min(float(monthly_payment) + float(extra_monthly), balance + interest)
        principal_payment = actual_payment - interest
        if principal_payment <= 0:
            return {"amortizes": False, "months": None, "interest": total_interest, "balances": balances}
        balance = max(balance - principal_payment, 0.0)
        total_interest += interest
        month += 1
        balances.append(balance)
    if month >= max_months and balance > 0.005:
        return {"amortizes": False, "months": None, "interest": total_interest, "balances": balances}
    return {"amortizes": True, "months": month, "interest": total_interest, "balances": balances}

def projected_mortgage_balance(schedule_balances, years_from_now: int):
    idx = int(years_from_now * 12)
    if not schedule_balances or idx >= len(schedule_balances):
        return 0.0
    return float(schedule_balances[idx])

def money(x):
    return f"${x:,.0f}"

def collect_app_state():
    data = {}
    for key in SCENARIO_KEYS:
        if key in st.session_state:
            value = st.session_state[key]
            if isinstance(value, (int, float, str, bool, list, dict)) or value is None:
                data[key] = value
    return data

def queue_scenario_for_load(saved_data: dict, scenario_name: str = None):
    st.session_state["_scenario_to_apply"] = saved_data.copy()
    st.session_state["_scenario_loaded_message"] = f"Plan loaded: {scenario_name}" if scenario_name else "Plan loaded."
    st.rerun()

def apply_queued_scenario_if_needed():
    saved_data = st.session_state.get("_scenario_to_apply")
    if not saved_data:
        return
    for key, value in saved_data.items():
        st.session_state[key] = value
    st.session_state["_scenario_to_apply"] = None

# ==========================================================
# AUTH / PROFILE HELPERS
# ==========================================================
def sign_up_user(email, password):
    try:
        return supabase.auth.sign_up({"email": email, "password": password}), None
    except Exception as e:
        return None, str(e)

def sign_in_user(email, password):
    try:
        return supabase.auth.sign_in_with_password({"email": email, "password": password}), None
    except Exception as e:
        return None, str(e)

def sign_out_user():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    for key in ["user_logged_in", "is_paid_user"]:
        st.session_state[key] = False
    for key in ["user_email", "user_id", "_checkout_url", "_checkout_user_id", "_sb_access_token", "_sb_refresh_token", "paid_via"]:
        st.session_state[key] = None
    st.session_state.subscription_status = "free"
    st.session_state.ai_question_count = 0
    st.session_state.ai_chat_history = []
    st.session_state.ai_limit = FREE_AI_QUESTION_LIMIT
    st.session_state._action_plan_cache = None

def remember_auth_session(auth_response):
    """Keep the Supabase session across reruns, including the return from Checkout.

    The client is created again on every run, so without this the JWT is gone
    when Stripe redirects back and the profile update cannot be authorized.
    """
    session = getattr(auth_response, "session", None)
    if session is None and isinstance(auth_response, dict):
        session = auth_response.get("session")
    if not session:
        return
    if isinstance(session, dict):
        access = session.get("access_token")
        refresh = session.get("refresh_token")
    else:
        access = getattr(session, "access_token", None)
        refresh = getattr(session, "refresh_token", None)
    if access and refresh:
        st.session_state["_sb_access_token"] = access
        st.session_state["_sb_refresh_token"] = refresh

def restore_auth_session():
    access = st.session_state.get("_sb_access_token")
    refresh = st.session_state.get("_sb_refresh_token")
    if not access or not refresh:
        return
    try:
        supabase.auth.set_session(access, refresh)
    except Exception:
        pass

def get_current_user():
    try:
        user_response = supabase.auth.get_user()
        if user_response and getattr(user_response, "user", None):
            return user_response.user
    except Exception:
        return None
    return None

def ensure_user_profile(user_id, email):
    try:
        existing = supabase.table("user_profiles").select("*").eq("user_id", user_id).execute()
        if existing.data:
            return existing.data[0], None
        inserted = supabase.table("user_profiles").insert({"user_id": user_id, "email": email, "is_paid_user": False, "subscription_status": "free"}).execute()
        if inserted.data:
            return inserted.data[0], None
        return None, "Could not create profile."
    except Exception as e:
        return None, str(e)

def get_user_profile(user_id):
    try:
        result = supabase.table("user_profiles").select("*").eq("user_id", user_id).execute()
        if result.data:
            return result.data[0], None
        return None, None
    except Exception as e:
        return None, str(e)

def apply_profile_to_session(profile: dict):
    paid = profile_is_paid(profile)
    st.session_state.is_paid_user = paid
    st.session_state.subscription_status = profile.get("subscription_status") or "free"
    st.session_state.paid_via = profile.get("paid_via")
    st.session_state.ai_limit = ai_question_limit(paid)
    if profile.get("ai_questions_used") is not None:
        merged = merged_question_count(st.session_state.ai_question_count, profile.get("ai_questions_used"))
        st.session_state.ai_question_count = merged
        stored = int(profile.get("ai_questions_used") or 0)
        if merged != stored and st.session_state.user_id:
            persist_ai_question_count(st.session_state.user_id, merged)

def refresh_paid_status():
    if not st.session_state.user_id:
        st.session_state.is_paid_user = False
        st.session_state.paid_via = None
        st.session_state.subscription_status = "free"
        st.session_state.ai_limit = FREE_AI_QUESTION_LIMIT
        return
    profile, error = get_user_profile(st.session_state.user_id)
    if error or not profile:
        st.session_state.is_paid_user = False
        st.session_state.paid_via = None
        st.session_state.subscription_status = "free"
        st.session_state.ai_limit = FREE_AI_QUESTION_LIMIT
        return
    apply_profile_to_session(profile)

def persist_ai_question_count(user_id: str, count: int):
    """Save the question count on the profile. Missing column is non-fatal."""
    try:
        supabase.table("user_profiles").update({"ai_questions_used": int(count)}).eq("user_id", user_id).execute()
        st.session_state["_ai_count_unsaved"] = False
        return None
    except Exception:
        st.session_state["_ai_count_unsaved"] = True
        return "unsaved"

def create_checkout_session(user_id: str, email: str | None = None):
    """Create a one-time Checkout Session. Active subscribers are not sent here."""
    params = onetime_checkout_params(user_id, email, STRIPE_PRICE_ID_ONETIME, APP_URL)
    if LOCAL_SANDBOX:
        # Screenshot mode must not create a live Checkout Session.
        return demo_checkout_session(user_id, email)
    return stripe.checkout.Session.create(**params)

def retrieve_checkout_session(session_id: str):
    if LOCAL_SANDBOX:
        return demo_retrieved_session(session_id, st.session_state.get("user_id"), st.session_state.get("user_email"))
    return stripe.checkout.Session.retrieve(session_id)

def create_portal_session(customer_id: str):
    if LOCAL_SANDBOX:
        raise RuntimeError("Billing portal is not available in local demo mode.")
    if not customer_id:
        raise ValueError("Missing Stripe customer ID.")
    session = stripe.billing_portal.Session.create(customer=customer_id, return_url=APP_URL)
    return session.url

def get_checkout_url():
    if not st.session_state.user_logged_in or not st.session_state.user_id or st.session_state.is_paid_user:
        return None
    if not STRIPE_PRICE_ID_ONETIME:
        raise ValueError("Add STRIPE_PRICE_ID_ONETIME to the app secrets before checkout can start.")
    if st.session_state.get("_checkout_url") and st.session_state.get("_checkout_user_id") == st.session_state.user_id:
        return st.session_state._checkout_url
    session = create_checkout_session(st.session_state.user_id, st.session_state.user_email)
    st.session_state._checkout_url = session.url
    st.session_state._checkout_user_id = st.session_state.user_id
    return session.url

def get_user_scenarios(user_id):
    try:
        result = supabase.table("user_scenarios").select("*").eq("user_id", user_id).order("updated_at", desc=True).execute()
        return result.data, None
    except Exception as e:
        return None, str(e)

def save_scenario_to_supabase(user_id, scenario_name, scenario_data):
    try:
        existing = supabase.table("user_scenarios").select("id").eq("user_id", user_id).eq("scenario_name", scenario_name).execute()
        payload = {"user_id": user_id, "scenario_name": scenario_name, "scenario_data": scenario_data}
        if existing.data:
            result = supabase.table("user_scenarios").update(payload).eq("id", existing.data[0]["id"]).execute()
        else:
            result = supabase.table("user_scenarios").insert(payload).execute()
        return result, None
    except Exception as e:
        return None, str(e)

# ==========================================================
# AI HELPERS
# ==========================================================
def format_ai_response(text: str):
    return (text or "").strip()

def get_real_ai_response(user_question, results):
    if not OPENAI_ENABLED or openai_client is None:
        raise RuntimeError("OPENAI_API_KEY is missing or invalid.")
    system_instructions = """
You are a helpful retirement planning assistant inside a retirement calculator.
Rules:
- Keep the answer concise and practical.
- Use the user's numbers from the app.
- Do not claim certainty.
- Do not present yourself as a licensed financial advisor.
- Do not give tax, legal, or regulated investment advice.
- Mention when assumptions seem aggressive.
- End with a short reminder to consult a qualified financial professional for major decisions.
"""
    user_context = f"""
Retirement age: {results['retirement_age']}
Projected investments at retirement: ${results['total_invest']:,.0f}
Projected home equity at retirement: ${results['home_proj_equity']:,.0f}
Projected total net worth at retirement: ${results['total_nw']:,.0f}
Withdrawal rate selected: {results['wd_rate_pct']:.1f}%
Expected annual portfolio growth in retirement: {results['post_growth_pct']:.1f}%
First-year withdrawal: ${results['annual_wd']:,.0f}
Portfolio depletion age estimate: {results['depletion_age_label']}
Annual Social Security total: ${results['ss_total']:,.0f}
Annual pension total: ${results['pension_total']:,.0f}
Retirement score: {results['score']}/100 - {results['score_label']}

User question:
{user_question}
"""
    if not results.get("score_ready", True):
        user_context += """
The user has not entered a balance or income amount. Do not present the retirement score as a real result. Tell them to enter at least one account balance, contribution, pension, home value, or earnings amount first.
"""
    response = openai_client.responses.create(model="gpt-4.1-mini", instructions=system_instructions, input=user_context)
    return format_ai_response(response.output_text)

def user_can_ask_ai():
    return user_can_ask(
        st.session_state.ai_question_count,
        bool(st.session_state.is_paid_user),
        bool(st.session_state.user_logged_in),
    )

def query_value(name: str):
    value = st.query_params.get(name)
    if isinstance(value, list):
        return value[0] if value else None
    return value

def render_auth_tabs(key_prefix: str):
    login_tab, signup_tab = st.tabs(["Log In", "Sign Up"])
    with login_tab:
        login_email = st.text_input("Login Email", key=f"{key_prefix}_login_email")
        login_password = st.text_input("Login Password", type="password", key=f"{key_prefix}_login_password")
        if st.button("Log In", use_container_width=True, key=f"{key_prefix}_login_button"):
            if not login_email or not login_password:
                st.error("Please enter both email and password.")
            else:
                response, error = sign_in_user(login_email, login_password)
                if error:
                    st.error(f"Login failed: {error}")
                else:
                    user = response.user
                    remember_auth_session(response)
                    st.session_state.user_logged_in = True
                    st.session_state.user_email = user.email
                    st.session_state.user_id = user.id
                    ensure_user_profile(user.id, user.email)
                    refresh_paid_status()
                    st.rerun()
    with signup_tab:
        signup_email = st.text_input("Sign Up Email", key=f"{key_prefix}_signup_email")
        signup_password = st.text_input("Create Password", type="password", key=f"{key_prefix}_signup_password")
        if st.button("Create Account", use_container_width=True, key=f"{key_prefix}_signup_button"):
            if not signup_email or not signup_password:
                st.error("Please enter both email and password.")
            else:
                response, error = sign_up_user(signup_email, signup_password)
                if error:
                    st.error(f"Sign up failed: {error}")
                else:
                    try:
                        user = response.user
                        if user:
                            remember_auth_session(response)
                            ensure_user_profile(user.id, user.email)
                    except Exception:
                        pass
                    st.success("Account created. If email confirmation is enabled, confirm your email before logging in.")

def render_unlock_paywall(key_prefix: str):
    st.markdown(
        f"<div class='unlock-card'><h3>{UNLOCK_TITLE}</h3><p class='muted'>{UNLOCK_BODY}</p></div>",
        unsafe_allow_html=True,
    )
    if not st.session_state.user_logged_in:
        if st.button(UNLOCK_BUTTON, type="primary", use_container_width=True, key=f"{key_prefix}_unlock"):
            st.session_state[f"{key_prefix}_auth_open"] = True
        if st.session_state.get(f"{key_prefix}_auth_open"):
            st.caption("A free account is required before checkout. No subscription.")
            render_auth_tabs(key_prefix)
        return
    if LOCAL_SANDBOX:
        st.caption("Local demo: this button does not contact Stripe.")
    try:
        url = get_checkout_url()
        if url:
            st.link_button(UNLOCK_BUTTON, url, type="primary", use_container_width=True, key=f"{key_prefix}_checkout")
    except Exception as e:
        st.error(f"Checkout error: {e}")

def plan_inputs_from_state(results: dict) -> dict:
    manual_ss = bool(st.session_state.get("use_manual_ss"))
    contributions = 0.0
    for spouse_accounts in results.get("accounts", {}).values():
        for account in spouse_accounts.values():
            contributions += float(account.get("contrib") or 0) + float(account.get("employer_match") or 0)
    earnings = float(st.session_state.get("avg_earn_sp1") or 0)
    if results.get("include_spouse2"):
        earnings += float(st.session_state.get("avg_earn_sp2") or 0)
    return {
        "planning_for": results.get("planning_for"),
        "current_age": results.get("sp1_age"),
        "retirement_age": results.get("retirement_age"),
        "years_to_retirement": int(results.get("max_years") or 0),
        "total_invest": round(float(results.get("total_invest") or 0), 2),
        "annual_contributions": round(contributions, 2),
        "earnings": round(earnings, 2),
        "withdrawal_rate_pct": round(float(results.get("wd_rate_pct") or 0), 2),
        "growth_pct": round(float(results.get("post_growth_pct") or 0), 2),
        "annual_withdrawal": round(float(results.get("annual_wd") or 0), 2),
        "depletion_label": results.get("depletion_age_label"),
        "score": results.get("score"),
        "score_label": results.get("score_label"),
        "ss_annual": round(float(results.get("ss_total") or 0), 2),
        "pension_annual": round(float(results.get("pension_total") or 0), 2),
        "ss_claim_age": int(st.session_state.get("ss_start_sp1") or 67) if manual_ss else 67,
        "manual_ss": manual_ss,
    }

def figure_png(fig) -> bytes:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight")
    return buffer.getvalue()

def render_paid_action_plan(results: dict, chart_pngs: list[bytes]):
    inputs = plan_inputs_from_state(results)
    fingerprint = plan_fingerprint(inputs)
    cached = st.session_state.get("_action_plan_cache")
    if not cached or cached.get("fingerprint") != fingerprint:
        client = openai_client if OPENAI_ENABLED else None
        text, source = generate_action_plan(inputs, client)
        st.session_state["_action_plan_cache"] = {"fingerprint": fingerprint, "text": text, "source": source}
    plan = st.session_state["_action_plan_cache"]
    st.markdown("## Your action plan")
    if plan["source"] == "openai":
        st.caption(f"Written from your audit numbers with a fixed prompt. {EDUCATIONAL_NOTE} This does not guarantee returns.")
    else:
        st.caption(f"Built from your audit numbers with a fixed set of rules, because the AI writer is unavailable. {EDUCATIONAL_NOTE} This does not guarantee returns.")
    st.markdown(plan["text"])
    summary = {
        "score": results.get("score"),
        "score_label": results.get("score_label"),
        "retirement_age": results.get("retirement_age"),
        "total_invest": results.get("total_invest"),
        "total_nw": results.get("total_nw"),
        "annual_withdrawal": results.get("annual_wd"),
        "withdrawal_rate_pct": results.get("wd_rate_pct"),
        "growth_pct": results.get("post_growth_pct"),
        "depletion_label": results.get("depletion_age_label"),
        "ss_annual": results.get("ss_total"),
        "pension_annual": results.get("pension_total"),
    }
    generated_on = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pdf_bytes = build_audit_pdf(summary, plan["text"], chart_pngs, generated_on=generated_on)
    st.download_button(
        "Download my audit PDF",
        data=pdf_bytes,
        file_name="retirement-audit.pdf",
        mime="application/pdf",
        use_container_width=True,
        key="download_audit_pdf",
        type="primary",
    )

def handle_checkout_return():
    """Apply a returned Checkout Session once. Repeating the same id is a no-op."""
    checkout = query_value("checkout")
    if checkout == "cancel":
        st.info("Checkout was canceled. You can unlock the full audit whenever you are ready.")
        return
    if checkout != "success":
        return
    session_id = query_value("session_id")
    st.session_state._checkout_url = None
    st.session_state._checkout_user_id = None
    if not session_id:
        # Older subscription checkouts returned without a session id. Re-read the profile.
        refresh_paid_status()
        if st.session_state.is_paid_user:
            st.success("Payment confirmed. Your full audit is unlocked.")
        else:
            st.info("If you just finished a subscription checkout, refresh in a few seconds. New $5 payments include a checkout session id.")
        return
    if not st.session_state.user_logged_in or not st.session_state.user_id:
        st.warning("Log in with the same account you used at checkout and this page will unlock the audit.")
        render_auth_tabs("checkout_return")
        return
    done = st.session_state.setdefault("_fulfilled_checkout_sessions", [])
    if session_id in done and st.session_state.is_paid_user:
        st.success("Your full audit is already unlocked.")
        return
    try:
        session = retrieve_checkout_session(session_id)
    except Exception as e:
        st.error(f"Could not confirm the payment with Stripe: {e}")
        return
    profile, error = get_user_profile(st.session_state.user_id)
    if error:
        st.error("Could not load your profile to record the payment.")
        return
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    decision = fulfillment_decision(session, st.session_state.user_id, st.session_state.user_email, profile, now_iso)
    if decision["update"]:
        try:
            saved = supabase.table("user_profiles").update(decision["update"]).eq("user_id", st.session_state.user_id).execute()
        except Exception:
            st.error("Payment was confirmed, but saving it on your profile failed. Run the database migration, then refresh this page.")
            return
        if not getattr(saved, "data", None):
            st.error("Payment was confirmed, but your profile did not change. Run the database migration, then refresh this page.")
            return
        refresh_paid_status()
    if decision["reason"] in {"unlocked", "already_unlocked"}:
        if session_id not in done:
            done.append(session_id)
        if decision["reason"] == "already_unlocked":
            refresh_paid_status()
            st.success("Your full audit is already unlocked.")
        else:
            st.success("Payment confirmed. Your full audit is unlocked. This was a one-time $5 payment, not a subscription.")
        return
    if decision["reason"] == "unpaid":
        st.warning("Stripe has not marked this payment as paid yet. If you just paid, wait a moment and refresh.")
    elif decision["reason"] == "user_mismatch":
        st.error("This payment does not match the account you are logged in with. Log in with the same account you used at checkout.")
    elif decision["reason"] == "not_one_time":
        refresh_paid_status()
        if st.session_state.is_paid_user:
            st.success("Your existing subscription is still unlocked.")
        else:
            st.info("This checkout was not a one-time payment, so the $5 unlock was not applied.")
    else:
        st.info("Checkout returned, but the audit was not unlocked.")

# ==========================================================
# APP STATE RESTORE
# ==========================================================
apply_queued_scenario_if_needed()
restore_auth_session()
current_user = get_current_user()
if LOCAL_SANDBOX and current_user is None:
    current_user = demo_identity(st.query_params)
if current_user:
    st.session_state.user_logged_in = True
    st.session_state.user_email = getattr(current_user, "email", None) or DEMO_EMAIL
    st.session_state.user_id = getattr(current_user, "id", None) or DEMO_USER_ID
    ensure_user_profile(st.session_state.user_id, st.session_state.user_email)
    refresh_paid_status()
    if LOCAL_SANDBOX:
        override = demo_profile_override(st.query_params)
        if override:
            try:
                supabase.table("user_profiles").update(override).eq("user_id", st.session_state.user_id).execute()
            except Exception:
                pass
            refresh_paid_status()

handle_checkout_return()

if LOCAL_SANDBOX and query_value("demo_sample") == "1":
    for key, value in demo_sample_inputs().items():
        st.session_state[key] = value
    st.session_state.wizard_step = int(query_value("demo_step")) if query_value("demo_step") else 7
if LOCAL_SANDBOX and query_value("demo_ai_used") and str(query_value("demo_ai_used")).isdigit():
    st.session_state.ai_question_count = int(query_value("demo_ai_used"))

# ==========================================================
# INPUT HELPERS
# ==========================================================
def section_header(step, title, subtitle=""):
    st.markdown(f"<div class='step-card'><span class='pill'>Step {step} of 7</span><h2>{title}</h2><p class='muted'>{subtitle}</p></div>", unsafe_allow_html=True)
    st.progress(step / 7)

def next_back_buttons(next_label="Next", show_back=True):
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        if show_back and st.button("← Back", use_container_width=True):
            st.session_state.wizard_step = max(1, st.session_state.wizard_step - 1)
            st.rerun()
    with c2:
        if st.button(next_label, type="primary", use_container_width=True):
            st.session_state.wizard_step = min(7, st.session_state.wizard_step + 1)
            st.rerun()

def account_inputs(spouse_label, spouse_key):
    age = st.session_state.get(f"{spouse_key}_age", 35)
    st.markdown(f"#### {spouse_label}")
    col1, col2 = st.columns(2)
    with col1:
        use_401k = st.checkbox("Traditional 401(k)", key=f"{spouse_key}_use_traditional_401k")
        if use_401k:
            _, _, limit = get_401k_limits(age)
            st.caption(f"Annual employee limit estimate: ${limit:,.0f}")
            st.number_input("401(k) balance", min_value=0.0, value=0.0, step=1000.0, key=f"{spouse_key}_trad_401k_bal")
            st.number_input("Annual contribution", min_value=0.0, value=0.0, step=500.0, key=f"{spouse_key}_trad_401k_cont")
            st.number_input("Employer match", min_value=0.0, value=0.0, step=500.0, key=f"{spouse_key}_trad_401k_match")
            st.number_input("Growth rate %", min_value=0.0, max_value=15.0, value=7.0, step=0.1, key=f"{spouse_key}_trad_401k_rate")

        use_roth401k = st.checkbox("Roth 401(k)", key=f"{spouse_key}_use_roth_401k")
        if use_roth401k:
            st.number_input("Roth 401(k) balance", min_value=0.0, value=0.0, step=1000.0, key=f"{spouse_key}_roth_401k_bal")
            st.number_input("Annual contribution", min_value=0.0, value=0.0, step=500.0, key=f"{spouse_key}_roth_401k_cont")
            st.number_input("Growth rate %", min_value=0.0, max_value=15.0, value=7.0, step=0.1, key=f"{spouse_key}_roth_401k_rate")

        use_brokerage = st.checkbox("Taxable brokerage", key=f"{spouse_key}_use_brokerage")
        if use_brokerage:
            st.number_input("Brokerage balance", min_value=0.0, value=0.0, step=1000.0, key=f"{spouse_key}_brok_bal")
            st.number_input("Annual contribution", min_value=0.0, value=0.0, step=500.0, key=f"{spouse_key}_brok_cont")
            st.number_input("Growth rate %", min_value=0.0, max_value=15.0, value=6.0, step=0.1, key=f"{spouse_key}_brok_rate")
    with col2:
        use_trad_ira = st.checkbox("Traditional IRA", key=f"{spouse_key}_use_traditional_ira")
        if use_trad_ira:
            _, _, limit = get_ira_limits(age)
            st.caption(f"Annual limit estimate: ${limit:,.0f}")
            st.number_input("Traditional IRA balance", min_value=0.0, value=0.0, step=1000.0, key=f"{spouse_key}_trad_ira_bal")
            st.number_input("Annual contribution", min_value=0.0, value=0.0, step=500.0, key=f"{spouse_key}_trad_ira_cont")
            st.number_input("Growth rate %", min_value=0.0, max_value=15.0, value=7.0, step=0.1, key=f"{spouse_key}_trad_ira_rate")

        use_roth = st.checkbox("Roth IRA", key=f"{spouse_key}_use_roth_ira")
        if use_roth:
            _, _, limit = get_ira_limits(age)
            st.caption(f"Annual limit estimate: ${limit:,.0f}")
            st.number_input("Roth IRA balance", min_value=0.0, value=0.0, step=1000.0, key=f"{spouse_key}_roth_bal")
            st.number_input("Annual contribution", min_value=0.0, value=0.0, step=500.0, key=f"{spouse_key}_roth_cont")
            st.number_input("Growth rate %", min_value=0.0, max_value=15.0, value=7.0, step=0.1, key=f"{spouse_key}_roth_rate")

        use_hsa = st.checkbox("HSA", key=f"{spouse_key}_use_hsa")
        if use_hsa:
            coverage = st.selectbox("HSA coverage", ["Self-only", "Family"], key=f"{spouse_key}_hsa_coverage")
            _, _, limit = get_hsa_limit(age, coverage)
            st.caption(f"Annual limit estimate: ${limit:,.0f}")
            st.number_input("HSA balance", min_value=0.0, value=0.0, step=500.0, key=f"{spouse_key}_hsa_bal")
            st.number_input("Annual contribution", min_value=0.0, value=0.0, step=250.0, key=f"{spouse_key}_hsa_cont")
            st.number_input("Growth rate %", min_value=0.0, max_value=15.0, value=6.0, step=0.1, key=f"{spouse_key}_hsa_rate")

def includes_spouse():
    return st.session_state.get("planning_for", "Me + spouse") == "Me + spouse"

def _positive_state(key):
    return float(st.session_state.get(key) or 0) > 0

def has_entered_balance_or_income():
    """True when the user entered savings or income that a score can be based on.

    A fresh plan starts with every balance and earnings field at zero. The old
    $60,000 earnings example is no longer prefilled, so leaving the wizard blank
    does not count as income.
    """
    people = ["spouse1"] + (["spouse2"] if includes_spouse() else [])
    tracked = [
        ("use_traditional_401k", ["trad_401k_bal", "trad_401k_cont", "trad_401k_match"]),
        ("use_roth_401k", ["roth_401k_bal", "roth_401k_cont"]),
        ("use_traditional_ira", ["trad_ira_bal", "trad_ira_cont"]),
        ("use_roth_ira", ["roth_bal", "roth_cont"]),
        ("use_hsa", ["hsa_bal", "hsa_cont"]),
        ("use_brokerage", ["brok_bal", "brok_cont"]),
    ]
    for person in people:
        for flag, suffixes in tracked:
            if not st.session_state.get(f"{person}_{flag}", False):
                continue
            for suffix in suffixes:
                if _positive_state(f"{person}_{suffix}"):
                    return True
    if st.session_state.get("use_pension", False):
        if _positive_state("pen_sp1"):
            return True
        if includes_spouse() and _positive_state("pen_sp2"):
            return True
    if st.session_state.get("use_home_equity", False) and _positive_state("home_value"):
        return True
    if _positive_state("avg_earn_sp1"):
        return True
    if includes_spouse() and _positive_state("avg_earn_sp2"):
        return True
    if st.session_state.get("use_manual_ss", False):
        if _positive_state("ss_ann_sp1"):
            return True
        if includes_spouse() and _positive_state("ss_ann_sp2"):
            return True
    return False

def retirement_age_bounds(current_age: int):
    """Keep the retirement-age field at or above the person's current age.

    The previous slider started at 40 even when current age was higher, so the
    target could default below the age entered on this step.
    """
    current_age = int(current_age)
    min_age = max(current_age, 40)
    max_age = max(80, current_age)
    if min_age > max_age:
        max_age = min_age
    return min_age, max_age

def read_accounts(spouse_key):
    accounts = {}
    account_defs = [
        ("trad_401k", "Traditional 401(k)", "trad_401k_bal", "trad_401k_cont", "trad_401k_rate", "trad_401k_match", "use_traditional_401k"),
        ("roth_401k", "Roth 401(k)", "roth_401k_bal", "roth_401k_cont", "roth_401k_rate", None, "use_roth_401k"),
        ("trad_ira", "Traditional IRA", "trad_ira_bal", "trad_ira_cont", "trad_ira_rate", None, "use_traditional_ira"),
        ("roth_ira", "Roth IRA", "roth_bal", "roth_cont", "roth_rate", None, "use_roth_ira"),
        ("hsa", "HSA", "hsa_bal", "hsa_cont", "hsa_rate", None, "use_hsa"),
        ("brokerage", "Brokerage", "brok_bal", "brok_cont", "brok_rate", None, "use_brokerage"),
    ]
    for short, name, bal, cont, rate, match, use in account_defs:
        if st.session_state.get(f"{spouse_key}_{use}", False):
            accounts[short] = {
                "name": name,
                "balance": float(st.session_state.get(f"{spouse_key}_{bal}", 0) or 0),
                "contrib": float(st.session_state.get(f"{spouse_key}_{cont}", 0) or 0),
                "rate": float(st.session_state.get(f"{spouse_key}_{rate}", 0) or 0),
                "employer_match": float(st.session_state.get(f"{spouse_key}_{match}", 0) or 0) if match else 0.0,
            }
    return accounts

def calculate_results():
    planning_for = st.session_state.get("planning_for", "Me + spouse")
    include_spouse2 = includes_spouse()
    retirement_age = int(st.session_state.get("retirement_age", 65))
    sp1_age = int(st.session_state.get("spouse1_age", 35))
    sp2_age = int(st.session_state.get("spouse2_age", 35)) if include_spouse2 else sp1_age
    spouse_ages = {"spouse1": sp1_age, "spouse2": sp2_age}
    accounts = {"spouse1": read_accounts("spouse1"), "spouse2": read_accounts("spouse2") if include_spouse2 else {}}
    total_invest = 0.0
    max_years = 0
    for spouse_key, spouse_accounts in accounts.items():
        current_age = spouse_ages.get(spouse_key, 30)
        years_to_retirement = max(retirement_age - current_age, 0)
        max_years = max(max_years, years_to_retirement)
        for acc in spouse_accounts.values():
            total_invest += future_value(acc["balance"], acc["contrib"] + acc["employer_match"], acc["rate"] / 100, years_to_retirement)

    use_home_equity = bool(st.session_state.get("use_home_equity", False))
    include_home = bool(st.session_state.get("include_home", True)) if use_home_equity else False
    home_value = float(st.session_state.get("home_value", 0) or 0)
    mortgage_balance = float(st.session_state.get("mortgage_balance", 0) or 0)
    home_appreciation = float(st.session_state.get("home_appreciation_pct", 3.0) or 0) / 100
    use_mortgage_calc = bool(st.session_state.get("use_mortgage_calc", False))

    schedule_no_extra = {"amortizes": False, "months": None, "interest": 0.0, "balances": [mortgage_balance]}
    schedule_with_extra = {"amortizes": False, "months": None, "interest": 0.0, "balances": [mortgage_balance]}
    if use_mortgage_calc:
        mort_principal = float(st.session_state.get("mort_principal", mortgage_balance) or 0)
        mort_rate = float(st.session_state.get("mort_rate_pct", 6.5) or 0) / 100
        monthly_payment = float(st.session_state.get("monthly_payment", 1500) or 0)
        extra_monthly = float(st.session_state.get("extra_monthly", 0) or 0)
        schedule_no_extra = amortization_schedule(mort_principal, mort_rate, monthly_payment, 0)
        schedule_with_extra = amortization_schedule(mort_principal, mort_rate, monthly_payment, extra_monthly)

    if include_home:
        home_proj_value = home_value * (1 + home_appreciation) ** max_years
        if use_mortgage_calc and schedule_no_extra["amortizes"]:
            mortgage_at_ret = projected_mortgage_balance(schedule_no_extra["balances"], max_years)
        else:
            mortgage_at_ret = mortgage_balance
        home_proj_equity = max(home_proj_value - mortgage_at_ret, 0.0)
    else:
        home_proj_equity = 0.0

    total_nw = total_invest + home_proj_equity
    wd_rate_pct = float(st.session_state.get("wd_rate_pct", 4.5) or 4.5)
    post_growth_pct = float(st.session_state.get("post_growth_pct", 6.0) or 6.0)
    wd_rate = wd_rate_pct / 100
    post_growth = post_growth_pct / 100
    annual_wd = total_invest * wd_rate if total_invest > 0 else 0

    est_ss_sp1 = estimate_ss_pia(float(st.session_state.get("avg_earn_sp1", 0) or 0))
    est_ss_sp2 = estimate_ss_pia(float(st.session_state.get("avg_earn_sp2", 0) or 0)) if include_spouse2 else 0
    if st.session_state.get("use_manual_ss", False):
        ss_annual_sp1 = float(st.session_state.get("ss_ann_sp1", est_ss_sp1) or 0)
        ss_annual_sp2 = float(st.session_state.get("ss_ann_sp2", est_ss_sp2) or 0) if include_spouse2 else 0
    else:
        ss_annual_sp1, ss_annual_sp2 = est_ss_sp1, est_ss_sp2
    pension_annual_sp1 = float(st.session_state.get("pen_sp1", 0) or 0) if st.session_state.get("use_pension", False) else 0
    pension_annual_sp2 = float(st.session_state.get("pen_sp2", 0) or 0) if include_spouse2 and st.session_state.get("use_pension", False) else 0

    wd_years_max = 60
    balances = [total_invest]
    depleted_year = None
    if total_invest > 0:
        for y in range(1, wd_years_max + 1):
            new_bal = balances[-1] * (1 + post_growth) - annual_wd
            if new_bal <= 0:
                depleted_year = y
                balances.append(0.0)
                break
            balances.append(new_bal)
        while len(balances) < wd_years_max + 1:
            balances.append(max(balances[-1] * (1 + post_growth) - annual_wd, 0.0))
    else:
        balances = [0]

    if depleted_year is None and total_invest > 0:
        depletion_age_label = f"Past age {retirement_age + wd_years_max}"
        years_last = wd_years_max
    elif depleted_year is None:
        depletion_age_label = "Not enough investment balance"
        years_last = 0
    else:
        depletion_age_label = f"Around age {retirement_age + depleted_year}"
        years_last = depleted_year

    score = 30
    if total_invest > 0:
        score += min(30, max_years + 5)
    if years_last >= 35:
        score += 25
    elif years_last >= 25:
        score += 18
    elif years_last >= 15:
        score += 10
    if wd_rate_pct <= 4.0:
        score += 10
    elif wd_rate_pct <= 5.0:
        score += 6
    if post_growth_pct <= 7.0:
        score += 5
    else:
        score += 2
    score = max(0, min(100, int(score)))
    if score >= 80:
        score_label, score_class = "Strong", "green"
    elif score >= 60:
        score_label, score_class = "Moderate", "yellow"
    else:
        score_label, score_class = "Needs attention", "red"

    years_arr = np.arange(0, max_years + 6)
    invest_growth = np.zeros(len(years_arr))
    home_growth = np.zeros(len(years_arr))
    for i, y in enumerate(years_arr):
        total_y = 0
        for spouse_key, spouse_accounts in accounts.items():
            current_age = spouse_ages.get(spouse_key, 30)
            yrs_to_ret = max(retirement_age - current_age, 0)
            effective_years = min(y, yrs_to_ret)
            for acc in spouse_accounts.values():
                total_y += future_value(acc["balance"], acc["contrib"] + acc["employer_match"], acc["rate"] / 100, effective_years)
        invest_growth[i] = total_y
        if include_home:
            future_home_value = home_value * (1 + home_appreciation) ** y
            future_mortgage_balance = projected_mortgage_balance(schedule_no_extra["balances"], y) if use_mortgage_calc and schedule_no_extra["amortizes"] else mortgage_balance
            home_growth[i] = max(future_home_value - future_mortgage_balance, 0.0)

    return {
        "planning_for": planning_for,
        "retirement_age": retirement_age,
        "sp1_age": sp1_age,
        "sp2_age": sp2_age,
        "include_spouse2": include_spouse2,
        "accounts": accounts,
        "total_invest": total_invest,
        "home_proj_equity": home_proj_equity,
        "total_nw": total_nw,
        "max_years": max_years,
        "wd_rate_pct": wd_rate_pct,
        "post_growth_pct": post_growth_pct,
        "annual_wd": annual_wd,
        "balances": balances,
        "depleted_year": depleted_year,
        "depletion_age_label": depletion_age_label,
        "score": score,
        "score_label": score_label,
        "score_class": score_class,
        "years_arr": years_arr,
        "invest_growth": invest_growth,
        "home_growth": home_growth,
        "total_growth": invest_growth + home_growth,
        "ss_total": ss_annual_sp1 + ss_annual_sp2,
        "pension_total": pension_annual_sp1 + pension_annual_sp2,
        "schedule_no_extra": schedule_no_extra,
        "schedule_with_extra": schedule_with_extra,
        "score_ready": has_entered_balance_or_income(),
    }

# ==========================================================
# SIDEBAR
# ==========================================================
with st.sidebar:
    st.markdown("### Retirement Audit")
    st.caption("AI retirement planning calculator")
    st.markdown("---")
    if st.session_state.user_logged_in:
        st.success(f"Logged in: {st.session_state.user_email}")
        if st.session_state.is_paid_user:
            status = str(st.session_state.subscription_status or "").lower()
            st.write("Plan: **Unlocked**")
            if status in ACTIVE_SUBSCRIPTION_STATUSES or st.session_state.paid_via == "subscription":
                st.caption("Existing subscription")
            else:
                st.caption("$5 once")
        else:
            st.write("Plan: **Free**")
        if st.button("Log out", use_container_width=True):
            sign_out_user()
            st.rerun()
    else:
        st.info("No account needed to start.")
    st.markdown("---")
    if st.button("Restart audit", use_container_width=True):
        st.session_state.started = False
        st.session_state.wizard_step = 1
        st.rerun()

# ==========================================================
# LANDING PAGE
# ==========================================================
if not st.session_state.started:
    st.markdown(
        """
        <div class='hero-card'>
            <span class='pill'>FREE RETIREMENT AUDIT</span>
            <span class='pill'>Takes about 4 minutes</span>
            <div class='hero-title'>Know if your retirement plan will actually last.</div>
            <p class='hero-sub'>Project retirement accounts, Social Security, home equity, withdrawals, and then ask an AI retirement planner questions based on your numbers.</p>
            <p><span class='pill'>✓ See if your money lasts</span><span class='pill'>✓ Test retirement ages</span><span class='pill'>✓ Compare withdrawal rates</span><span class='pill'>✓ Ask AI about your plan</span></p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns([1.2, 1, 1])
    with c1:
        if st.button("Start My Free Retirement Audit", type="primary", use_container_width=True):
            st.session_state.started = True
            st.session_state.wizard_step = 1
            st.rerun()
    with c2:
        st.markdown("<div class='metric-card'><div class='muted'>Cost to start</div><div class='big-metric'>Free</div></div>", unsafe_allow_html=True)
    with c3:
        st.markdown("<div class='metric-card'><div class='muted'>Account required?</div><div class='big-metric'>No</div></div>", unsafe_allow_html=True)

    st.markdown("### What you get")
    cols = st.columns(3)
    with cols[0]:
        st.markdown("<div class='summary-card'><h3>Retirement Score</h3><p class='muted'>Get a simple snapshot of how your plan looks based on your assumptions.</p></div>", unsafe_allow_html=True)
    with cols[1]:
        st.markdown("<div class='summary-card'><h3>Money Lasts Estimate</h3><p class='muted'>See whether your projected investments last through retirement.</p></div>", unsafe_allow_html=True)
    with cols[2]:
        st.markdown("<div class='summary-card'><h3>AI Planner</h3><p class='muted'>Ask questions like: Can I retire at 60? Is 4% safe? What should I change?</p></div>", unsafe_allow_html=True)
    render_creator_footer()
    st.stop()

# ==========================================================
# WIZARD STEPS
# ==========================================================
if st.session_state.get("_scenario_loaded_message"):
    st.success(st.session_state["_scenario_loaded_message"])
    st.session_state["_scenario_loaded_message"] = None

step = st.session_state.wizard_step

if step == 1:
    section_header(1, "Who are you planning retirement for?", "Start simple. You can add more detail as you go.")
    st.radio("Planning for", ["Just me", "Me + spouse"], horizontal=True, key="planning_for")
    next_back_buttons(show_back=False)

elif step == 2:
    section_header(2, "Ages and retirement target", "This tells the calculator how many years your money has to grow.")
    your_age = int(st.session_state.get("spouse1_age") or 35)
    min_ret, max_ret = retirement_age_bounds(your_age)
    target_age = int(st.session_state.get("retirement_age") or 65)
    if target_age < min_ret:
        target_age = min_ret
    elif target_age > max_ret:
        target_age = max_ret
    st.session_state.retirement_age = target_age
    if includes_spouse():
        c1, c2, c3 = st.columns(3)
    else:
        c1, c3 = st.columns(2)
        c2 = None
    with c1:
        st.number_input(
            "Your current age",
            min_value=18,
            max_value=90,
            value=35,
            step=1,
            key="spouse1_age",
            help="How old you are today. Starts at 35.",
        )
    if includes_spouse() and c2 is not None:
        with c2:
            st.number_input(
                "Spouse's current age",
                min_value=18,
                max_value=90,
                value=35,
                step=1,
                key="spouse2_age",
                help="How old your spouse is today. Starts at 35. Used only when you choose Me + spouse.",
            )
    with c3:
        st.number_input(
            "Target retirement age",
            min_value=min_ret,
            max_value=max_ret,
            value=target_age,
            step=1,
            key="retirement_age",
            help="The age you plan to retire. Starts at 65, and is never set below your current age.",
        )
        shown_target = int(st.session_state.get("retirement_age") or target_age)
        st.caption(f"Your current age is {your_age}. Target retirement age is {shown_target} and must be from {min_ret} to {max_ret}.")
    next_back_buttons()

elif step == 3:
    section_header(3, "Retirement accounts", "Check only the accounts you have. Leave anything else blank.")
    account_inputs("You", "spouse1")
    if includes_spouse():
        st.markdown("---")
        account_inputs("Spouse", "spouse2")
    next_back_buttons()

elif step == 4:
    section_header(4, "Social Security and pension", "Use estimates now. You can override with your own values if you know them.")
    st.markdown("#### Social Security estimator")
    c1, c2 = st.columns(2)
    with c1:
        st.number_input(
            "Your average annual earnings",
            min_value=0,
            max_value=300000,
            value=0,
            step=1000,
            key="avg_earn_sp1",
            help="Used to estimate Social Security. For example, 60000. Leave at 0 if you have not entered income yet.",
        )
        st.metric("Estimated annual SS at FRA", money(estimate_ss_pia(st.session_state.get("avg_earn_sp1", 0))))
    if includes_spouse():
        with c2:
            st.number_input("Spouse average annual earnings", min_value=0, max_value=300000, value=0, step=1000, key="avg_earn_sp2")
            st.metric("Estimated annual SS at FRA", money(estimate_ss_pia(st.session_state.get("avg_earn_sp2", 0))))
    st.caption("Example: average earnings of $60,000 estimate about " + money(estimate_ss_pia(60000)) + " a year. This is a simplified estimate. For an exact estimate, use ssa.gov/myaccount.")
    st.checkbox("Use manual Social Security amounts", key="use_manual_ss")
    if st.session_state.get("use_manual_ss"):
        c3, c4 = st.columns(2)
        with c3:
            st.slider("Your claim age", 62, 70, 67, key="ss_start_sp1")
            st.number_input("Your annual SS at claim age", min_value=0, max_value=100000, value=int(estimate_ss_pia(st.session_state.get("avg_earn_sp1", 0))), step=1000, key="ss_ann_sp1")
        if includes_spouse():
            with c4:
                st.slider("Spouse claim age", 62, 70, 67, key="ss_start_sp2")
                st.number_input("Spouse annual SS at claim age", min_value=0, max_value=100000, value=int(estimate_ss_pia(st.session_state.get("avg_earn_sp2", 0))), step=1000, key="ss_ann_sp2")
    st.markdown("#### Pension")
    st.checkbox("Include pension / defined benefit", key="use_pension")
    if st.session_state.get("use_pension"):
        c5, c6 = st.columns(2)
        with c5:
            st.number_input("Your annual pension", min_value=0, value=0, step=1000, key="pen_sp1")
            st.slider("Your pension COLA %", 0.0, 5.0, 2.0, step=0.1, key="pen_cola_sp1")
        if includes_spouse():
            with c6:
                st.number_input("Spouse annual pension", min_value=0, value=0, step=1000, key="pen_sp2")
                st.slider("Spouse pension COLA %", 0.0, 5.0, 2.0, step=0.1, key="pen_cola_sp2")
    next_back_buttons()

elif step == 5:
    section_header(5, "Home equity and mortgage", "Optional. Only include this if you want home equity in your net worth projection.")
    st.checkbox("Include home equity", key="use_home_equity")
    if st.session_state.get("use_home_equity"):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.number_input("Current home value", min_value=0.0, value=0.0, format="%.0f", key="home_value")
        with c2:
            st.number_input("Remaining mortgage", min_value=0.0, value=0.0, format="%.0f", key="mortgage_balance")
        with c3:
            st.slider("Annual home appreciation %", min_value=0.0, max_value=10.0, value=3.0, step=0.1, key="home_appreciation_pct")
        st.checkbox("Include home equity in net worth", value=True, key="include_home")
    st.checkbox("Include mortgage payoff calculator", key="use_mortgage_calc")
    if st.session_state.get("use_mortgage_calc"):
        c4, c5, c6, c7 = st.columns(4)
        with c4:
            st.number_input("Mortgage balance", min_value=0.0, value=float(st.session_state.get("mortgage_balance", 0) or 0), format="%.2f", key="mort_principal")
        with c5:
            st.number_input("Interest rate %", min_value=0.0, max_value=20.0, value=6.5, step=0.125, key="mort_rate_pct")
        with c6:
            st.number_input("Monthly payment", min_value=0.0, value=1500.0, format="%.2f", key="monthly_payment")
        with c7:
            st.number_input("Extra monthly", min_value=0.0, value=0.0, format="%.2f", key="extra_monthly")
    next_back_buttons()

elif step == 6:
    section_header(6, "Withdrawal assumptions", "This estimates how long your investments may last after retirement.")
    c1, c2 = st.columns(2)
    with c1:
        st.slider("Annual withdrawal rate from investments %", min_value=3.0, max_value=12.0, value=4.5, step=0.1, key="wd_rate_pct", help="Lower rates are generally safer for longer retirements.")
    with c2:
        st.slider("Expected annual portfolio growth in retirement %", min_value=0.0, max_value=12.0, value=6.0, step=0.1, key="post_growth_pct", help="This is a simplified assumption.")
    results = calculate_results()
    st.markdown("### Quick preview")
    c3, c4, c5 = st.columns(3)
    with c3:
        st.metric("Projected investments", money(results["total_invest"]))
    with c4:
        st.metric("First-year withdrawal", money(results["annual_wd"]))
    with c5:
        st.metric("Money lasts estimate", results["depletion_age_label"])
    if not results["score_ready"]:
        st.info("Enter at least one account balance, contribution, pension, home value, or earnings amount to get a Retirement Score. With those left blank, the dollars above stay at $0.")
    next_back_buttons("See My Results")

elif step == 7:
    results = calculate_results()
    st.markdown("<span class='pill'>YOUR RETIREMENT AUDIT RESULTS</span>", unsafe_allow_html=True)
    if not results["score_ready"]:
        st.markdown(
            """
            <div class='step-card'>
                <h2>Enter a balance or income to see your score</h2>
                <p class='muted'>Add at least one account balance, contribution, pension, home value, or earnings amount. With those left blank, a Retirement Score would only reflect the default withdrawal assumptions (41/100, Needs attention) and every dollar result would be $0.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        prompt_accounts, prompt_income = st.columns(2)
        with prompt_accounts:
            if st.button("Enter account balances", type="primary", use_container_width=True):
                st.session_state.wizard_step = 3
                st.rerun()
        with prompt_income:
            if st.button("Enter income", use_container_width=True):
                st.session_state.wizard_step = 4
                st.rerun()
    else:
        st.markdown(f"# Retirement Score: <span class='{results['score_class']}'>{results['score']} / 100</span>", unsafe_allow_html=True)
        st.markdown(f"### {results['score_label']} outlook based on the assumptions you entered")
        if results["total_invest"] <= 0:
            st.info("This score is based on invested savings and your withdrawal assumptions. Social Security, pension, and home equity are not part of the score, so with no investment balance it stays near the baseline.")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"<div class='metric-card'><div class='muted'>Projected investments</div><div class='big-metric'>{money(results['total_invest'])}</div></div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='metric-card'><div class='muted'>Projected net worth</div><div class='big-metric'>{money(results['total_nw'])}</div></div>", unsafe_allow_html=True)
        with c3:
            st.markdown(f"<div class='metric-card'><div class='muted'>First-year withdrawal</div><div class='big-metric'>{money(results['annual_wd'])}</div></div>", unsafe_allow_html=True)
        with c4:
            st.markdown(f"<div class='metric-card'><div class='muted'>Money lasts estimate</div><div class='big-metric'>{results['depletion_age_label']}</div></div>", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("## Your projection")
        chart_pngs = []
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(results["years_arr"], results["invest_growth"], label="Investments", linewidth=3)
        if np.max(results["home_growth"]) > 0:
            ax.plot(results["years_arr"], results["home_growth"], label="Home Equity", linewidth=3)
        ax.plot(results["years_arr"], results["total_growth"], label="Total Net Worth", linewidth=4, linestyle="--")
        ax.set_xlabel("Years from now")
        ax.set_ylabel("Value ($)")
        ax.legend()
        ax.grid(True, alpha=0.3)
        chart_pngs.append(figure_png(fig))
        st.pyplot(fig)

        if results["total_invest"] > 0:
            st.markdown("## Retirement withdrawal simulation")
            years_post = np.arange(0, len(results["balances"]))
            fig2, ax2 = plt.subplots(figsize=(12, 6))
            ax2.plot(years_post, results["balances"], label="Portfolio Balance", linewidth=3)
            ax2.axhline(results["total_invest"], linestyle="--", label="Starting Balance")
            if results["depleted_year"] is not None:
                ax2.axvline(results["depleted_year"], linestyle="--", label="Depletion Point")
            ax2.set_xlabel("Years in retirement")
            ax2.set_ylabel("Balance ($)")
            ax2.set_title(f"Withdrawal at {results['wd_rate_pct']:.1f}% with {results['post_growth_pct']:.1f}% annual growth")
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            chart_pngs.append(figure_png(fig2))
            st.pyplot(fig2)

        if st.session_state.is_paid_user:
            render_paid_action_plan(results, chart_pngs)
        else:
            render_unlock_paywall("after_charts")

    st.markdown("---")
    st.markdown("## Ask AI about your retirement plan")
    st.caption("For educational purposes only. This is not financial, tax, or legal advice.")
    st.markdown("Ask questions like: **Can I retire earlier? Is my withdrawal rate too high? What should I change first?**")
    questions_used = int(st.session_state.ai_question_count or 0)
    question_cap = ai_question_limit(bool(st.session_state.is_paid_user))
    questions_left = max(question_cap - questions_used, 0)
    if st.session_state.is_paid_user:
        st.success(f"Full audit unlocked. You have {questions_left} of {question_cap} AI questions left.")
    else:
        st.info(f"You have {questions_left} free AI question(s) remaining.")
    if st.session_state.get("_ai_count_unsaved"):
        st.caption("Your latest question counted, but it could not be saved on your profile yet. Run the database migration so the count stays after a refresh.")
    if not st.session_state.is_paid_user and questions_left == 0:
        st.caption("You've used your 3 free AI questions.")
        render_unlock_paywall("ai_limit")
    ai_question = st.text_area("Type your retirement question", placeholder="Example: Am I on track to retire by 65?", key="ai_question_input")
    ask_ai_clicked = st.button("Get AI Retirement Insight", type="primary", use_container_width=True)
    if ask_ai_clicked:
        can_ask, message = user_can_ask_ai()
        if not can_ask:
            if message == "limit":
                st.warning("You've used all 50 AI questions included with your unlock.")
            elif questions_left > 0:
                # The paywall above is already on screen when the free cap is spent.
                render_unlock_paywall("ai_click")
        elif not ai_question.strip():
            st.error("Please type a question first.")
        else:
            try:
                with st.spinner("Thinking..."):
                    ai_response = get_real_ai_response(ai_question, results)
                st.session_state.ai_question_count = questions_used + 1
                if st.session_state.user_logged_in and st.session_state.user_id:
                    persist_ai_question_count(st.session_state.user_id, st.session_state.ai_question_count)
                st.session_state.ai_chat_history.append({"question": ai_question, "answer": ai_response})
                st.rerun()
            except Exception as e:
                st.error(f"AI request failed: {e}")

    if st.session_state.ai_chat_history:
        st.markdown("### AI Conversation")
        for chat in reversed(st.session_state.ai_chat_history):
            st.markdown(f"**Question:** {chat['question']}")
            st.markdown(chat["answer"])
            st.markdown("---")

    st.markdown("---")
    st.markdown("## Save this plan")
    if not st.session_state.user_logged_in:
        st.markdown(
            "<div class='upgrade-card'><h3>Create a free account</h3><p class='muted'>The audit, score, and 3 AI questions stay free without an account. A free account is what checkout uses, and the $5 unlock keeps your plan on that account.</p></div>",
            unsafe_allow_html=True,
        )
        render_auth_tabs("save")
    elif not st.session_state.is_paid_user:
        render_unlock_paywall("save")
    else:
        scenario_name = st.text_input("Plan Name", value=st.session_state.get("scenario_name", "My Retirement Plan"), key="scenario_name")
        if st.button("Save Plan", use_container_width=True):
            if not scenario_name.strip():
                st.error("Please enter a plan name.")
            else:
                _, error = save_scenario_to_supabase(st.session_state.user_id, scenario_name.strip(), collect_app_state())
                st.success("Plan saved successfully." if not error else f"Save failed: {error}")
        scenarios, error = get_user_scenarios(st.session_state.user_id)
        if error:
            st.error(f"Could not load saved plans: {error}")
        elif scenarios:
            options = {f"{item['scenario_name']} ({item.get('updated_at', 'saved')})": item for item in scenarios}
            selected = st.selectbox("Load a saved plan", list(options.keys()), key="saved_scenario_select")
            if st.button("Load Selected Plan", use_container_width=True):
                data = options[selected].get("scenario_data", {})
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except Exception:
                        data = {}
                queue_scenario_for_load(data, options[selected].get("scenario_name", "Plan"))

    st.markdown("---")
    b1, b2 = st.columns(2)
    with b1:
        if st.button("← Edit assumptions", use_container_width=True):
            st.session_state.wizard_step = 6
            st.rerun()
    with b2:
        if st.button("Start over", use_container_width=True):
            st.session_state.started = False
            st.session_state.wizard_step = 1
            st.rerun()

# ==========================================================
# IMPORTANT INFO
# ==========================================================
st.markdown("---")
with st.expander("Important disclaimer", expanded=False):
    st.markdown("""
This tool is provided for educational and informational purposes only and does not constitute financial, investment, tax, or legal advice.

All projections and estimates are based on user inputs and assumptions that may not reflect real-world outcomes. Actual results will vary based on market conditions, individual circumstances, taxes, inflation, and other factors.

You should consult a qualified financial professional before making important financial decisions.
""")
with st.expander("Privacy notice", expanded=False):
    st.markdown("""
We do not ask for or store highly sensitive personal financial information such as account numbers or Social Security numbers in this calculator.

Any information entered into this tool is used to generate estimates and projections based on the values you provide.
""")
with st.expander("For financial advisors", expanded=False):
    st.markdown("""
Are you a licensed financial advisor interested in being featured in this app?

**Email:** retirementaudit@gmail.com
""")
render_creator_footer()
