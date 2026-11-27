"""Streamlit screens for Dealer Fee Check."""

from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from checkout import (
    PRICE_SETUP_ERROR,
    PRODUCT,
    UNLOCK_TOKEN_SETUP_ERROR,
    checkout_block_reason,
    commit_unlock,
    fulfillment_decision,
    onetime_checkout_params,
)
from copy_text import (
    ALT_TAGLINE,
    BULLETS,
    CHECKOUT_BUTTON,
    CHECKOUT_DISCLAIMER,
    CTA,
    HEADLINE,
    PUBLIC_URL,
    LANDING_STRIP,
    METHOD_PARAGRAPHS,
    PRICE_DOLLARS,
    QUESTIONS_TO_ASK,
    RESULTS_DISCLAIMER,
    RULES_BANNER,
    SCRIPT_DISCLAIMER,
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
    LineItem,
    QuoteInput,
    build_audit,
    counter_offer_text,
    flagged_lines,
    make_sample_quote,
    quote_from_dict,
)
from fees import (
    CATEGORY_LABELS,
    CATEGORY_PICKER,
    DOC_FEE_RULES,
    PICKER_TO_CAT,
    STATE_CHOICES,
    STATE_NAMES,
    doc_fee_rule,
    normalize_state,
)
from report import build_report_pdf
from store import quote_row, sort_newest_first, unlock_is_active
from theme import THEME_CSS

NAV_ITEMS = ("Home", "Check a quote", "My quotes", "How we check", "Disclaimer", "Terms", "Privacy")
STATE_LABELS = tuple(f"{name} ({code})" for name, code in STATE_CHOICES)
LABEL_TO_CODE = {f"{name} ({code})": code for name, code in STATE_CHOICES}
CODE_TO_LABEL = {code: label for label, code in LABEL_TO_CODE.items()}

STARTER_ROWS = [
    {"Line item": "Destination charge", "Amount ($)": 0.0, "Category": "Auto-detect"},
    {"Line item": "Doc fee", "Amount ($)": 0.0, "Category": "Auto-detect"},
    {"Line item": "Sales tax", "Amount ($)": 0.0, "Category": "Auto-detect"},
    {"Line item": "Title and registration", "Amount ($)": 0.0, "Category": "Auto-detect"},
]


@dataclass
class Ctx:
    supabase: object
    stripe: object
    price_id: str | None
    app_url: str
    local_sandbox: bool
    unlock_token: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _money(value) -> str:
    if value is None:
        return "—"
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


def _go(page: str):
    st.session_state["_nav_to"] = page


def _consume_nav():
    target = st.session_state.pop("_nav_to", None)
    if target:
        st.session_state.nav = target


