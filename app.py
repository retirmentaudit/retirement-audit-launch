import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from openai import OpenAI
from supabase import create_client, Client
import stripe
import json

# ==========================================================
# PAGE CONFIG
# ==========================================================
st.set_page_config(page_title="Retirement Audit App", layout="wide")

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

missing_secrets = [key for key in REQUIRED_SECRETS if key not in st.secrets]
if missing_secrets:
    st.error(
        "Missing required secrets in secrets.toml: "
        + ", ".join(missing_secrets)
    )
    st.stop()

# OPENAI is optional for the app to load, but required for AI responses
OPENAI_ENABLED = "OPENAI_API_KEY" in st.secrets

# ==========================================================
# CLIENTS
# ==========================================================
supabase: Client = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]

def create_portal_session(customer_id):
    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=APP_URL
        )
        return session.url
    except Exception as e:
        return None
    
openai_client = None
if OPENAI_ENABLED:
    try:
        openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    except Exception:
        openai_client = None
        OPENAI_ENABLED = False

APP_URL = st.secrets["APP_URL"].rstrip("/")
STRIPE_PRICE_ID = st.secrets["STRIPE_PRICE_ID"]

# ==========================================================
# STYLING
# ==========================================================
st.markdown(
    """
    <style>
    .stApp {
        background-color: #0e1117;
        color: white;
    }

    .stMarkdown, .stText, label, p, div, span {
        color: white !important;
    }

    .summary-card {
        padding: 16px;
        border-radius: 12px;
        background: #151b23;
        border: 1px solid #2d3748;
        margin-bottom: 12px;
    }

    .small-muted {
        color: #c9d1d9 !important;
        font-size: 0.95rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ==========================================================
# SESSION STATE DEFAULTS
# ==========================================================
DEFAULT_SESSION_VALUES = {
    "ai_question_count": 0,
    "ai_chat_history": [],
    "ai_limit": 3,
    "user_logged_in": False,
    "user_email": None,
    "user_id": None,
    "is_paid_user": False,
    "subscription_status": "free",
    "_scenario_to_apply": None,
    "_scenario_loaded_message": None,
    "_checkout_url": None,
    "_checkout_user_id": None,
    "scenario_name": "My Scenario",
}

for k, v in DEFAULT_SESSION_VALUES.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ==========================================================
# INPUT / SCENARIO KEYS
# ==========================================================
SCENARIO_KEYS = [
    "retirement_age",
    "use_home_equity",
    "home_value",
    "mortgage_balance",
    "home_appreciation_pct",
    "include_home",
    "use_mortgage_calc",
    "mort_principal",
    "mort_rate_pct",
    "mort_years",
    "monthly_payment",
    "extra_monthly",
    "wd_rate_pct",
    "post_growth_pct",
    "avg_earn_sp1",
    "avg_earn_sp2",
    "use_manual_ss",
    "ss_start_sp1",
    "ss_start_sp2",
    "ss_ann_sp1",
    "ss_ann_sp2",
    "use_pension",
    "pen_sp1",
    "pen_sp2",
    "pen_cola_sp1",
    "pen_cola_sp2",
    "scenario_name",
]

for spouse in ["spouse1", "spouse2"]:
    SCENARIO_KEYS.extend([
        f"{spouse}_age",

        f"{spouse}_use_traditional_ira",
        f"{spouse}_trad_ira_bal",
        f"{spouse}_trad_ira_cont",
        f"{spouse}_trad_ira_rate",

        f"{spouse}_use_roth_ira",
        f"{spouse}_roth_bal",
        f"{spouse}_roth_cont",
        f"{spouse}_roth_rate",

        f"{spouse}_use_hsa",
        f"{spouse}_hsa_coverage",
        f"{spouse}_hsa_bal",
        f"{spouse}_hsa_cont",
        f"{spouse}_hsa_rate",

        f"{spouse}_use_traditional_401k",
        f"{spouse}_trad_401k_bal",
        f"{spouse}_trad_401k_cont",
        f"{spouse}_trad_401k_match",
        f"{spouse}_trad_401k_rate",

        f"{spouse}_use_roth_401k",
        f"{spouse}_roth_401k_bal",
        f"{spouse}_roth_401k_cont",
        f"{spouse}_roth_401k_rate",

        f"{spouse}_use_brokerage",
        f"{spouse}_brok_bal",
        f"{spouse}_brok_cont",
        f"{spouse}_brok_rate",
    ])

# ==========================================================
# HELPER FUNCTIONS
# ==========================================================
def get_ira_limits(age: int):
    base_limit = 7500
    catch_up = 1100 if age >= 50 else 0
    total_limit = base_limit + catch_up
    return base_limit, catch_up, total_limit

def get_401k_limits(age: int):
    base_limit = 24500
    if 60 <= age <= 63:
        catch_up = 11250
    elif age >= 50:
        catch_up = 8000
    else:
        catch_up = 0
    total_limit = base_limit + catch_up
    return base_limit, catch_up, total_limit

def get_hsa_limit(age: int, coverage_type: str):
    base_limit = 4400 if coverage_type == "Self-only" else 8750
    catch_up = 1000 if age >= 55 else 0
    total_limit = base_limit + catch_up
    return base_limit, catch_up, total_limit

def estimate_ss_pia(avg_annual_earnings: float):
    if avg_annual_earnings <= 0:
        return 0

    aime = avg_annual_earnings / 12
    bend1 = 1286
    bend2 = 7749

    pia_monthly = (
        min(aime, bend1) * 0.90
        + max(0, min(aime - bend1, bend2 - bend1)) * 0.32
        + max(0, aime - bend2) * 0.15
    )

    pia_monthly = np.floor(pia_monthly * 10) / 10
    return round(pia_monthly * 12)

def future_value(balance: float, annual_contrib: float, annual_rate: float, years: int):
    if years <= 0:
        return float(balance)
    if annual_rate == 0:
        return float(balance) + float(annual_contrib) * years

    return (
        float(balance) * (1 + annual_rate) ** years
        + float(annual_contrib) * (((1 + annual_rate) ** years - 1) / annual_rate)
    )

def amortization_schedule(
    principal: float,
    annual_rate: float,
    monthly_payment: float,
    extra_monthly: float = 0.0,
    max_months: int = 1200
):
    principal = float(principal)
    annual_rate = float(annual_rate)
    monthly_payment = float(monthly_payment)
    extra_monthly = float(extra_monthly)

    if principal <= 0:
        return {
            "amortizes": True,
            "months": 0,
            "interest": 0.0,
            "balances": [0.0],
        }

    monthly_rate = annual_rate / 12
    balance = principal
    total_interest = 0.0
    month = 0
    balances = [balance]

    while balance > 0.005 and month < max_months:
        interest = balance * monthly_rate
        scheduled_payment = monthly_payment + extra_monthly
        actual_payment = min(scheduled_payment, balance + interest)
        principal_payment = actual_payment - interest

        if principal_payment <= 0:
            return {
                "amortizes": False,
                "months": None,
                "interest": total_interest,
                "balances": balances,
            }

        balance = max(balance - principal_payment, 0.0)
        total_interest += interest
        month += 1
        balances.append(balance)

    if month >= max_months and balance > 0.005:
        return {
            "amortizes": False,
            "months": None,
            "interest": total_interest,
            "balances": balances,
        }

    return {
        "amortizes": True,
        "months": month,
        "interest": total_interest,
        "balances": balances,
    }

def projected_mortgage_balance(schedule_balances, years_from_now: int):
    month_index = int(years_from_now * 12)
    if not schedule_balances:
        return 0.0
    if month_index >= len(schedule_balances):
        return 0.0
    return float(schedule_balances[month_index])

def format_ai_response(text: str):
    text = (text or "").strip()
    return text

def get_real_ai_response(
    user_question,
    total_invest,
    total_nw,
    retirement_age,
    include_home,
    home_proj_equity,
    wd_rate_pct,
    post_growth_pct,
    ss_annual_sp1,
    ss_annual_sp2,
    pension_annual_sp1,
    pension_annual_sp2,
):
    if not OPENAI_ENABLED or openai_client is None:
        raise RuntimeError("OPENAI_API_KEY is missing or invalid.")

    system_instructions = """
You are a helpful retirement planning assistant inside a Streamlit retirement calculator.

Rules:
- Keep the answer concise.
- Use short paragraphs or bullets.
- Be practical and easy to understand.
- Do not claim certainty.
- Do not present yourself as a licensed financial advisor.
- Do not give tax, legal, or regulated investment advice.
- Mention when assumptions seem aggressive.
- End with a short reminder to consult a qualified financial professional for major decisions.
"""

    user_context = f"""
Retirement age: {retirement_age}
Projected investments at retirement: ${total_invest:,.0f}
Projected total net worth at retirement: ${total_nw:,.0f}
Include home equity: {include_home}
Projected home equity at retirement: ${home_proj_equity:,.0f}
Withdrawal rate selected: {wd_rate_pct:.1f}%
Expected annual portfolio growth in retirement: {post_growth_pct:.1f}%
Spouse 1 annual Social Security: ${ss_annual_sp1:,.0f}
Spouse 2 annual Social Security: ${ss_annual_sp2:,.0f}
Spouse 1 annual pension: ${pension_annual_sp1:,.0f}
Spouse 2 annual pension: ${pension_annual_sp2:,.0f}

User question:
{user_question}
"""

    response = openai_client.responses.create(
        model="gpt-4.1-mini",
        instructions=system_instructions,
        input=user_context,
    )

    return format_ai_response(response.output_text)

def collect_app_state():
    scenario_data = {}
    for key in SCENARIO_KEYS:
        if key in st.session_state:
            value = st.session_state[key]
            if isinstance(value, (int, float, str, bool, list, dict)) or value is None:
                scenario_data[key] = value
    return scenario_data

def queue_scenario_for_load(saved_data: dict, scenario_name: str = None):
    st.session_state["_scenario_to_apply"] = saved_data.copy()
    st.session_state["_scenario_loaded_message"] = (
        f"Scenario loaded: {scenario_name}" if scenario_name else "Scenario loaded."
    )
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
        response = supabase.auth.sign_up({"email": email, "password": password})
        return response, None
    except Exception as e:
        return None, str(e)

def sign_in_user(email, password):
    try:
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        return response, None
    except Exception as e:
        return None, str(e)

def sign_out_user():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass

    st.session_state.user_logged_in = False
    st.session_state.user_email = None
    st.session_state.user_id = None
    st.session_state.is_paid_user = False
    st.session_state.subscription_status = "free"
    st.session_state._checkout_url = None
    st.session_state._checkout_user_id = None

def get_current_user():
    try:
        user_response = supabase.auth.get_user()
        if user_response and getattr(user_response, "user", None):
            return user_response.user
        return None
    except Exception:
        return None

def ensure_user_profile(user_id, email):
    try:
        existing = (
            supabase.table("user_profiles")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )

        if existing.data:
            return existing.data[0], None

        inserted = (
            supabase.table("user_profiles")
            .insert({
                "user_id": user_id,
                "email": email,
                "is_paid_user": False,
                "subscription_status": "free",
            })
            .execute()
        )

        if inserted.data:
            return inserted.data[0], None

        return None, "Could not create profile."
    except Exception as e:
        return None, str(e)

def get_user_profile(user_id):
    try:
        result = (
            supabase.table("user_profiles")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        if result.data:
            return result.data[0], None
        return None, None
    except Exception as e:
        return None, str(e)

def refresh_paid_status():
    if not st.session_state.user_id:
        st.session_state.is_paid_user = False
        st.session_state.subscription_status = "free"
        return

    profile, error = get_user_profile(st.session_state.user_id)

    if error or not profile:
        st.session_state.is_paid_user = False
        st.session_state.subscription_status = "free"
        return

    st.session_state.is_paid_user = bool(profile.get("is_paid_user", False))
    st.session_state.subscription_status = profile.get("subscription_status", "free")

# ==========================================================
# STRIPE HELPERS
# ==========================================================
def create_portal_session(customer_id: str):
    """
    Creates a Stripe Billing Portal session so paid users can
    manage/cancel their subscription.
    """
    if not customer_id:
        raise ValueError("Missing Stripe customer ID.")

    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=APP_URL,
    )

    return session.url

def create_checkout_session(user_id: str, email: str | None = None):
    """
    Creates a Stripe Checkout session.
    Your webhook / Supabase edge function should use metadata.user_id
    to mark the user as paid in user_profiles.
    """
    if not user_id:
        raise ValueError("User must be logged in before upgrading.")

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[
                {
                    "price": STRIPE_PRICE_ID,
                    "quantity": 1
                }
            ],
            success_url=f"{APP_URL}?checkout=success",
            cancel_url=f"{APP_URL}?checkout=cancel",
            allow_promotion_codes=True,
            client_reference_id=user_id,
            customer_email=email if email else None,
            metadata={
                "user_id": user_id,
                "email": email or "",
            },
        )
        return session
    except Exception as e:
        raise RuntimeError(f"Stripe checkout session creation failed: {e}")

def get_checkout_url():
    """
    Keeps a reusable checkout URL in session state so the link button
    is always clickable and the app does not recreate sessions more
    than needed for the same logged-in user.
    """
    if not st.session_state.user_logged_in or not st.session_state.user_id:
        return None

    if st.session_state.is_paid_user:
        return None

    cached_url = st.session_state.get("_checkout_url")
    cached_user = st.session_state.get("_checkout_user_id")

    if cached_url and cached_user == st.session_state.user_id:
        return cached_url

    session = create_checkout_session(
        st.session_state.user_id,
        st.session_state.user_email
    )
    st.session_state._checkout_url = session.url
    st.session_state._checkout_user_id = st.session_state.user_id
    return session.url

# ==========================================================
# SCENARIO HELPERS
# ==========================================================
def user_can_ask_ai():
    if st.session_state.is_paid_user:
        return True, None

    if st.session_state.ai_question_count < st.session_state.ai_limit:
        return True, None

    if not st.session_state.user_logged_in:
        return False, "Create an account to continue."

    return False, "Upgrade to Pro for unlimited AI."

def user_can_save_scenarios():
    return bool(st.session_state.is_paid_user)

def get_user_scenarios(user_id):
    try:
        result = (
            supabase.table("user_scenarios")
            .select("*")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .execute()
        )
        return result.data, None
    except Exception as e:
        return None, str(e)

def save_scenario_to_supabase(user_id, scenario_name, scenario_data):
    try:
        existing = (
            supabase.table("user_scenarios")
            .select("id")
            .eq("user_id", user_id)
            .eq("scenario_name", scenario_name)
            .execute()
        )

        payload = {
            "user_id": user_id,
            "scenario_name": scenario_name,
            "scenario_data": scenario_data,
        }

        if existing.data and len(existing.data) > 0:
            scenario_id = existing.data[0]["id"]
            result = (
                supabase.table("user_scenarios")
                .update(payload)
                .eq("id", scenario_id)
                .execute()
            )
        else:
            result = (
                supabase.table("user_scenarios")
                .insert(payload)
                .execute()
            )

        return result, None
    except Exception as e:
        return None, str(e)

# ==========================================================
# WIDGET HELPERS
# ==========================================================
def build_spouse_accounts(spouse_label: str, spouse_key: str):
    st.markdown(f"### {spouse_label}")

    age = st.number_input(
        f"{spouse_label} Current Age",
        min_value=18,
        max_value=90,
        value=35 if spouse_key == "spouse1" else 35,
        step=1,
        key=f"{spouse_key}_age",
    )

    accounts = {}

    col_a, col_b = st.columns(2)

    with col_a:
        use_trad_ira = st.checkbox("Use Traditional IRA", value=False, key=f"{spouse_key}_use_traditional_ira")
        if use_trad_ira:
            _, _, ira_limit = get_ira_limits(age)
            st.caption(f"Annual limit estimate: ${ira_limit:,.0f}")
            accounts["trad_ira"] = {
                "name": "Traditional IRA",
                "balance": st.number_input(
                    "Traditional IRA Balance ($)",
                    min_value=0.0,
                    value=0.0,
                    step=1000.0,
                    key=f"{spouse_key}_trad_ira_bal",
                ),
                "contrib": st.number_input(
                    "Traditional IRA Annual Contribution ($)",
                    min_value=0.0,
                    value=0.0,
                    step=500.0,
                    key=f"{spouse_key}_trad_ira_cont",
                ),
                "rate": st.number_input(
                    "Traditional IRA Growth Rate (%)",
                    min_value=0.0,
                    max_value=15.0,
                    value=7.0,
                    step=0.1,
                    key=f"{spouse_key}_trad_ira_rate",
                ),
                "employer_match": 0.0,
            }

        use_roth_ira = st.checkbox("Use Roth IRA", value=False, key=f"{spouse_key}_use_roth_ira")
        if use_roth_ira:
            _, _, ira_limit = get_ira_limits(age)
            st.caption(f"Annual limit estimate: ${ira_limit:,.0f}")
            accounts["roth_ira"] = {
                "name": "Roth IRA",
                "balance": st.number_input(
                    "Roth IRA Balance ($)",
                    min_value=0.0,
                    value=0.0,
                    step=1000.0,
                    key=f"{spouse_key}_roth_bal",
                ),
                "contrib": st.number_input(
                    "Roth IRA Annual Contribution ($)",
                    min_value=0.0,
                    value=0.0,
                    step=500.0,
                    key=f"{spouse_key}_roth_cont",
                ),
                "rate": st.number_input(
                    "Roth IRA Growth Rate (%)",
                    min_value=0.0,
                    max_value=15.0,
                    value=7.0,
                    step=0.1,
                    key=f"{spouse_key}_roth_rate",
                ),
                "employer_match": 0.0,
            }

        use_hsa = st.checkbox("Use HSA", value=False, key=f"{spouse_key}_use_hsa")
        if use_hsa:
            coverage = st.selectbox(
                "HSA Coverage Type",
                options=["Self-only", "Family"],
                key=f"{spouse_key}_hsa_coverage",
            )
            _, _, hsa_limit = get_hsa_limit(age, coverage)
            st.caption(f"Annual limit estimate: ${hsa_limit:,.0f}")
            accounts["hsa"] = {
                "name": "HSA",
                "balance": st.number_input(
                    "HSA Balance ($)",
                    min_value=0.0,
                    value=0.0,
                    step=500.0,
                    key=f"{spouse_key}_hsa_bal",
                ),
                "contrib": st.number_input(
                    "HSA Annual Contribution ($)",
                    min_value=0.0,
                    value=0.0,
                    step=250.0,
                    key=f"{spouse_key}_hsa_cont",
                ),
                "rate": st.number_input(
                    "HSA Growth Rate (%)",
                    min_value=0.0,
                    max_value=15.0,
                    value=6.0,
                    step=0.1,
                    key=f"{spouse_key}_hsa_rate",
                ),
                "employer_match": 0.0,
            }

    with col_b:
        use_trad_401k = st.checkbox("Use Traditional 401(k)", value=False, key=f"{spouse_key}_use_traditional_401k")
        if use_trad_401k:
            _, _, k_limit = get_401k_limits(age)
            st.caption(f"Annual employee limit estimate: ${k_limit:,.0f}")
            accounts["trad_401k"] = {
                "name": "Traditional 401(k)",
                "balance": st.number_input(
                    "Traditional 401(k) Balance ($)",
                    min_value=0.0,
                    value=0.0,
                    step=1000.0,
                    key=f"{spouse_key}_trad_401k_bal",
                ),
                "contrib": st.number_input(
                    "Traditional 401(k) Annual Contribution ($)",
                    min_value=0.0,
                    value=0.0,
                    step=500.0,
                    key=f"{spouse_key}_trad_401k_cont",
                ),
                "employer_match": st.number_input(
                    "Traditional 401(k) Employer Match ($)",
                    min_value=0.0,
                    value=0.0,
                    step=500.0,
                    key=f"{spouse_key}_trad_401k_match",
                ),
                "rate": st.number_input(
                    "Traditional 401(k) Growth Rate (%)",
                    min_value=0.0,
                    max_value=15.0,
                    value=7.0,
                    step=0.1,
                    key=f"{spouse_key}_trad_401k_rate",
                ),
            }

        use_roth_401k = st.checkbox("Use Roth 401(k)", value=False, key=f"{spouse_key}_use_roth_401k")
        if use_roth_401k:
            _, _, k_limit = get_401k_limits(age)
            st.caption(f"Annual employee limit estimate: ${k_limit:,.0f}")
            accounts["roth_401k"] = {
                "name": "Roth 401(k)",
                "balance": st.number_input(
                    "Roth 401(k) Balance ($)",
                    min_value=0.0,
                    value=0.0,
                    step=1000.0,
                    key=f"{spouse_key}_roth_401k_bal",
                ),
                "contrib": st.number_input(
                    "Roth 401(k) Annual Contribution ($)",
                    min_value=0.0,
                    value=0.0,
                    step=500.0,
                    key=f"{spouse_key}_roth_401k_cont",
                ),
                "rate": st.number_input(
                    "Roth 401(k) Growth Rate (%)",
                    min_value=0.0,
                    max_value=15.0,
                    value=7.0,
                    step=0.1,
                    key=f"{spouse_key}_roth_401k_rate",
                ),
                "employer_match": 0.0,
            }

        use_brokerage = st.checkbox("Use Taxable Brokerage", value=False, key=f"{spouse_key}_use_brokerage")
        if use_brokerage:
            accounts["brokerage"] = {
                "name": "Brokerage",
                "balance": st.number_input(
                    "Brokerage Balance ($)",
                    min_value=0.0,
                    value=0.0,
                    step=1000.0,
                    key=f"{spouse_key}_brok_bal",
                ),
                "contrib": st.number_input(
                    "Brokerage Annual Contribution ($)",
                    min_value=0.0,
                    value=0.0,
                    step=500.0,
                    key=f"{spouse_key}_brok_cont",
                ),
                "rate": st.number_input(
                    "Brokerage Growth Rate (%)",
                    min_value=0.0,
                    max_value=15.0,
                    value=6.0,
                    step=0.1,
                    key=f"{spouse_key}_brok_rate",
                ),
                "employer_match": 0.0,
            }

    return age, accounts

# ==========================================================
# APPLY QUEUED SCENARIO BEFORE WIDGETS
# ==========================================================
apply_queued_scenario_if_needed()

# ==========================================================
# RESTORE AUTH SESSION
# ==========================================================
current_user = get_current_user()
if current_user:
    st.session_state.user_logged_in = True
    st.session_state.user_email = current_user.email
    st.session_state.user_id = current_user.id
    ensure_user_profile(current_user.id, current_user.email)
    refresh_paid_status()

# ==========================================================
# HANDLE STRIPE RETURN PAGE
# ==========================================================
query_params = st.query_params

if query_params.get("checkout") == "success":
    refresh_paid_status()
    st.session_state._checkout_url = None
    st.session_state._checkout_user_id = None

    if st.session_state.is_paid_user:
        st.success("Payment confirmed. Your Pro access is active.")
    else:
        st.info("Payment completed. Your webhook may still be updating your account. Refresh in a few seconds if needed.")

if query_params.get("checkout") == "cancel":
    st.info("Checkout was canceled.")

# ==========================================================
# HEADER
# ==========================================================
st.title("Retirement Audit App 🚀")
st.subheader("Retirement planning, projections, scenarios, and AI guidance")

if st.session_state.get("_scenario_loaded_message"):
    st.success(st.session_state["_scenario_loaded_message"])
    st.session_state["_scenario_loaded_message"] = None

# ==========================================================
# ACCOUNT SECTION
# ==========================================================
# ==========================================================
# ACCOUNT SECTION
# ==========================================================
st.markdown("---")
st.subheader("Account")

if st.session_state.user_logged_in and st.session_state.user_email:
    if st.session_state.is_paid_user:
        st.success(f"Logged in as {st.session_state.user_email} • Pro User")
    else:
        st.info(f"Logged in as {st.session_state.user_email} • Free Account")

    col_account1, col_account2 = st.columns(2)

    with col_account1:
        if st.button("Log Out", use_container_width=True):
            sign_out_user()
            st.rerun()

    with col_account2:
        if st.session_state.is_paid_user:
            try:
                profile, profile_error = get_user_profile(st.session_state.user_id)

                if profile_error:
                    st.error("Could not load billing profile.")
                else:
                    stripe_customer_id = profile.get("stripe_customer_id") if profile else None

                    if stripe_customer_id:
                        portal_url = create_portal_session(stripe_customer_id)
                        st.link_button(
                            "Manage Billing / Cancel Subscription",
                            portal_url,
                            use_container_width=True,
                        )
                    else:
                        st.info("Billing portal is not available yet. Please refresh in a moment.")
            except Exception as e:
                st.error(f"Billing portal error: {e}")
        else:
            try:
                checkout_url = get_checkout_url()
                if checkout_url:
                    st.link_button(
                        "Upgrade to Pro • $1.99/month",
                        checkout_url,
                        use_container_width=True,
                    )
                    st.caption("Cancel anytime • First month free with code")
                else:
                    st.info("Could not generate checkout link yet.")
            except Exception as e:
                st.error(f"Checkout error: {e}")

else:
    st.info("Log in or sign up to save scenarios and connect a paid subscription to your account.")

    login_tab, signup_tab = st.tabs(["Log In", "Sign Up"])

    with login_tab:
        login_email = st.text_input("Login Email", key="login_email")
        login_password = st.text_input("Login Password", type="password", key="login_password")

        if st.button("Log In to Account", use_container_width=True):
            if not login_email or not login_password:
                st.error("Please enter both email and password.")
            else:
                response, error = sign_in_user(login_email, login_password)
                if error:
                    st.error(f"Login failed: {error}")
                else:
                    try:
                        user = response.user
                        st.session_state.user_logged_in = True
                        st.session_state.user_email = user.email
                        st.session_state.user_id = user.id
                        ensure_user_profile(user.id, user.email)
                        refresh_paid_status()
                        st.session_state._checkout_url = None
                        st.session_state._checkout_user_id = None
                        st.success("Logged in successfully.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Login worked, but the session could not be loaded: {e}")

    with signup_tab:
        signup_email = st.text_input("Sign Up Email", key="signup_email")
        signup_password = st.text_input("Create Password", type="password", key="signup_password")

        if st.button("Create Account", use_container_width=True):
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
                            ensure_user_profile(user.id, user.email)
                        st.success("Account created. If email confirmation is enabled, confirm your email before logging in.")
                    except Exception:
                        st.success("Account created. If email confirmation is enabled, confirm your email before logging in.")
# ==========================================================
# MAIN INPUTS
# ==========================================================
st.markdown("---")
st.subheader("Retirement Inputs")

retirement_age = st.slider(
    "Target Retirement Age",
    min_value=40,
    max_value=80,
    value=65,
    step=1,
    key="retirement_age",
)

sp1_age, sp1_accounts = build_spouse_accounts("Spouse 1", "spouse1")
st.markdown("---")
sp2_age, sp2_accounts = build_spouse_accounts("Spouse 2", "spouse2")

accounts = {
    "spouse1": sp1_accounts,
    "spouse2": sp2_accounts,
}
# ==========================================================
# RETIREMENT INCOME
# ==========================================================
st.markdown("---")
st.subheader("Income Sources in Retirement")

st.markdown("### Social Security Estimator")
st.markdown(
    "Enter average annual earnings for a rough estimate of annual Social Security at Full Retirement Age."
)

col_est1, col_est2 = st.columns(2)
with col_est1:
    avg_annual_earnings_sp1 = st.number_input(
        "Spouse 1 Average Annual Earnings ($)",
        min_value=0,
        max_value=300000,
        value=60000,
        step=1000,
        key="avg_earn_sp1",
    )
with col_est2:
    avg_annual_earnings_sp2 = st.number_input(
        "Spouse 2 Average Annual Earnings ($)",
        min_value=0,
        max_value=300000,
        value=0,
        step=1000,
        key="avg_earn_sp2",
    )

est_ss_sp1 = estimate_ss_pia(avg_annual_earnings_sp1)
est_ss_sp2 = estimate_ss_pia(avg_annual_earnings_sp2)

col_ss_metric1, col_ss_metric2 = st.columns(2)
with col_ss_metric1:
    st.metric("Estimated Annual SS at FRA - Spouse 1", f"${est_ss_sp1:,.0f}")
with col_ss_metric2:
    st.metric("Estimated Annual SS at FRA - Spouse 2", f"${est_ss_sp2:,.0f}")

st.info("This is a simplified estimate. For an exact estimate, use ssa.gov/myaccount.")

use_manual_ss = st.checkbox(
    "Use Social Security manual inputs / override",
    value=False,
    key="use_manual_ss",
)

if use_manual_ss:
    st.markdown("### Social Security Manual Inputs")
    col_ss1, col_ss2 = st.columns(2)

    with col_ss1:
        ss_start_sp1 = st.slider(
            "Claim Age - Spouse 1",
            62,
            70,
            67,
            key="ss_start_sp1",
        )
        ss_annual_sp1 = st.number_input(
            "Annual SS at Claim Age - Spouse 1 ($)",
            min_value=0,
            max_value=100000,
            value=int(est_ss_sp1),
            step=1000,
            key="ss_ann_sp1",
        )

    with col_ss2:
        ss_start_sp2 = st.slider(
            "Claim Age - Spouse 2",
            62,
            70,
            67,
            key="ss_start_sp2",
        )
        ss_annual_sp2 = st.number_input(
            "Annual SS at Claim Age - Spouse 2 ($)",
            min_value=0,
            max_value=100000,
            value=int(est_ss_sp2),
            step=1000,
            key="ss_ann_sp2",
        )
else:
    ss_start_sp1 = 67
    ss_start_sp2 = 67
    ss_annual_sp1 = est_ss_sp1
    ss_annual_sp2 = est_ss_sp2

use_pension = st.checkbox(
    "Include Pension / Defined Benefit",
    value=False,
    key="use_pension",
)

if use_pension:
    st.markdown("### Pension / Defined Benefit")
    col_pen1, col_pen2 = st.columns(2)

    with col_pen1:
        pension_annual_sp1 = st.number_input(
            "Annual Pension - Spouse 1 ($)",
            min_value=0,
            value=0,
            step=1000,
            key="pen_sp1",
        )
        pension_cola_sp1 = (
            st.slider(
                "Pension COLA % - Spouse 1",
                min_value=0.0,
                max_value=5.0,
                value=2.0,
                step=0.1,
                key="pen_cola_sp1",
            )
            / 100
        )

    with col_pen2:
        pension_annual_sp2 = st.number_input(
            "Annual Pension - Spouse 2 ($)",
            min_value=0,
            value=0,
            step=1000,
            key="pen_sp2",
        )
        pension_cola_sp2 = (
            st.slider(
                "Pension COLA % - Spouse 2",
                min_value=0.0,
                max_value=5.0,
                value=2.0,
                step=0.1,
                key="pen_cola_sp2",
            )
            / 100
        )
else:
    pension_annual_sp1 = 0
    pension_cola_sp1 = 0.0
    pension_annual_sp2 = 0
    pension_cola_sp2 = 0.0

# ==========================================================
# HOME EQUITY
# ==========================================================
st.markdown("---")
st.subheader("Home Equity")

use_home_equity = st.checkbox(
    "Include Home Equity section",
    value=False,
    key="use_home_equity",
)

if use_home_equity:
    home_value = st.number_input(
        "Current Home Value ($)",
        min_value=0.0,
        value=0.0,
        format="%.0f",
        key="home_value",
    )
    mortgage_balance = st.number_input(
        "Remaining Mortgage ($)",
        min_value=0.0,
        value=0.0,
        format="%.0f",
        key="mortgage_balance",
    )
    home_appreciation = (
        st.slider(
            "Annual Home Appreciation (%)",
            min_value=0.0,
            max_value=10.0,
            value=3.0,
            step=0.1,
            key="home_appreciation_pct",
        )
        / 100
    )
    include_home = st.checkbox(
        "Include Home Equity in Graph & Net Worth",
        value=True,
        key="include_home",
    )
else:
    home_value = 0.0
    mortgage_balance = 0.0
    home_appreciation = 0.0
    include_home = False

# ==========================================================
# MORTGAGE PAYOFF CALCULATOR
# ==========================================================
st.markdown("---")
st.subheader("Mortgage Payoff Calculator")

use_mortgage_calc = st.checkbox(
    "Include Mortgage Payoff Calculator",
    value=False,
    key="use_mortgage_calc",
)

mort_principal = float(mortgage_balance)
mort_rate_pct = 6.5
mort_rate_annual = mort_rate_pct / 100
mort_years = 30
monthly_payment = 1500.0
extra_monthly = 0.0

schedule_no_extra = {
    "amortizes": False,
    "months": None,
    "interest": 0.0,
    "balances": [mort_principal],
}
schedule_with_extra = {
    "amortizes": False,
    "months": None,
    "interest": 0.0,
    "balances": [mort_principal],
}

if use_mortgage_calc:
    mort_principal = st.number_input(
        "Current Mortgage Balance ($)",
        min_value=0.0,
        value=float(mortgage_balance),
        format="%.2f",
        key="mort_principal",
    )
    mort_rate_pct = st.number_input(
        "Annual Interest Rate (%)",
        min_value=0.0,
        max_value=20.0,
        value=6.5,
        step=0.125,
        key="mort_rate_pct",
    )
    mort_rate_annual = mort_rate_pct / 100

    mort_years = st.number_input(
        "Remaining Term (Years)",
        min_value=1,
        max_value=40,
        value=30,
        step=1,
        key="mort_years",
    )

    monthly_payment = st.number_input(
        "Standard Monthly Payment ($)",
        min_value=0.0,
        value=1500.0,
        format="%.2f",
        key="monthly_payment",
    )

    extra_monthly = st.number_input(
        "Extra Monthly Payment ($)",
        min_value=0.0,
        value=0.0,
        format="%.2f",
        key="extra_monthly",
    )

    schedule_no_extra = amortization_schedule(
        mort_principal,
        mort_rate_annual,
        monthly_payment,
        0.0,
    )
    schedule_with_extra = amortization_schedule(
        mort_principal,
        mort_rate_annual,
        monthly_payment,
        extra_monthly,
    )

    if not schedule_no_extra["amortizes"]:
        st.error("The standard monthly payment is too low to amortize this mortgage.")
    else:
        date_no = datetime.now() + timedelta(days=schedule_no_extra["months"] * 30)

        if schedule_with_extra["amortizes"]:
            date_yes = datetime.now() + timedelta(days=schedule_with_extra["months"] * 30)
            savings = schedule_no_extra["interest"] - schedule_with_extra["interest"]

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Payoff Date (no extra)", date_no.strftime("%b %Y"))
            with col2:
                st.metric("Payoff Date (with extra)", date_yes.strftime("%b %Y"))
            with col3:
                st.metric("Interest Savings", f"${savings:,.2f}")
        else:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Payoff Date (no extra)", date_no.strftime("%b %Y"))
            with col2:
                st.warning("Extra-payment scenario does not amortize with the values entered.")

# ==========================================================
# RETIREMENT PROJECTIONS
# ==========================================================
total_invest = 0.0
max_years = 0

spouse_ages = {
    "spouse1": sp1_age,
    "spouse2": sp2_age,
}

for spouse_key, spouse_accounts in accounts.items():
    current_age = spouse_ages.get(spouse_key, 30)
    years_to_retirement = max(retirement_age - current_age, 0)
    max_years = max(max_years, years_to_retirement)

    for _, acc in spouse_accounts.items():
        annual_contrib = float(acc.get("contrib", 0.0)) + float(acc.get("employer_match", 0.0))
        annual_rate = float(acc.get("rate", 7.0)) / 100
        projected = future_value(
            balance=float(acc.get("balance", 0.0)),
            annual_contrib=annual_contrib,
            annual_rate=annual_rate,
            years=years_to_retirement,
        )
        total_invest += projected

if include_home:
    home_proj_value = home_value * (1 + home_appreciation) ** max_years
    if use_mortgage_calc and schedule_no_extra["amortizes"]:
        mortgage_balance_at_retirement = projected_mortgage_balance(
            schedule_no_extra["balances"],
            max_years,
        )
    else:
        mortgage_balance_at_retirement = mortgage_balance

    home_proj_equity = max(home_proj_value - mortgage_balance_at_retirement, 0.0)
else:
    home_proj_value = 0.0
    mortgage_balance_at_retirement = 0.0
    home_proj_equity = 0.0

total_nw = total_invest + (home_proj_equity if include_home else 0.0)

# ==========================================================
# KEY OUTPUTS
# ==========================================================
st.markdown("---")
st.subheader("Key Outputs")

col_out1, col_out2, col_out3 = st.columns(3)
with col_out1:
    st.metric("Projected Investments at Retirement", f"${total_invest:,.0f}")
with col_out2:
    st.metric("Projected Home Equity at Retirement", f"${home_proj_equity:,.0f}")
with col_out3:
    st.metric("Projected Total Net Worth", f"${total_nw:,.0f}")

# ==========================================================
# GROWTH OVER TIME
# ==========================================================
st.markdown("---")
st.subheader("Growth Over Time")

years_arr = np.arange(0, max_years + 6)
invest_growth = np.zeros(len(years_arr))
home_growth = np.zeros(len(years_arr))

for y_idx, y in enumerate(years_arr):
    yearly_invest_total = 0.0

    for spouse_key, spouse_accounts in accounts.items():
        current_age = spouse_ages.get(spouse_key, 30)
        years_to_retirement = max(retirement_age - current_age, 0)
        effective_years = min(y, years_to_retirement)

        for _, acc in spouse_accounts.items():
            annual_contrib = float(acc.get("contrib", 0.0)) + float(acc.get("employer_match", 0.0))
            annual_rate = float(acc.get("rate", 7.0)) / 100
            balance = float(acc.get("balance", 0.0))

            yearly_invest_total += future_value(
                balance,
                annual_contrib,
                annual_rate,
                effective_years,
            )

    invest_growth[y_idx] = yearly_invest_total

    if include_home:
        future_home_value = home_value * (1 + home_appreciation) ** y

        if use_mortgage_calc and schedule_no_extra["amortizes"]:
            future_mortgage_balance = projected_mortgage_balance(
                schedule_no_extra["balances"],
                y,
            )
        else:
            future_mortgage_balance = mortgage_balance

        home_growth[y_idx] = max(future_home_value - future_mortgage_balance, 0.0)

total_growth = invest_growth + (home_growth if include_home else 0.0)

fig, ax = plt.subplots(figsize=(12, 6))
ax.plot(years_arr, invest_growth, label="Investments", linewidth=3)
if include_home:
    ax.plot(years_arr, home_growth, label="Home Equity", linewidth=3)
ax.plot(years_arr, total_growth, label="Total Net Worth", linewidth=4, linestyle="--")
ax.set_xlabel("Years from Now")
ax.set_ylabel("Value ($)")
ax.legend()
ax.grid(True, alpha=0.3)
st.pyplot(fig)

# ==========================================================
# RETIREMENT WITHDRAWAL SIMULATION
# ==========================================================
st.markdown("---")
st.subheader("Retirement Withdrawal Simulation")

wd_rate_pct = st.slider(
    "Annual Withdrawal Rate from Investments (%)",
    min_value=3.0,
    max_value=12.0,
    value=4.5,
    step=0.1,
    help="Lower rates are generally safer for longer retirements.",
    key="wd_rate_pct",
)
wd_rate = wd_rate_pct / 100

post_growth_pct = st.slider(
    "Expected Annual Portfolio Growth in Retirement (%)",
    min_value=0.0,
    max_value=12.0,
    value=6.0,
    step=0.1,
    help="This is a simplified assumption.",
    key="post_growth_pct",
)
post_growth = post_growth_pct / 100

wd_years_max = 60
starting_balance = invest_growth[max_years] if len(invest_growth) > max_years else invest_growth[-1]

if starting_balance <= 0:
    st.warning("No investments projected at retirement — can't simulate withdrawals.")
else:
    annual_wd = starting_balance * wd_rate
    st.write(
        f"**First-year withdrawal from investments:** ${annual_wd:,.0f} "
        f"({wd_rate_pct:.1f}% of starting balance)"
    )

    years_post = np.arange(0, wd_years_max + 1)
    balances = [starting_balance]
    depleted_year = None

    for y in range(1, len(years_post)):
        new_bal = balances[-1] * (1 + post_growth) - annual_wd
        if new_bal <= 0:
            depleted_year = y
            balances.append(0.0)
            break
        balances.append(new_bal)

    if depleted_year is None:
        while len(balances) < len(years_post):
            next_bal = balances[-1] * (1 + post_growth) - annual_wd
            balances.append(max(next_bal, 0.0))

    fig_wd, ax_wd = plt.subplots(figsize=(12, 6))
    ax_wd.plot(years_post[:len(balances)], balances, label="Portfolio Balance", linewidth=3)
    ax_wd.axhline(starting_balance, linestyle="--", label="Starting Balance")

    if depleted_year is not None and depleted_year <= wd_years_max:
        ax_wd.axvline(depleted_year, linestyle="--", label="Depletion Point")

    ax_wd.set_xlabel("Years in Retirement")
    ax_wd.set_ylabel("Balance ($)")
    ax_wd.set_title(
        f"Withdrawal at {wd_rate_pct:.1f}% with {post_growth_pct:.1f}% Annual Growth"
    )
    ax_wd.legend()
    ax_wd.grid(True, alpha=0.3)
    st.pyplot(fig_wd)

# ==========================================================
# SAVE / LOAD SCENARIOS
# ==========================================================
st.markdown("---")
st.subheader("Save or Load Your Scenario")

if not st.session_state.user_logged_in:
    st.info("Save and load scenarios is a Pro feature. Create an account and upgrade to unlock it.")
elif not user_can_save_scenarios():
    st.warning("Save and load scenarios is available on Pro.")
    try:
        checkout_url = get_checkout_url()
        if checkout_url:
            st.link_button(
                "Upgrade to Pro for Save/Load",
                checkout_url,
                use_container_width=True,
            )
        else:
            st.info("Checkout link unavailable right now.")
    except Exception as e:
        st.error(f"Checkout error: {e}")
else:
    scenario_name = st.text_input(
        "Scenario Name",
        value=st.session_state.get("scenario_name", "My Scenario"),
        key="scenario_name",
    )

    col_save_1, col_save_2 = st.columns(2)

    with col_save_1:
        if st.button("Save Scenario", use_container_width=True):
            if not scenario_name.strip():
                st.error("Please enter a scenario name.")
            else:
                scenario_data = collect_app_state()
                result, error = save_scenario_to_supabase(
                    user_id=st.session_state.user_id,
                    scenario_name=scenario_name.strip(),
                    scenario_data=scenario_data,
                )

                if error:
                    st.error(f"Save failed: {error}")
                else:
                    st.success("Scenario saved successfully.")

    with col_save_2:
        if st.button("Refresh Saved Scenarios", use_container_width=True):
            st.rerun()

    scenarios, error = get_user_scenarios(st.session_state.user_id)

    if error:
        st.error(f"Could not load saved scenarios: {error}")
    elif scenarios:
        scenario_options = {
            f"{item['scenario_name']} ({item.get('updated_at', 'saved')})": item
            for item in scenarios
        }

        selected_scenario_label = st.selectbox(
            "Choose a saved scenario to load",
            options=list(scenario_options.keys()),
            key="saved_scenario_select",
        )

        if st.button("Load Selected Scenario", use_container_width=True):
            selected_scenario = scenario_options[selected_scenario_label]
            scenario_data = selected_scenario.get("scenario_data", {})

            if isinstance(scenario_data, str):
                try:
                    scenario_data = json.loads(scenario_data)
                except Exception:
                    scenario_data = {}

            queue_scenario_for_load(
                saved_data=scenario_data,
                scenario_name=selected_scenario.get("scenario_name", "Scenario"),
            )
    else:
        st.info("No saved scenarios yet.")

# ==========================================================
# AI SECTION
# ==========================================================
st.markdown("---")
st.subheader("Ask AI About Your Retirement Plan")
st.caption("For educational purposes only. This is not financial, tax, or legal advice.")

st.markdown(
    """
### Pro includes
- Unlimited AI retirement insights
- Save and load scenarios
- A faster planning workflow for comparing ideas
"""
)

if st.session_state.is_paid_user:
    st.success("Pro access active: unlimited AI questions.")
else:
    questions_left = max(
        st.session_state.ai_limit - st.session_state.ai_question_count,
        0,
    )

    if not st.session_state.user_logged_in:
        st.info(f"You have {questions_left} free AI question(s) remaining as a guest.")
    else:
        if questions_left > 0:
            st.info(f"You have {questions_left} free AI question(s) remaining.")
        else:
            st.warning("You’ve used your free AI questions. Upgrade to Pro for unlimited AI.")

ai_question = st.text_area(
    "Type your retirement question here",
    placeholder="Example: Am I on track to retire by 65?",
    key="ai_question_input",
)

col_ai1, col_ai2 = st.columns(2)

with col_ai1:
    ask_ai_clicked = st.button("Get AI Retirement Insight", use_container_width=True)

with col_ai2:
    if st.session_state.user_logged_in and not st.session_state.is_paid_user:
        try:
            checkout_url = get_checkout_url()
            if checkout_url:
                st.link_button(
                    "Upgrade for Unlimited AI",
                    checkout_url,
                    use_container_width=True,
                )
            else:
                st.info("Checkout link unavailable right now.")
        except Exception as e:
            st.error(f"Checkout error: {e}")

if ask_ai_clicked:
    can_ask, message = user_can_ask_ai()

    if not can_ask:
        if message == "Create an account to continue.":
            st.error("You’ve used your 3 free AI questions. Create an account and upgrade to keep going.")
        else:
            st.error("Unlimited AI is a Pro feature. Upgrade to continue.")
    elif not ai_question.strip():
        st.error("Please type a question before clicking Get AI Retirement Insight.")
    else:
        try:
            with st.spinner("Thinking..."):
                ai_response = get_real_ai_response(
                    user_question=ai_question,
                    total_invest=total_invest,
                    total_nw=total_nw,
                    retirement_age=retirement_age,
                    include_home=include_home,
                    home_proj_equity=home_proj_equity,
                    wd_rate_pct=wd_rate_pct,
                    post_growth_pct=post_growth_pct,
                    ss_annual_sp1=ss_annual_sp1,
                    ss_annual_sp2=ss_annual_sp2,
                    pension_annual_sp1=pension_annual_sp1,
                    pension_annual_sp2=pension_annual_sp2,
                )

            if not st.session_state.is_paid_user:
                st.session_state.ai_question_count += 1

            st.session_state.ai_chat_history.append(
                {
                    "question": ai_question,
                    "answer": ai_response,
                }
            )
            st.rerun()

        except Exception as e:
            st.error(f"AI request failed: {e}")

if st.session_state.ai_chat_history:
    st.markdown("### AI Conversation")
    for chat in reversed(st.session_state.ai_chat_history):
        with st.container():
            st.markdown(f"**Question:** {chat['question']}")
            st.markdown(chat["answer"])
            st.markdown("---")

# ==========================================================
# IMPORTANT INFO
# ==========================================================
st.markdown("---")
st.subheader("Important Information")

with st.expander("Disclaimer", expanded=False):
    st.markdown(
        """
This tool is provided for educational and informational purposes only and does not constitute
financial, investment, tax, or legal advice.

All projections and estimates are based on user inputs and assumptions that may not reflect
real-world outcomes. Actual results will vary based on market conditions, individual circumstances,
taxes, inflation, and other factors.

You should consult a qualified financial professional before making important financial decisions.
"""
    )

with st.expander("Privacy Notice", expanded=False):
    st.markdown(
        """
We do not ask for or store highly sensitive personal financial information such as account numbers
or Social Security numbers in this calculator.

Any information entered into this tool is used to generate estimates and projections based on
the values you provide.
"""
    )

with st.expander("For Financial Advisors", expanded=False):
    st.markdown(
        """
Are you a licensed financial advisor interested in being featured in this app?

You can reach out to discuss future promotional opportunities:

**Email:** retirementaudit@gmail.com
"""
    )
    