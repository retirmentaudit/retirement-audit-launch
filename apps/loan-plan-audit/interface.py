"""Streamlit screens for Loan Plan Audit."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone

import streamlit as st

from charts import comparison_chart, monthly_bar, payoff_timeline
from checkout import (
    PRICE_SETUP_ERROR,
    PRODUCT,
    checkout_block_reason,
    fulfillment_decision,
    onetime_checkout_params,
)
from copy_text import (
    AI_INSTRUCTIONS,
    AI_LINE,
    ALT_TAGLINE,
    BULLETS,
    CHECKOUT_BUTTON,
    CHECKOUT_DISCLAIMER,
    CTA,
    HEADLINE,
    LANDING_STRIP,
    LINKS,
    LOWEST_TOTAL_CAPTION,
    METHOD_PARAGRAPHS,
    METHOD_UNCERTAIN,
    RESULTS_DISCLAIMER,
    RULES_BANNER,
    SAVE_CHECKLIST,
    SERVICER_QUESTIONS,
    SHORT_DISCLAIMER,
    SOURCES,
    TAGLINE,
    TERMS_CHECKBOX,
    UNLOCK_BUTTON,
    privacy_markdown,
    terms_markdown,
)
from demo import DEMO_EMAIL, DEMO_USER_ID, demo_checkout_session, demo_retrieved_session, query_param
from engine import (
    LOAN_TYPES,
    PLAN_RAP,
    LoanInput,
    ScenarioInput,
    build_audit,
    format_duration,
    lowest_estimated_total,
    make_scenario,
    scenario_from_dict,
    sort_plans,
    validate_scenario,
)
from pdf_report import build_report_pdf
from share_card import render_share_card
from states import STATE_CHOICES, STATE_NAMES, blocked_state_note, normalize_state, paid_report_available, residence_gate
from store import diff_plans, scenario_fingerprint, scenario_row, sort_newest_first, table_missing, unlock_is_active
from theme import THEME_CSS

NAV_ITEMS = (
    "Home",
    "Run the numbers",
    "My scenarios",
    "How we calculate",
    "Ask a question",
    "Sample posts",
    "Disclaimer",
    "Terms",
    "Privacy",
)

WHEN_LABELS = ("Before July 1, 2026", "On or after July 1, 2026", "Not sure")
WHEN_VALUES = {
    "Before July 1, 2026": "no",
    "On or after July 1, 2026": "yes",
    "Not sure": "not_sure",
}
FILING_LABELS = ("Single", "Head of household", "Married filing jointly", "Married filing separately")
FILING_VALUES = {
    "Single": "single",
    "Head of household": "hoh",
    "Married filing jointly": "mfj",
    "Married filing separately": "mfs",
}
NEW_LABELS = ("No", "Yes", "Not sure")
NEW_VALUES = {"No": "no", "Yes": "yes", "Not sure": "not_sure"}
YES_NO = ("No", "Yes")
END_LABELS = {
    "paid_off": "Paid off",
    "pslf": "PSLF",
    "idr_discharge": "Discharge at the payment count",
    "term_complete": "End of the modeled term",
}
SORTS = {
    "Lowest monthly payment now": "monthly",
    "Lowest estimated total paid": "total",
    "Soonest estimated end date": "soonest",
}


@dataclass
class Ctx:
    supabase: object
    stripe: object
    price_id: str | None
    app_url: str
    local_sandbox: bool
    openai_client: object | None


def _ensure(key, value):
    if key not in st.session_state:
        st.session_state[key] = value


# Widget keys disappear when that step is not on screen. saved_inputs keeps them.
_INPUT_DEFAULTS = {
    "on_save": "No",
    "pslf_credited": 0,
    "idr_credited": 0,
    "new_borrower": "No",
    "agi": 0.0,
    "filing": "Single",
    "spouse_agi": 0.0,
    "dependents": 0,
    "family_size": 1,
    "residence": "",
    "federal_tax": 22.0,
    "state_tax": 0.0,
    "pslf_job": "No",
    "raise_pct": 3.0,
    "inflation_pct": 2.5,
    "autopay": False,
    "scenario_name": "My scenario",
}
_LOAN_PREFIXES = ("loan_balance_", "loan_rate_", "loan_type_", "loan_when_", "loan_parent_")


def _init():
    _ensure("loans", [{"id": 0}])
    _ensure("show_results", False)
    _ensure("wizard_step", 1)
    _ensure("user_logged_in", False)
    _ensure("user_email", None)
    _ensure("user_id", None)
    _ensure("unlock_row", None)
    _ensure("agreed_terms", False)
    _ensure("nav", "Home")
    _ensure("saved_inputs", {})


# Keys whose widgets were actually drawn this run. Unmounted widgets must not
# overwrite the copy we kept from the step where they were on screen.
_RENDERED: set[str] = set()


def _prime(key, default=None):
    """Put a stored answer back before the widget for that step is created."""
    _RENDERED.add(key)
    if key in st.session_state:
        return
    saved = st.session_state.get("saved_inputs") or {}
    if key in saved:
        st.session_state[key] = saved[key]
    elif default is not None:
        st.session_state[key] = default
    elif key in _INPUT_DEFAULTS:
        st.session_state[key] = _INPUT_DEFAULTS[key]


def _field(key, default=None):
    saved = st.session_state.get("saved_inputs") or {}
    if key not in _RENDERED and key in saved:
        return saved[key]
    if key in st.session_state:
        return st.session_state[key]
    if key in saved:
        return saved[key]
    if default is not None:
        return default
    return _INPUT_DEFAULTS.get(key)


def _snapshot_inputs():
    saved = dict(st.session_state.get("saved_inputs") or {})
    for key in _RENDERED:
        if key in st.session_state:
            saved[key] = st.session_state[key]
    st.session_state["saved_inputs"] = saved


def _go(page: str):
    st.session_state["pending_nav"] = page


def _consume_nav():
    pending = st.session_state.pop("pending_nav", None)
    if pending in NAV_ITEMS:
        st.session_state.nav = pending


def _money(amount) -> str:
    if amount is None:
        return "—"
    if abs(float(amount) - round(float(amount))) < 0.005:
        return f"${float(amount):,.0f}"
    return f"${float(amount):,.2f}"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _scenario_from_widgets() -> ScenarioInput:
    loans = []
    for index in range(len(st.session_state.loans)):
        loan_type = _field(f"loan_type_{index}", "Direct Unsubsidized")
        loans.append(
            LoanInput(
                balance=float(_field(f"loan_balance_{index}", 0) or 0),
                rate_pct=float(_field(f"loan_rate_{index}", 0) or 0),
                loan_type=loan_type,
                disbursed_on_or_after_july_2026=WHEN_VALUES.get(_field(f"loan_when_{index}", "Before July 1, 2026"), "no"),
                repaid_parent_plus=bool(_field(f"loan_parent_{index}", False)) and loan_type == "Consolidation",
            )
        )
    return ScenarioInput(
        loans=tuple(loans),
        agi=float(_field("agi", 0) or 0),
        filing_status=FILING_VALUES.get(_field("filing", "Single"), "single"),
        spouse_agi=float(_field("spouse_agi", 0) or 0),
        dependents=int(_field("dependents", 0) or 0),
        family_size=int(_field("family_size", 1) or 1),
        state=_field("residence", "") or "",
        pslf_job=_field("pslf_job", "No") == "Yes",
        annual_raise=float(_field("raise_pct", 3) or 0) / 100,
        poverty_inflation=float(_field("inflation_pct", 2.5) or 0) / 100,
        autopay=bool(_field("autopay", False)),
        federal_tax_pct=float(_field("federal_tax", 22) or 0) / 100,
        state_tax_pct=float(_field("state_tax", 0) or 0) / 100,
        extra_monthly=0.0,
        pslf_months_credited=int(_field("pslf_credited", 0) or 0),
        idr_months_credited=int(_field("idr_credited", 0) or 0),
        new_borrower_after_2014=NEW_VALUES.get(_field("new_borrower", "No"), "no"),
        on_save=_field("on_save", "No") == "Yes",
        start_date=date(2026, 12, 1),
    )


def _apply_what_if(scenario: ScenarioInput) -> ScenarioInput:
    scale = float(st.session_state.get("what_income") or 1.0)
    filing = st.session_state.get("what_filing") or scenario.filing_status
    return replace(
        scenario,
        agi=max(0.0, scenario.agi * scale),
        spouse_agi=max(0.0, float(st.session_state.get("what_spouse") if "what_spouse" in st.session_state else scenario.spouse_agi) * scale),
        filing_status=filing,
        dependents=int(st.session_state.get("what_deps") if "what_deps" in st.session_state else scenario.dependents),
        annual_raise=float(st.session_state.get("what_raise") if "what_raise" in st.session_state else scenario.annual_raise * 100) / 100,
        extra_monthly=float(st.session_state.get("what_extra") or 0),
        pslf_job=bool(st.session_state.get("what_pslf") if "what_pslf" in st.session_state else scenario.pslf_job),
        autopay=bool(st.session_state.get("what_autopay") if "what_autopay" in st.session_state else scenario.autopay),
    )


def _footer():
    st.markdown(f"<div class='fine-print'>{SHORT_DISCLAIMER}</div>", unsafe_allow_html=True)
    st.caption("Loan Plan Audit · an independent calculator · loanplanaudit.com")


def _rules():
    st.markdown(f"<div class='rules'>{RULES_BANNER}</div>", unsafe_allow_html=True)


def _auth_user(response):
    if response is None:
        return None
    user = getattr(response, "user", None)
    if user is None and isinstance(response, dict):
        user = response.get("user")
    return user


def _auth_session(response):
    if response is None:
        return None
    session = getattr(response, "session", None)
    if session is None and isinstance(response, dict):
        session = response.get("session")
    return session


def _remember(response):
    session = _auth_session(response)
    if not session:
        return
    access = session.get("access_token") if isinstance(session, dict) else getattr(session, "access_token", None)
    refresh = session.get("refresh_token") if isinstance(session, dict) else getattr(session, "refresh_token", None)
    if access and refresh:
        st.session_state["_sb_access_token"] = access
        st.session_state["_sb_refresh_token"] = refresh


def _restore(ctx: Ctx):
    access = st.session_state.get("_sb_access_token")
    refresh = st.session_state.get("_sb_refresh_token")
    if not access or not refresh or ctx.local_sandbox:
        return
    try:
        ctx.supabase.auth.set_session(access, refresh)
    except Exception:
        pass


def _load_unlock(ctx: Ctx):
    user_id = st.session_state.get("user_id")
    if not user_id:
        st.session_state.unlock_row = None
        return
    try:
        result = ctx.supabase.table("unlocks").select("*").eq("user_id", user_id).eq("product", PRODUCT).execute()
        rows = result.data or []
        st.session_state.unlock_row = rows[0] if rows and unlock_is_active(rows[0]) else None
    except Exception:
        st.session_state.unlock_row = st.session_state.get("unlock_row")


def _save_unlock(ctx: Ctx, update: dict):
    try:
        existing = (
            ctx.supabase.table("unlocks").select("id").eq("user_id", update["user_id"]).eq("product", PRODUCT).execute()
        )
        if existing.data:
            ctx.supabase.table("unlocks").update(update).eq("user_id", update["user_id"]).eq("product", PRODUCT).execute()
        else:
            ctx.supabase.table("unlocks").insert(update).execute()
    except Exception as exc:
        st.error(f"The payment was confirmed, but the unlock could not be saved: {exc}")
        return
    st.session_state.unlock_row = update


def _complete_login(response):
    user = _auth_user(response)
    if user is None:
        st.error("Login succeeded, but no account was returned.")
        return
    _remember(response)
    st.session_state.user_logged_in = True
    st.session_state.user_email = getattr(user, "email", None) or (user.get("email") if isinstance(user, dict) else None)
    st.session_state.user_id = getattr(user, "id", None) or (user.get("id") if isinstance(user, dict) else None)
    st.session_state["_reload_unlock"] = True
    st.rerun()


def _sign_in(ctx: Ctx, email: str, password: str):
    if ctx.local_sandbox:
        from types import SimpleNamespace

        user = SimpleNamespace(id=DEMO_USER_ID, email=email)
        session = SimpleNamespace(access_token="demo-access", refresh_token="demo-refresh")
        return SimpleNamespace(user=user, session=session), None
    try:
        return ctx.supabase.auth.sign_in_with_password({"email": email, "password": password}), None
    except Exception as exc:
        return None, str(exc)


def _sign_up(ctx: Ctx, email: str, password: str):
    if ctx.local_sandbox:
        return _sign_in(ctx, email, password)
    try:
        return ctx.supabase.auth.sign_up({"email": email, "password": password}), None
    except Exception as exc:
        return None, str(exc)


def _sign_out(ctx: Ctx):
    try:
        ctx.supabase.auth.sign_out()
    except Exception:
        pass
    for key in ("user_logged_in",):
        st.session_state[key] = False
    for key in ("user_email", "user_id", "unlock_row", "_sb_access_token", "_sb_refresh_token", "_checkout_url"):
        st.session_state[key] = None


def _login_failure(error: str) -> str:
    text = (error or "").lower()
    if "not confirmed" in text or "email_not_confirmed" in text:
        return "Confirm your email first, then log in. After you log in, checkout can continue. No subscription."
    return f"Login failed: {error}"


def render_auth(ctx: Ctx, prefix: str):
    login_tab, signup_tab = st.tabs(["Log in", "Create account"])
    with login_tab:
        email = st.text_input("Email", key=f"{prefix}_login_email")
        password = st.text_input("Password", type="password", key=f"{prefix}_login_password")
        if st.button("Log in", key=f"{prefix}_login_button"):
            if not email or not password:
                st.error("Enter both email and password.")
            else:
                response, error = _sign_in(ctx, email.strip(), password)
                if error:
                    st.error(_login_failure(error))
                else:
                    _complete_login(response)
    with signup_tab:
        email = st.text_input("Email", key=f"{prefix}_signup_email")
        password = st.text_input("Password", type="password", key=f"{prefix}_signup_password")
        if st.button("Create account", key=f"{prefix}_signup_button"):
            if not email or not password:
                st.error("Enter both email and password.")
            else:
                response, error = _sign_up(ctx, email.strip(), password)
                if error:
                    st.error(f"Sign up failed: {error}")
                elif _auth_user(response) is not None and not _auth_session(response):
                    st.info("Check your email and confirm the account, then log in. No subscription.")
                else:
                    _complete_login(response)


def _checkout_url(ctx: Ctx, state: str) -> str | None:
    reason = checkout_block_reason(
        state=state,
        agreed_to_terms=bool(st.session_state.get("agreed_terms")),
        price_id=ctx.price_id,
        logged_in=bool(st.session_state.get("user_logged_in")),
    )
    if reason:
        return None
    if st.session_state.get("_checkout_url") and st.session_state.get("_checkout_user_id") == st.session_state.user_id:
        return st.session_state._checkout_url
    params = onetime_checkout_params(
        st.session_state.user_id,
        st.session_state.user_email,
        ctx.price_id,
        ctx.app_url,
        state=state,
    )
    if ctx.local_sandbox:
        session = demo_checkout_session(st.session_state.user_id, st.session_state.user_email)
    else:
        session = ctx.stripe.checkout.Session.create(**params)
    st.session_state._checkout_url = session.url
    st.session_state._checkout_user_id = st.session_state.user_id
    return session.url


def _handle_checkout_return(ctx: Ctx):
    status = query_param(st.query_params, "checkout")
    if status == "cancel":
        st.info("Checkout was canceled. The free comparison is still here.")
        return
    if status != "success":
        return
    session_id = query_param(st.query_params, "session_id")
    st.session_state._checkout_url = None
    if not st.session_state.get("user_logged_in"):
        st.warning("Log in on this page so the payment can be matched to your account.")
        render_auth(ctx, "return")
        return
    if not session_id:
        _load_unlock(ctx)
        return
    try:
        if ctx.local_sandbox:
            session = demo_retrieved_session(session_id, st.session_state.user_id, st.session_state.user_email)
        else:
            session = ctx.stripe.checkout.Session.retrieve(session_id)
    except Exception as exc:
        st.error(f"Checkout could not be confirmed: {exc}")
        return
    decision = fulfillment_decision(
        session,
        st.session_state.user_id,
        st.session_state.user_email,
        st.session_state.get("unlock_row"),
        _now(),
        ctx.price_id,
    )
    if decision["reason"] == "unlocked" and decision["update"]:
        _save_unlock(ctx, decision["update"])
        st.success("The full report is unlocked on this account.")
    elif decision["reason"] == "already_unlocked":
        st.success("This payment was already applied.")
    else:
        st.error("That checkout could not be applied to this account.")


def _apply_demo(ctx: Ctx):
    if st.session_state.get("_demo_applied") or not ctx.local_sandbox:
        return
    params = st.query_params
    view = query_param(params, "view")
    sample = query_param(params, "demo_sample") == "1"
    paid = query_param(params, "demo_user") == "paid" or query_param(params, "checkout") == "success"
    state = query_param(params, "demo_state") or "TX"
    if query_param(params, "demo_missing_price") == "1":
        ctx.price_id = None
    nav_for_view = {
        "home": "Home",
        "inputs": "Run the numbers",
        "terms": "Terms",
        "privacy": "Privacy",
        "method": "How we calculate",
        "disclaimer": "Disclaimer",
        "ask": "Ask a question",
        "scenarios": "My scenarios",
        "posts": "Sample posts",
    }
    if sample or view == "inputs":
        st.session_state.loan_balance_0 = 40000.0
        st.session_state.loan_rate_0 = 6.5
        st.session_state.loan_type_0 = "Direct Unsubsidized"
        st.session_state.loan_when_0 = "Before July 1, 2026"
        st.session_state.on_save = "Yes"
        st.session_state.agi = 53000.0
        st.session_state.filing = "Single"
        st.session_state.dependents = 0
        st.session_state.family_size = 1
        st.session_state.residence = normalize_state(state) or "TX"
        st.session_state.new_borrower = "No"
        st.session_state.pslf_job = "No"
        st.session_state.show_results = view != "inputs"
        st.session_state.wizard_step = 1 if view == "inputs" else 3
    if view in nav_for_view:
        st.session_state.nav = nav_for_view[view]
    elif sample:
        st.session_state.nav = "Run the numbers"
    if paid:
        st.session_state.user_logged_in = True
        st.session_state.user_email = DEMO_EMAIL
        st.session_state.user_id = DEMO_USER_ID
        st.session_state.unlock_row = {
            "user_id": DEMO_USER_ID,
            "product": PRODUCT,
            "stripe_checkout_session_id": "cs_demo_paid",
            "paid_at": "2026-11-27T00:00:00+00:00",
            "terms_accepted_at": "2026-11-27T00:00:00+00:00",
        }
        _seed_scenarios(ctx)
    st.session_state._demo_applied = True


def _seed_scenarios(ctx: Ctx):
    try:
        existing = ctx.supabase.table("loan_scenarios").select("id").eq("user_id", DEMO_USER_ID).execute()
        if existing.data:
            return
    except Exception:
        return
    first = make_scenario()
    second = make_scenario(agi=70_000)
    now = "2026-11-27T00:00:00+00:00"
    later = "2026-11-27T01:00:00+00:00"
    ctx.supabase.table("loan_scenarios").insert(scenario_row(DEMO_USER_ID, "Me now", first, build_audit(first), now)).execute()
    ctx.supabase.table("loan_scenarios").insert(
        scenario_row(DEMO_USER_ID, "After a raise", second, build_audit(second), later)
    ).execute()


def _sidebar(ctx: Ctx):
    st.sidebar.markdown("**Loan Plan Audit**")
    st.sidebar.caption("An independent calculator")
    st.sidebar.radio("Menu", NAV_ITEMS, key="nav")
    if st.session_state.get("user_logged_in"):
        st.sidebar.caption(st.session_state.get("user_email") or "Signed in")
        if st.sidebar.button("Log out"):
            _sign_out(ctx)
            st.rerun()
        if st.sidebar.button("Delete my saved data"):
            _delete_my_data(ctx)
            st.rerun()
    else:
        with st.sidebar.expander("Log in to save"):
            render_auth(ctx, "side")


def _delete_my_data(ctx: Ctx):
    user_id = st.session_state.get("user_id")
    if not user_id:
        return
    try:
        ctx.supabase.table("loan_scenarios").delete().eq("user_id", user_id).execute()
        ctx.supabase.table("unlocks").delete().eq("user_id", user_id).eq("product", PRODUCT).execute()
    except Exception as exc:
        st.error(f"Could not delete saved rows: {exc}")
        return
    _sign_out(ctx)
    st.session_state["_delete_note"] = (
        "Saved scenarios and the unlock record for this calculator were removed. "
        "To delete the login itself, email [CONTACT EMAIL]. Account data is removed within 30 days."
    )


def _landing():
    bullets = "".join(f"<li>{item}</li>" for item in BULLETS)
    st.markdown(
        f"<div class='hero'><h1>{HEADLINE}</h1>"
        f"<p class='tagline'>{TAGLINE}</p>"
        f"<p class='alt-tag'>{ALT_TAGLINE}</p>"
        f"<ul>{bullets}</ul></div>",
        unsafe_allow_html=True,
    )
    st.markdown(f"<div class='strip'>{LANDING_STRIP}</div>", unsafe_allow_html=True)
    if st.button(CTA, type="primary"):
        st.session_state.show_results = False
        st.session_state.wizard_step = 1
        _go("Run the numbers")
        st.rerun()


def _loan_editor():
    st.markdown("### Loans")
    st.caption("About a minute for the whole form. Do not enter a Social Security number, an FSA ID, or a servicer password.")
    remove_at = None
    for index in range(len(st.session_state.loans)):
        _prime(f"loan_balance_{index}", 0.0)
        _prime(f"loan_rate_{index}", 0.0)
        _prime(f"loan_type_{index}", "Direct Unsubsidized")
        _prime(f"loan_when_{index}", "Before July 1, 2026")
        _prime(f"loan_parent_{index}", False)
        st.markdown(f"**Loan {index + 1}**")
        left, right = st.columns(2)
        with left:
            st.number_input("Balance", min_value=0.0, step=1000.0, key=f"loan_balance_{index}", persist_state="session")
            st.selectbox("Loan type", LOAN_TYPES, key=f"loan_type_{index}", persist_state="session")
        with right:
            st.number_input("Interest rate (%)", min_value=0.0, max_value=20.0, step=0.1, key=f"loan_rate_{index}", persist_state="session")
            st.selectbox("First disbursed", WHEN_LABELS, key=f"loan_when_{index}", persist_state="session")
        if st.session_state.get(f"loan_type_{index}") == "Consolidation":
            st.checkbox("This consolidation repaid a Parent PLUS loan", key=f"loan_parent_{index}", persist_state="session")
        if len(st.session_state.loans) > 1 and st.button("Remove this loan", key=f"remove_{index}"):
            remove_at = index
    if remove_at is not None:
        _remove_loan(remove_at)
        st.rerun()
    if st.button("Add a loan"):
        index = len(st.session_state.loans)
        st.session_state.loans.append({"id": index})
        st.session_state[f"loan_balance_{index}"] = 0.0
        st.session_state[f"loan_rate_{index}"] = 0.0
        st.session_state[f"loan_type_{index}"] = "Direct Unsubsidized"
        st.session_state[f"loan_when_{index}"] = "Before July 1, 2026"
        st.session_state[f"loan_parent_{index}"] = False
        st.rerun()
    for key in ("on_save", "pslf_credited", "idr_credited", "new_borrower"):
        _prime(key)
    st.selectbox("Currently on SAVE?", YES_NO, key="on_save", persist_state="session")
    st.number_input("Months already credited toward PSLF", min_value=0, max_value=600, step=1, key="pslf_credited", persist_state="session")
    st.number_input("Months already credited toward an IDR count", min_value=0, max_value=600, step=1, key="idr_credited", persist_state="session")
    st.selectbox("First loan after July 1, 2014?", NEW_LABELS, key="new_borrower", help="Used for the 10% or 15% IBR estimate.", persist_state="session")


def _remove_loan(index: int):
    kept = []
    for cursor in range(len(st.session_state.loans)):
        if cursor == index:
            continue
        kept.append(
            {
                "balance": st.session_state.get(f"loan_balance_{cursor}", 0.0),
                "rate": st.session_state.get(f"loan_rate_{cursor}", 0.0),
                "type": st.session_state.get(f"loan_type_{cursor}", "Direct Unsubsidized"),
                "when": st.session_state.get(f"loan_when_{cursor}", "Before July 1, 2026"),
                "parent": st.session_state.get(f"loan_parent_{cursor}", False),
            }
        )
    for cursor in range(len(st.session_state.loans)):
        for prefix in ("loan_balance_", "loan_rate_", "loan_type_", "loan_when_", "loan_parent_"):
            st.session_state.pop(f"{prefix}{cursor}", None)
    st.session_state.loans = [{"id": i} for i in range(len(kept))]
    saved = dict(st.session_state.get("saved_inputs") or {})
    for key in list(saved):
        if key.startswith(_LOAN_PREFIXES):
            saved.pop(key, None)
    for cursor, loan in enumerate(kept):
        values = {
            f"loan_balance_{cursor}": loan["balance"],
            f"loan_rate_{cursor}": loan["rate"],
            f"loan_type_{cursor}": loan["type"],
            f"loan_when_{cursor}": loan["when"],
            f"loan_parent_{cursor}": loan["parent"],
        }
        st.session_state.update(values)
        saved.update(values)
    st.session_state["saved_inputs"] = saved


def _household():
    st.markdown("### Household")
    for key in ("agi", "filing", "spouse_agi", "dependents", "family_size", "residence", "federal_tax", "state_tax"):
        _prime(key)
    st.number_input("AGI", min_value=0.0, step=1000.0, key="agi", help="Line 11 of Form 1040, from your most recent return.", persist_state="session")
    st.selectbox("Filing status", FILING_LABELS, key="filing", persist_state="session")
    if st.session_state.get("filing") == "Married filing jointly":
        st.number_input("Spouse AGI", min_value=0.0, step=1000.0, key="spouse_agi", persist_state="session")
    st.number_input("Dependents claimed", min_value=0, max_value=15, step=1, key="dependents", help="Used in the RAP estimate.", persist_state="session")
    st.number_input("Family size", min_value=1, max_value=15, step=1, key="family_size", help="Used for the poverty guideline in the IBR estimate.", persist_state="session")
    codes = [""] + [code for _name, code in STATE_CHOICES]
    st.selectbox(
        "State of residence",
        codes,
        format_func=lambda code: "Select your state" if not code else STATE_NAMES[code],
        key="residence",
        persist_state="session",
    )
    st.number_input("Federal tax rate on a discharged balance (%)", min_value=0.0, max_value=50.0, step=1.0, key="federal_tax", persist_state="session")
    st.number_input("State tax rate on a discharged balance (%)", min_value=0.0, max_value=15.0, step=0.5, key="state_tax", persist_state="session")


def _career():
    st.markdown("### Career")
    for key in ("pslf_job", "raise_pct", "inflation_pct", "autopay"):
        _prime(key)
    st.selectbox("Works full time for a government or 501(c)(3) employer?", YES_NO, key="pslf_job", persist_state="session")
    st.number_input("Expected annual raise (%)", min_value=0.0, max_value=15.0, step=0.5, key="raise_pct", persist_state="session")
    st.number_input("Poverty-guideline inflation (%)", min_value=0.0, max_value=10.0, step=0.5, key="inflation_pct", persist_state="session")
    st.checkbox("Auto-pay rate reduction", key="autopay", persist_state="session", help="Off unless you turn it on. The estimate then uses a rate one percentage point lower. Confirm any reduction with your servicer.")


def _wizard():
    step = int(st.session_state.wizard_step)
    st.caption(f"Step {step} of 3")
    if step == 1:
        _loan_editor()
    elif step == 2:
        _household()
    else:
        _career()
    _snapshot_inputs()
    back, forward = st.columns(2)
    with back:
        if step > 1 and st.button("Back"):
            _snapshot_inputs()
            st.session_state.wizard_step = step - 1
            st.rerun()
    with forward:
        if step < 3 and st.button("Next", type="primary"):
            _snapshot_inputs()
            st.session_state.wizard_step = step + 1
            st.rerun()
        if step == 3 and st.button("See my free results", type="primary"):
            _snapshot_inputs()
            errors = validate_scenario(_scenario_from_widgets())
            if errors:
                for error in errors:
                    st.error(error)
            else:
                st.session_state.show_results = True
                st.rerun()


def _links():
    st.markdown("**Free tools**")
    for label, url in LINKS.items():
        st.markdown(f"- [{label}]({url})")


def _chips(plans):
    html = []
    for plan in plans:
        chip = " · ".join(plan.chips) if plan.chips else ""
        html.append(f"<span class='chip'><b>{plan.label}</b> · {chip}</span>")
    st.markdown("".join(html), unsafe_allow_html=True)


def _blurred(plans):
    rows = []
    for plan in plans:
        if not plan.eligible:
            continue
        rows.append(
            "<tr>"
            f"<td>{plan.label}</td><td>{_money(plan.total_paid)}</td>"
            f"<td>{_money(plan.interest_paid)}</td><td>{_money(plan.forgiven_amount)}</td>"
            f"<td>{_money(plan.estimated_tax)}</td></tr>"
        )
    table = (
        "<table><tr><th>Plan</th><th>Total paid</th><th>Interest paid</th>"
        "<th>Balance at end</th><th>Estimated tax</th></tr>"
        + "".join(rows)
        + "</table>"
    )
    st.markdown(
        f"<p>Lifetime totals are part of the full report.</p><div class='blur-target'>{table}</div>",
        unsafe_allow_html=True,
    )


def _paid_world(audit, plans, scenario: ScenarioInput, world_key: str, show_private: bool):
    sort_label = st.selectbox("Sort by", list(SORTS), key=f"sort_{world_key}")
    ordered = sort_plans(plans, SORTS[sort_label])
    lowest = lowest_estimated_total(plans)
    if lowest:
        st.markdown(f"**{lowest.label}:** {LOWEST_TOTAL_CAPTION}")
    records = []
    for plan in ordered:
        records.append(
            {
                "Plan": plan.label,
                "Eligible": "Yes" if plan.eligible else plan.chips[0] if plan.chips else "No",
                "Monthly now": None if plan.first_year_monthly is None else round(plan.first_year_monthly, 2),
                "Total paid": plan.total_paid,
                "Interest paid": plan.interest_paid,
                "Interest not charged": plan.interest_waived,
                "Principal match": plan.principal_matched,
                "End": plan.end_date,
                "What happens": END_LABELS.get(plan.end_reason or "", ""),
                "Balance at end": plan.forgiven_amount,
                "Estimated tax": plan.estimated_tax,
            }
        )
    st.dataframe(records, width="stretch", hide_index=True)
    st.plotly_chart(comparison_chart(plans), width="stretch", key=f"compare_{world_key}")
    start = date.fromisoformat(audit.start_date)
    st.plotly_chart(
        payoff_timeline(plans, start, scenario.pslf_job, scenario.pslf_months_credited),
        width="stretch",
        key=f"timeline_{world_key}",
    )
    st.markdown("### Plan end dates")
    for plan in plans:
        if not plan.eligible or not plan.end_month:
            continue
        if plan.end_reason == "pslf":
            line = f"PSLF in {format_duration(plan.end_month)} ({plan.end_month} payments left)"
        elif plan.plan_id == PLAN_RAP and plan.end_reason == "idr_discharge" and plan.end_date:
            line = f"RAP discharge in {plan.end_date[:4]}"
        else:
            line = f"{plan.label}: {format_duration(plan.end_month)} · {END_LABELS.get(plan.end_reason, '')}"
        st.markdown(f"<p class='big'>{line}</p>", unsafe_allow_html=True)
        if plan.estimated_tax:
            st.markdown(f"<p class='coral'>Estimated tax at the rate you entered: {_money(plan.estimated_tax)}</p>", unsafe_allow_html=True)
        elif plan.end_reason == "pslf":
            st.markdown("<p class='mint'>PSLF estimate: federal tax $0</p>", unsafe_allow_html=True)
    rap = next((plan for plan in plans if plan.plan_id == PLAN_RAP and plan.eligible), None)
    if rap:
        st.markdown("### RAP interest and principal match")
        left, right = st.columns(2)
        left.markdown(f"<div class='card'><p>Interest not added</p><p class='big mint'>{_money(rap.interest_waived)}</p></div>", unsafe_allow_html=True)
        right.markdown(f"<div class='card'><p>Principal match</p><p class='big mint'>{_money(rap.principal_matched)}</p></div>", unsafe_allow_html=True)
        st.caption("These are the formula results for the combined balance, month by month, in this estimate.")
    st.markdown("### PSLF")
    if scenario.pslf_job:
        st.caption("The toggle is on. Tiered Standard is marked as not counting. Other plans stop at 120 qualifying payments in this estimate, minus months you entered.")
    else:
        st.caption("The full-time public-service toggle is off. Turn it on in the sliders to see that estimate.")
    st.markdown("### Questions to ask your servicer")
    for item in SERVICER_QUESTIONS:
        st.markdown(f"- {item}")
    generated = date.today().isoformat()
    st.download_button(
        "Download the report PDF",
        data=build_report_pdf(audit, plans, generated_on=generated),
        file_name="loan-plan-audit.pdf",
        mime="application/pdf",
        type="primary",
        key=f"pdf_{world_key}",
    )
    png = render_share_card(audit, plans, show_private=show_private)
    st.image(png, caption="Estimate. Not advice.")
    st.download_button(
        "Download share card",
        data=png,
        file_name="loan-plan-audit-card.png",
        mime="image/png",
        key=f"card_{world_key}",
    )


def _what_if(scenario: ScenarioInput):
    st.markdown("### What if")
    st.caption("Sliders change this page only. They do not change a saved scenario until you save again.")
    _ensure("what_income", 1.0)
    _ensure("what_raise", min(8.0, scenario.annual_raise * 100))
    _ensure("what_deps", min(5, int(scenario.dependents)))
    st.session_state.what_raise = min(8.0, float(st.session_state.what_raise))
    st.session_state.what_deps = min(5, int(st.session_state.what_deps))
    _ensure("what_extra", 0)
    _ensure("what_spouse", float(scenario.spouse_agi))
    _ensure("what_filing", scenario.filing_status)
    _ensure("what_pslf", scenario.pslf_job)
    _ensure("what_autopay", scenario.autopay)
    st.slider("Income", min_value=0.5, max_value=1.5, step=0.05, key="what_income", help="Multiplies the AGI you entered. 1.00 leaves it unchanged.")
    st.slider("Annual raise (%)", min_value=0.0, max_value=8.0, step=0.5, key="what_raise")
    st.slider("Dependents", min_value=0, max_value=5, step=1, key="what_deps")
    st.slider("Extra monthly amount", min_value=0, max_value=500, step=25, key="what_extra")
    st.number_input("Spouse AGI for this comparison", min_value=0.0, step=1000.0, key="what_spouse")
    st.selectbox(
        "Filing status for this comparison",
        ("single", "hoh", "mfj", "mfs"),
        format_func=lambda code: {value: label for label, value in FILING_VALUES.items()}[code],
        key="what_filing",
    )
    st.checkbox("Full-time public service", key="what_pslf")
    st.checkbox("Auto-pay rate reduction", key="what_autopay")


def _checkout_panel(ctx: Ctx, state: str):
    st.markdown(f"<div class='disclaimer'>{CHECKOUT_DISCLAIMER}</div>", unsafe_allow_html=True)
    st.checkbox(TERMS_CHECKBOX, key="agreed_terms")
    st.caption("Read the Terms before checking the box. Checkout stays closed until the box is checked.")
    if not ctx.price_id:
        st.error(PRICE_SETUP_ERROR)
        return
    if not st.session_state.get("agreed_terms"):
        st.info("Check the box to agree to the Terms before checkout.")
        return
    if not st.session_state.get("user_logged_in"):
        st.markdown("**Create an account or log in. The free comparison stays on this page. No subscription.**")
        render_auth(ctx, "pay")
        return
    if ctx.local_sandbox:
        st.caption("Local demo: this button does not contact Stripe.")
    try:
        url = _checkout_url(ctx, state)
    except Exception as exc:
        st.error(str(exc))
        return
    if url:
        st.link_button(CHECKOUT_BUTTON, url, type="primary")
    else:
        reason = checkout_block_reason(
            state=state,
            agreed_to_terms=True,
            price_id=ctx.price_id,
            logged_in=True,
        )
        if reason == "price_missing":
            st.error(PRICE_SETUP_ERROR)
        else:
            st.info("Checkout is not available for this visit.")


def _save_panel(ctx: Ctx, scenario: ScenarioInput, audit):
    if not st.session_state.get("user_logged_in"):
        st.caption("Log in if you want this scenario saved. The calculation itself is not stored.")
        return
    name = st.text_input("Scenario name", key="scenario_name")
    if st.button("Save this scenario"):
        fingerprint = scenario_fingerprint(scenario)
        if st.session_state.get("_saved_fp") == fingerprint:
            st.info("This scenario is already saved.")
            return
        try:
            ctx.supabase.table("loan_scenarios").insert(
                scenario_row(st.session_state.user_id, name, scenario, audit, _now())
            ).execute()
            st.session_state._saved_fp = fingerprint
            st.success("Saved.")
        except Exception as exc:
            if table_missing(str(exc), "loan_scenarios"):
                st.warning("The loan_scenarios table is not in this database yet. The calculation is still on the page.")
            else:
                st.error(f"Could not save: {exc}")


def _render_world(ctx: Ctx, audit, plans, scenario: ScenarioInput, unlocked: bool, blocked: bool, world_key: str, show_private: bool):
    _chips(plans)
    for plan in plans:
        for note in plan.notes:
            if not plan.eligible:
                st.caption(f"{plan.label}: {note}")
    st.plotly_chart(monthly_bar(plans), width="stretch", key=f"monthly_{world_key}")
    if unlocked:
        _paid_world(audit, plans, scenario, world_key, show_private)
    elif not blocked:
        _blurred(plans)


def _results(ctx: Ctx):
    _rules()
    st.markdown(f"<div class='disclaimer'>{RESULTS_DISCLAIMER}</div>", unsafe_allow_html=True)
    if st.button("Edit inputs"):
        st.session_state.show_results = False
        st.rerun()
    base = _scenario_from_widgets()
    errors = validate_scenario(base)
    if errors:
        for error in errors:
            st.error(error)
        return
    gate = residence_gate(base.state)
    blocked = gate == "blocked"
    unlocked = bool(st.session_state.get("unlock_row")) and not blocked and gate == "ok"
    if unlocked:
        _what_if(base)
        scenario = _apply_what_if(base)
    else:
        scenario = base
    audit = build_audit(scenario)
    if not audit.ok:
        for error in audit.errors:
            st.error(error)
        return
    for note in audit.notes:
        st.caption(note)
    show_private = False
    if unlocked:
        show_private = st.checkbox("Include balances and income on the share card", key="show_private_card")
    if audit.uncertain:
        st.info("A disbursement date is marked not sure. Both sets are below. Check the loan list on StudentAid.gov.")
        left, right = st.tabs(
            ["If every loan is from before July 1, 2026", "If any loan is from on or after July 1, 2026"]
        )
        with left:
            _render_world(ctx, audit, audit.worlds["pre_july_2026"], scenario, unlocked, blocked, "pre", show_private)
        with right:
            _render_world(ctx, audit, audit.worlds["on_or_after_july_2026"], scenario, unlocked, blocked, "post", show_private)
    else:
        _render_world(ctx, audit, audit.worlds["primary"], scenario, unlocked, blocked, "primary", show_private)
    if unlocked:
        _save_panel(ctx, scenario, audit)
    st.markdown("### Your SAVE checklist" if scenario.on_save else "### SAVE checklist")
    for item in SAVE_CHECKLIST:
        st.markdown(f"- {item}")
    _links()
    if blocked:
        st.info(blocked_state_note(base.state))
    elif not unlocked:
        _checkout_panel(ctx, base.state)


def _scenarios(ctx: Ctx):
    st.markdown("## My scenarios")
    if not st.session_state.get("user_logged_in"):
        st.caption("Log in to see scenarios saved on your account.")
        render_auth(ctx, "scenarios")
        return
    if not st.session_state.get("unlock_row"):
        st.caption("Saving and comparing scenarios is part of the full report.")
        return
    try:
        result = ctx.supabase.table("loan_scenarios").select("*").eq("user_id", st.session_state.user_id).execute()
        rows = sort_newest_first(result.data or [])
    except Exception as exc:
        if table_missing(str(exc), "loan_scenarios"):
            st.warning("The loan_scenarios table is not in this database yet.")
            return
        st.error(str(exc))
        return
    if not rows:
        st.caption("No saved scenarios yet. Save one from the results page.")
        return
    for row in rows:
        with st.expander(row.get("name") or "My scenario"):
            renamed = st.text_input("Name", value=row.get("name") or "", key=f"rename_{row['id']}")
            if st.button("Rename", key=f"rename_btn_{row['id']}"):
                ctx.supabase.table("loan_scenarios").update({"name": renamed, "updated_at": _now()}).eq("user_id", st.session_state.user_id).eq("id", row["id"]).execute()
                st.rerun()
            if st.button("Delete", key=f"delete_btn_{row['id']}"):
                ctx.supabase.table("loan_scenarios").delete().eq("user_id", st.session_state.user_id).eq("id", row["id"]).execute()
                st.rerun()
    if len(rows) >= 2:
        st.markdown("### Compare two scenarios")
        labels = {f"{row.get('name')} ({row['id']})": row for row in rows}
        left = st.selectbox("First", list(labels), key="compare_left")
        right = st.selectbox("Second", list(labels), index=1, key="compare_right")
        if st.button("Compare these two"):
            first = scenario_from_dict(labels[left]["inputs"])
            second = scenario_from_dict(labels[right]["inputs"])
            if residence_gate(first.state) == "blocked" or residence_gate(second.state) == "blocked":
                st.info(blocked_state_note(first.state if residence_gate(first.state) == "blocked" else second.state))
            audit_a = build_audit(first)
            audit_b = build_audit(second)
            plans_a = next(iter(audit_a.worlds.values()))
            plans_b = next(iter(audit_b.worlds.values()))
            show_totals = paid_report_available(first.state) and paid_report_available(second.state)
            for item in diff_plans(plans_a, plans_b):
                monthly = _money(item["monthly_difference"])
                line = f"{item['label']}: estimated monthly difference {monthly}"
                if show_totals and item["total_difference"] is not None:
                    line += f"; estimated total difference {_money(item['total_difference'])}"
                st.write(line)
            st.caption("Estimated difference, second minus first.")


def _method():
    _rules()
    st.markdown("## How we calculate")
    for paragraph in METHOD_PARAGRAPHS:
        st.write(paragraph)
    st.markdown("### Open points")
    for item in METHOD_UNCERTAIN:
        st.markdown(f"- {item}")
    st.markdown("### Sources")
    for label, url in SOURCES:
        st.markdown(f"- [{label}]({url})")
    st.markdown(f"<div class='disclaimer'>{RESULTS_DISCLAIMER}</div>", unsafe_allow_html=True)


def _disclaimer_page():
    st.markdown("## Disclaimer")
    st.markdown("**Landing**")
    st.markdown(f"<div class='strip'>{LANDING_STRIP}</div>", unsafe_allow_html=True)
    st.markdown("**Short**")
    st.markdown(f"<div class='disclaimer'>{SHORT_DISCLAIMER}</div>", unsafe_allow_html=True)
    st.markdown("**Results**")
    st.markdown(f"<div class='disclaimer'>{RESULTS_DISCLAIMER}</div>", unsafe_allow_html=True)
    st.markdown("**Checkout**")
    st.markdown(f"<div class='disclaimer'>{CHECKOUT_DISCLAIMER}</div>", unsafe_allow_html=True)
    st.markdown(f"**Question box:** {AI_LINE}")


def _ask(ctx: Ctx):
    st.markdown("## Ask a question")
    st.caption(AI_LINE)
    st.caption("Do not include a Social Security number, an FSA ID, or a servicer password.")
    question = st.text_area("Question", key="question_text")
    if st.button("Ask"):
        cleaned = _scrub(question)
        if not cleaned.strip():
            st.error("Enter a question first.")
        elif ctx.openai_client is None:
            st.info("The question box is not configured on this copy of the app.")
        else:
            summary = _public_numbers()
            try:
                response = ctx.openai_client.responses.create(
                    model="gpt-4.1-mini",
                    instructions=AI_INSTRUCTIONS,
                    input=f"Plan figures only:\n{summary}\n\nQuestion:\n{cleaned}",
                )
                answer = (getattr(response, "output_text", "") or "").strip()
            except Exception:
                answer = ""
            if not answer:
                st.error("No answer came back. The question box did not invent one.")
            else:
                if AI_LINE not in answer:
                    answer = f"{answer}\n\n{AI_LINE}"
                st.write(answer)
    st.markdown(f"<div class='fine-print'>{SHORT_DISCLAIMER}</div>", unsafe_allow_html=True)


def _scrub(text: str) -> str:
    cleaned = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[removed]", text or "")
    cleaned = re.sub(r"\b\d{9}\b", "[removed]", cleaned)
    return cleaned[:2000]


def _public_numbers() -> str:
    try:
        audit = build_audit(_scenario_from_widgets())
    except Exception:
        return "No figures yet."
    if not audit.ok:
        return "No figures yet."
    lines = []
    for plans in audit.worlds.values():
        for plan in plans:
            if plan.eligible and plan.first_year_monthly is not None:
                lines.append(f"{plan.label}: {_money(plan.first_year_monthly)} a month")
    return "\n".join(lines) or "No figures yet."


def _posts():
    from carousels import all_decks, render_slide_png

    st.markdown("## Sample posts")
    st.caption("Hypothetical drafts. Each set ends on the disclaimer. These are not ads running on this page.")
    for name, slides in all_decks():
        st.markdown(f"### {name}")
        st.image(render_slide_png(slides[0]), width="stretch")
        with st.expander("All slides"):
            for slide in slides:
                st.image(render_slide_png(slide), width="stretch")


def run(ctx: Ctx):
    global _RENDERED
    _RENDERED = set()
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    _init()
    _apply_demo(ctx)
    _consume_nav()
    _restore(ctx)
    if st.session_state.pop("_reload_unlock", False):
        _load_unlock(ctx)
    if st.session_state.get("_delete_note"):
        st.success(st.session_state.pop("_delete_note"))
    if not ctx.price_id:
        st.error(PRICE_SETUP_ERROR)
    _handle_checkout_return(ctx)
    _sidebar(ctx)
    page = st.session_state.get("nav") or "Home"
    if page == "Home":
        _landing()
    elif page == "Run the numbers":
        if st.session_state.get("show_results"):
            _results(ctx)
        else:
            _wizard()
    elif page == "My scenarios":
        _scenarios(ctx)
    elif page == "How we calculate":
        _method()
    elif page == "Ask a question":
        _ask(ctx)
    elif page == "Sample posts":
        _posts()
    elif page == "Disclaimer":
        _disclaimer_page()
    elif page == "Terms":
        st.markdown(terms_markdown())
    elif page == "Privacy":
        st.markdown(privacy_markdown())
    _footer()