def _init():
    defaults = {
        "nav": "Home",
        "show_results": False,
        "user_logged_in": False,
        "user_email": None,
        "user_id": None,
        "unlock_row": None,
        "residence": CODE_TO_LABEL["TX"],
        "condition": "New",
        "vehicle_price": 0.0,
        "vehicle": "",
        "trade_in": 0.0,
        "down_payment": 0.0,
        "financing": False,
        "apr": 7.0,
        "term": 60,
        "is_ev": False,
        "items_base": pd.DataFrame(STARTER_ROWS),
        "items_df": pd.DataFrame(STARTER_ROWS),
        "editor_version": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _sample_into_state(state: str = "TX"):
    sample = make_sample_quote(state)
    st.session_state.residence = CODE_TO_LABEL[normalize_state(state) or "TX"]
    st.session_state.condition = "New"
    st.session_state.vehicle_price = sample.vehicle_price
    st.session_state.vehicle = sample.vehicle
    st.session_state.down_payment = sample.down_payment
    st.session_state.trade_in = 0.0
    st.session_state.financing = True
    st.session_state.apr = sample.apr
    st.session_state.term = sample.term_months
    st.session_state.items_base = pd.DataFrame(
        [{"Line item": item.label, "Amount ($)": item.amount, "Category": "Auto-detect"} for item in sample.items]
    )
    st.session_state.items_df = st.session_state.items_base
    st.session_state.editor_version += 1


def _quote_from_state() -> QuoteInput:
    df = st.session_state.items_df
    items = []
    for _, row in df.iterrows():
        label = str(row.get("Line item") or "").strip()
        try:
            amount = float(row.get("Amount ($)") or 0.0)
        except (TypeError, ValueError):
            amount = 0.0
        if not amount:
            continue  # starter rows left at $0 are ignored
        picked = row.get("Category") or "Auto-detect"
        items.append(LineItem(label=label, amount=amount, category=PICKER_TO_CAT.get(picked)))
    financing = bool(st.session_state.financing)
    return QuoteInput(
        state=LABEL_TO_CODE.get(st.session_state.residence, ""),
        condition="new" if st.session_state.condition == "New" else "used",
        vehicle_price=float(st.session_state.vehicle_price or 0.0),
        items=items,
        trade_in=float(st.session_state.trade_in or 0.0),
        down_payment=float(st.session_state.down_payment or 0.0),
        apr=float(st.session_state.apr) if financing else None,
        term_months=int(st.session_state.term) if financing else None,
        is_ev=bool(st.session_state.is_ev),
        vehicle=str(st.session_state.vehicle or ""),
    )


# ---------- auth and unlock (same flow as Loan Plan Audit) ----------

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


def _unlock_rows(ctx: Ctx) -> list[dict]:
    user_id = st.session_state.get("user_id")
    if not user_id:
        return []
    try:
        result = ctx.supabase.table("unlocks").select("*").eq("user_id", user_id).eq("product", PRODUCT).execute()
        return list(result.data or [])
    except Exception:
        return []


def _load_unlock(ctx: Ctx):
    rows = _unlock_rows(ctx)
    st.session_state.unlock_row = rows[0] if rows and unlock_is_active(rows[0]) else None


def _save_unlock(ctx: Ctx, session, update: dict) -> str:
    """Record an unlock only after Stripe and the recording token both pass.

    Production calls record_dealer_fee_unlock, which writes auth.uid() only.
    The anon key cannot insert into unlocks directly.
    """
    if not ctx.unlock_token:
        st.error(UNLOCK_TOKEN_SETUP_ERROR)
        return "rejected"
    decision = commit_unlock(
        session=session,
        user_id=st.session_state.get("user_id"),
        email=st.session_state.get("user_email"),
        existing_rows=_unlock_rows(ctx),
        now_iso=update.get("paid_at") or _now(),
        expected_price_id=ctx.price_id,
        token=ctx.unlock_token,
        configured_token=ctx.unlock_token,
    )
    if not decision["recorded"]:
        if decision["reason"] == "already_unlocked":
            _load_unlock(ctx)
            return "already_unlocked"
        st.error("That checkout could not be applied to this account.")
        return "rejected"
    if ctx.local_sandbox:
        ctx.supabase.table("unlocks").insert(decision["update"]).execute()
        st.session_state.unlock_row = decision["update"]
        return "recorded"
    try:
        ctx.supabase.rpc(
            "record_dealer_fee_unlock",
            {"p_session_id": decision["update"]["stripe_checkout_session_id"], "p_token": ctx.unlock_token},
        ).execute()
    except Exception:
        st.error("That checkout could not be applied to this account.")
        return "rejected"
    _load_unlock(ctx)
    if not st.session_state.get("unlock_row"):
        st.session_state.unlock_row = decision["update"]
    return "recorded"


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
    st.session_state.user_logged_in = False
    for key in ("user_email", "user_id", "unlock_row", "_sb_access_token", "_sb_refresh_token", "_checkout_url"):
        st.session_state[key] = None


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
                    if "not confirmed" in error.lower():
                        st.error("Confirm your email first, then log in.")
                    else:
                        st.error(f"Login failed: {error}")
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
        st.session_state.user_id, st.session_state.user_email, ctx.price_id, ctx.app_url, state=state
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
        st.info("Checkout was canceled. Your free results are still here.")
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
    if st.session_state.get("_handled_session") == session_id:
        return
    st.session_state._handled_session = session_id
    try:
        if ctx.local_sandbox:
            session = demo_retrieved_session(session_id, st.session_state.user_id, st.session_state.user_email)
        else:
            session = ctx.stripe.checkout.Session.retrieve(session_id, expand=["line_items"])
    except Exception as exc:
        st.error(f"Checkout could not be confirmed: {exc}")
        return
    decision = fulfillment_decision(
        session, st.session_state.user_id, st.session_state.user_email, st.session_state.get("unlock_row"), _now(), ctx.price_id
    )
    if decision["reason"] == "unlocked" and decision["update"]:
        outcome = _save_unlock(ctx, session, decision["update"])
        if outcome == "recorded":
            st.success("The full report is unlocked on this account.")
        elif outcome == "already_unlocked":
            st.success("This payment was already applied.")
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
    paid = query_param(params, "demo_user") == "paid"
    state = query_param(params, "demo_state") or "TX"
    if query_param(params, "demo_missing_price") == "1":
        ctx.price_id = None
    nav_for_view = {
        "home": "Home",
        "quote": "Check a quote",
        "terms": "Terms",
        "privacy": "Privacy",
        "method": "How we check",
        "disclaimer": "Disclaimer",
        "quotes": "My quotes",
    }
    if sample or view == "quote":
        _sample_into_state(state)
        st.session_state.show_results = view != "quote"
    if view in nav_for_view:
        st.session_state.nav = nav_for_view[view]
    elif sample:
        st.session_state.nav = "Check a quote"
    if query_param(params, "demo_login") == "1" or paid:
        st.session_state.user_logged_in = True
        st.session_state.user_email = DEMO_EMAIL
        st.session_state.user_id = DEMO_USER_ID
    if query_param(params, "demo_terms") == "1":
        st.session_state.agreed_terms = True
    if paid:
        st.session_state.unlock_row = {
            "user_id": DEMO_USER_ID,
            "product": PRODUCT,
            "stripe_checkout_session_id": "cs_demo_paid",
            "paid_at": "2026-11-27T00:00:00+00:00",
        }
    st.session_state._demo_applied = True


# ---------- screens ----------

def _footer():
    st.markdown(f"<div class='fine-print'>{SHORT_DISCLAIMER}</div>", unsafe_allow_html=True)
    st.caption(f"Dealer Fee Check · independent software · not a dealer, broker, or lender · {PUBLIC_URL}")


def _rules():
    st.markdown(f"<div class='rules'>{RULES_BANNER}</div>", unsafe_allow_html=True)


def _sidebar(ctx: Ctx):
    st.sidebar.markdown("**Dealer Fee Check**")
    st.sidebar.caption("Independent fee checker")
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
        with st.sidebar.expander("Log in to save quotes"):
            render_auth(ctx, "side")


def _delete_my_data(ctx: Ctx):
    user_id = st.session_state.get("user_id")
    if not user_id:
        return
    try:
        ctx.supabase.table("dealer_fee_quotes").delete().eq("user_id", user_id).execute()
        if ctx.local_sandbox:
            ctx.supabase.table("unlocks").delete().eq("user_id", user_id).eq("product", PRODUCT).execute()
        else:
            ctx.supabase.rpc("delete_my_dealer_fee_unlock", {}).execute()
    except Exception as exc:
        st.error(f"Could not delete saved rows: {exc}")
        return
    _sign_out(ctx)
    st.session_state["_delete_note"] = (
        "Saved quotes and the unlock record for this app were removed. "
        "To delete the login itself, email [CONTACT EMAIL]. Account data is removed within 30 days."
    )


def _landing():
    bullets = "".join(f"<li>{item}</li>" for item in BULLETS)
    st.markdown(
        f"<div class='hero'><h1>{HEADLINE}</h1><p class='tagline'>{TAGLINE}</p>"
        f"<p class='alt-tag'>{ALT_TAGLINE}</p><ul>{bullets}</ul></div>",
        unsafe_allow_html=True,
    )
    st.markdown(f"<div class='strip'>{LANDING_STRIP}</div>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    if col1.button(CTA, type="primary"):
        st.session_state.show_results = False
        _go("Check a quote")
        st.rerun()
    if col2.button("Try it with a sample quote"):
        _sample_into_state("TX")
        st.session_state.show_results = True
        _go("Check a quote")
        st.rerun()


def _entry():
    _rules()
    st.markdown("## Your quote")
    st.caption(
        "Copy the lines from the dealer's quote or buyer's order. About a minute. "
        "Don't enter your name, address, VIN, Social Security number, or any account number."
    )
    c1, c2, c3 = st.columns(3)
    c1.selectbox("State where you'll register the car", STATE_LABELS, key="residence")
    c2.radio("New or used", ("New", "Used"), key="condition", horizontal=True)
    c3.text_input("Vehicle (optional, e.g. 2026 compact SUV)", key="vehicle", max_chars=80)
    c1, c2, c3 = st.columns(3)
    c1.number_input("Vehicle selling price before fees ($)", min_value=0.0, step=100.0, key="vehicle_price")
    c2.number_input("Trade-in credit ($)", min_value=0.0, step=100.0, key="trade_in")
    c3.number_input("Down payment ($)", min_value=0.0, step=100.0, key="down_payment")
    st.markdown("**Every other line on the quote** — add rows with the + at the bottom. Use a minus sign for discounts.")
    edited = st.data_editor(
        st.session_state.items_base,
        num_rows="dynamic",
        width="stretch",
        height=min(36 * (len(st.session_state.items_base) + 2) + 4, 640),
        key=f"items_editor_{st.session_state.editor_version}",
        column_config={
            "Line item": st.column_config.TextColumn("Line item", max_chars=80, required=True),
            "Amount ($)": st.column_config.NumberColumn("Amount ($)", format="$%.2f", step=1.0),
            "Category": st.column_config.SelectboxColumn("Category", options=list(CATEGORY_PICKER), default="Auto-detect"),
        },
    )
    st.session_state.items_df = edited
    c1, c2, c3 = st.columns(3)
    c1.checkbox("I'm financing through the dealer", key="financing")
    if st.session_state.financing:
        c2.number_input("APR (%)", min_value=0.0, max_value=40.0, step=0.1, key="apr")
        c3.number_input("Term (months)", min_value=6, max_value=96, step=6, key="term")
    st.checkbox("It's an electric vehicle", key="is_ev")
    if st.button("Check my quote", type="primary"):
        audit = build_audit(_quote_from_state())
        if not audit.ok:
            for error in audit.errors:
                st.error(error)
        else:
            st.session_state.items_base = edited.reset_index(drop=True)
            st.session_state.editor_version += 1
            st.session_state.show_results = True
            st.rerun()


def _verdict_chip(line) -> str:
    return f"<span class='verdict v-{line.verdict}'>{html.escape(line.verdict_label)}</span>"


def _line_card(line):
    st.markdown(
        f"<div class='line'><span class='amt'>{_money(line.amount)}</span><b>{html.escape(line.label)}</b> "
        f"<span class='chip'>{html.escape(line.category_label)}</span><br>{_verdict_chip(line)}"
        f"<p style='margin:8px 0 0 0'><b>{html.escape(line.headline)}.</b> {html.escape(line.detail)}</p></div>",
        unsafe_allow_html=True,
    )


def _category_chart(audit):
    labels, values = [], []
    for key, label in CATEGORY_LABELS.items():
        if key in audit.by_category and audit.by_category[key] != 0:
            labels.append(label)
            values.append(audit.by_category[key])
    colors = {
        CATEGORY_LABELS["government"]: "#64748B",
        CATEGORY_LABELS["doc_fee"]: "#1C2430",
        CATEGORY_LABELS["destination"]: "#94A3B8",
        CATEGORY_LABELS["market_adjustment"]: "#E5484D",
        CATEGORY_LABELS["dealer_addon"]: "#FF7A1A",
        CATEGORY_LABELS["fi_product"]: "#F5A524",
        CATEGORY_LABELS["discount"]: "#22C55E",
        CATEGORY_LABELS["other"]: "#A78BFA",
    }
    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker_color=[colors.get(label, "#1C2430") for label in labels],
            text=[_money(v) for v in values],
            textposition="auto",
        )
    )
    fig.update_layout(
        height=60 + 44 * max(len(labels), 1),
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, visible=False),
        yaxis=dict(autorange="reversed"),
        font=dict(color="#1C2430"),
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def _checkout_panel(ctx: Ctx, state: str):
    st.markdown(f"<div class='disclaimer'>{CHECKOUT_DISCLAIMER}</div>", unsafe_allow_html=True)
    st.checkbox(TERMS_CHECKBOX, key="agreed_terms")
    st.caption("Read the Terms (in the menu) before checking the box. Checkout stays closed until it's checked.")
    if not ctx.price_id:
        st.error(PRICE_SETUP_ERROR)
        return
    if not ctx.local_sandbox and not ctx.unlock_token:
        st.error(UNLOCK_TOKEN_SETUP_ERROR)
        return
    if not st.session_state.get("agreed_terms"):
        st.info("Check the box to agree to the Terms before checkout.")
        return
    if not st.session_state.get("user_logged_in"):
        st.markdown("**Create an account or log in so the report stays unlocked. No subscription.**")
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
        st.info("Checkout is not available for this visit.")


def _results(ctx: Ctx):
    quote = _quote_from_state()
    audit = build_audit(quote)
    if not audit.ok:
        for error in audit.errors:
            st.error(error)
        if st.button("Edit quote"):
            st.session_state.show_results = False
            st.rerun()
        return
    unlocked = unlock_is_active(st.session_state.get("unlock_row"))
    _rules()
    st.markdown(f"## {html.escape(quote.vehicle or 'Your quote')} · {STATE_NAMES.get(audit.state, audit.state)}")
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div class='card'>Out-the-door total<p class='big'>{_money(audit.out_the_door)}</p>"
                "<small>as entered, after trade-in</small></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='card'>Items to question<p class='big coral'>{audit.flagged_count}</p>"
                "<small>optional, unclear, or above a state amount</small></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='card'>Optional or above-limit dollars<p class='big coral'>{_money(audit.removable_total)}</p>"
                f"<small>{audit.removable_pct_of_price}% of the vehicle price</small></div>", unsafe_allow_html=True)
    st.markdown("### Where the money goes")
    _category_chart(audit)

    flagged = flagged_lines(audit)
    if unlocked:
        _paid_report(quote, audit)
    else:
        st.markdown("### Free preview")
        if flagged:
            st.caption("The top item we'd ask about:")
            _line_card(flagged[0])
        else:
            st.success("Nothing on this quote looks optional or unclear by our rules. Confirm the taxes with your state.")
        rest = flagged[1:]
        if rest:
            names = "".join(
                f"<div class='line blur-target'><span class='amt'>$•••</span><b>{html.escape(line.label)}</b><br>"
                "Explanation, source and what to ask</div>"
                for line in rest
            )
            st.markdown(names, unsafe_allow_html=True)
        st.markdown(
            "<div class='lock'><b>Full report — one-time $" + str(PRICE_DOLLARS) + "</b><ul>"
            "<li>A verdict and plain-English explanation for every line, with the state source</li>"
            "<li>Doc-fee check against your state's published limit</li>"
            "<li>A ready-to-edit message asking the dealer for a revised out-the-door price</li>"
            "<li>Monthly payment with and without the optional items (if financing)</li>"
            "<li>Questions to ask before you sign, and a PDF to bring with you</li></ul>"
            "No subscription. 7-day refund on request.</div>",
            unsafe_allow_html=True,
        )
        with st.expander(UNLOCK_BUTTON, expanded=bool(st.session_state.get("agreed_terms"))):
            _checkout_panel(ctx, audit.state or "")
    _save_panel(ctx, quote, audit)
    st.markdown(f"<div class='disclaimer'>{RESULTS_DISCLAIMER}</div>", unsafe_allow_html=True)
    if st.button("Edit quote"):
        st.session_state.show_results = False
        st.rerun()


def _paid_report(quote: QuoteInput, audit):
    st.success("Full report unlocked.")
    if audit.monthly_payment is not None:
        st.markdown("### Payment check")
        c1, c2, c3 = st.columns(3)
        c1.metric("Estimated payment as quoted", f"{_money(audit.monthly_payment)}/mo")
        c2.metric("Without the optional items", f"{_money(audit.monthly_without_removable)}/mo")
        c3.metric("Those items cost over the loan", _money(audit.finance_cost_of_removable))
        st.caption(
            f"Standard loan math on {_money(audit.amount_financed)} financed at {quote.apr}% for {quote.term_months} months. "
            "Your actual payment depends on the lender's terms."
        )
    rule = doc_fee_rule(audit.state)
    st.markdown("### Doc fee check")
    if rule.kind == "none":
        st.write(f"{STATE_NAMES.get(audit.state, audit.state)}: {rule.note}")
    else:
        limit = audit.doc_fee_limit
        kind = "limit" if rule.kind == "cap" else "presumed-reasonable amount"
        st.write(
            f"{STATE_NAMES.get(audit.state, audit.state)} {kind} we found: **{_money(limit)}**. "
            f"Doc-type fees on this quote: **{_money(audit.doc_fee_total)}**. {rule.note} Source: {rule.citation}."
        )
        if rule.source:
            st.markdown(f"[State source]({rule.source})")
    if audit.implied_tax_rate is not None:
        st.caption(f"Tax lines equal {audit.implied_tax_rate}% of the vehicle price. Compare it to your state and local rate.")
    st.markdown("### Every line")
    for line in audit.lines:
        _line_card(line)
    st.markdown("### Message you can edit and send")
    text = counter_offer_text(quote, audit)
    st.text_area("Message", value=text, height=320, key="script_box")
    st.caption(SCRIPT_DISCLAIMER)
    c1, c2 = st.columns(2)
    c1.download_button("Download message (.txt)", text, file_name="dealer-fee-check-message.txt")
    try:
        c2.download_button(
            "Download full report (PDF)", build_report_pdf(quote, audit), file_name="dealer-fee-check.pdf", mime="application/pdf"
        )
    except Exception:
        c2.caption("The PDF could not be built for this quote.")
    st.markdown("### Questions to ask before you sign")
    for question in QUESTIONS_TO_ASK:
        st.markdown(f"- {question}")


def _save_panel(ctx: Ctx, quote: QuoteInput, audit):
    if not st.session_state.get("user_logged_in"):
        return
    with st.expander("Save this quote"):
        name = st.text_input("Name", value=quote.vehicle or "My quote", key="save_name")
        if st.button("Save quote"):
            try:
                ctx.supabase.table("dealer_fee_quotes").insert(
                    quote_row(st.session_state.user_id, name, quote, audit, _now())
                ).execute()
                st.success("Saved.")
            except Exception as exc:
                st.error(f"Could not save: {exc}")


def _my_quotes(ctx: Ctx):
    st.markdown("## My quotes")
    if not st.session_state.get("user_logged_in"):
        st.info("Log in from the menu to save and compare quotes.")
        return
    try:
        rows = ctx.supabase.table("dealer_fee_quotes").select("*").eq("user_id", st.session_state.user_id).execute().data or []
    except Exception as exc:
        st.error(f"Could not load saved quotes: {exc}")
        return
    if not rows:
        st.caption("No saved quotes yet.")
        return
    for row in sort_newest_first(rows):
        summary = row.get("summary") or {}
        st.markdown(
            f"<div class='line'><b>{html.escape(row.get('name') or 'Quote')}</b> · "
            f"{_money(summary.get('out_the_door'))} out the door · {summary.get('flagged_count', 0)} items to question</div>",
            unsafe_allow_html=True,
        )
        if st.button("Open", key=f"open_{row.get('id')}"):
            quote = quote_from_dict(row.get("inputs") or {})
            st.session_state.residence = CODE_TO_LABEL.get(quote.state, CODE_TO_LABEL["TX"])
            st.session_state.condition = "New" if quote.condition == "new" else "Used"
            st.session_state.vehicle_price = quote.vehicle_price
            st.session_state.vehicle = quote.vehicle
            st.session_state.items_base = pd.DataFrame(
                [{"Line item": i.label, "Amount ($)": i.amount, "Category": CATEGORY_LABELS.get(i.category, "Auto-detect") if i.category else "Auto-detect"} for i in quote.items]
            )
            st.session_state.items_df = st.session_state.items_base
            st.session_state.editor_version += 1
            st.session_state.show_results = True
            _go("Check a quote")
            st.rerun()


def _method():
    _rules()
    st.markdown("## How we check")
    for paragraph in METHOD_PARAGRAPHS:
        st.write(paragraph)
    st.markdown("### State doc-fee amounts we use")
    table = [
        {
            "State": STATE_NAMES[code],
            "Type": "Limit" if rule.kind == "cap" else "Presumed reasonable",
            "Amount": _money(rule.cap) + (f" or {int(rule.pct_cap * 100)}% of price if less" if rule.pct_cap else ""),
            "Source": rule.citation,
        }
        for code, rule in sorted(DOC_FEE_RULES.items(), key=lambda item: STATE_NAMES[item[0]])
    ]
    st.dataframe(pd.DataFrame(table), hide_index=True, width="stretch")
    st.caption("All other states and DC: we found no state dollar limit.")
    st.markdown("### Sources")
    for label, url in SOURCES:
        st.markdown(f"- [{label}]({url})")
    st.markdown(f"<div class='disclaimer'>{RESULTS_DISCLAIMER}</div>", unsafe_allow_html=True)


def _disclaimer_page():
    st.markdown("## Disclaimer")
    for title, text in (
        ("Every page", LANDING_STRIP),
        ("Footer", SHORT_DISCLAIMER),
        ("Results", RESULTS_DISCLAIMER),
        ("Checkout", CHECKOUT_DISCLAIMER),
        ("Message template", SCRIPT_DISCLAIMER),
    ):
        st.markdown(f"**{title}**")
        st.markdown(f"<div class='disclaimer'>{text}</div>", unsafe_allow_html=True)


def run(ctx: Ctx):
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
    if not ctx.local_sandbox and not ctx.unlock_token:
        st.error(UNLOCK_TOKEN_SETUP_ERROR)
    _handle_checkout_return(ctx)
    _sidebar(ctx)
    page = st.session_state.get("nav") or "Home"
    if page == "Home":
        _landing()
    elif page == "Check a quote":
        if st.session_state.get("show_results"):
            _results(ctx)
        else:
            _entry()
    elif page == "My quotes":
        _my_quotes(ctx)
    elif page == "How we check":
        _method()
    elif page == "Disclaimer":
        _disclaimer_page()
    elif page == "Terms":
        st.markdown(terms_markdown())
    elif page == "Privacy":
        st.markdown(privacy_markdown())
    _footer()
