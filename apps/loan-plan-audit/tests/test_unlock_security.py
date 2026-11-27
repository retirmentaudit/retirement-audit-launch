"""Unlock writes. These tests do not call Stripe or Supabase."""

from pathlib import Path

from checkout import PRODUCT, commit_unlock, unlock_record_decision

NOW = "2026-11-27T00:00:00+00:00"
TOKEN = "local-demo-unlock-token"
PRICE = "price_loan"
ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "supabase" / "migrations" / "20261128_loan_unlock_server_write.sql"
APPLIED = ROOT / "supabase" / "migrations" / "20261127_loan_plan_audit.sql"


def _paid(user_id="user-1", session_id="cs_test_paid", price=PRICE):
    return {
        "id": session_id,
        "payment_status": "paid",
        "mode": "payment",
        "client_reference_id": user_id,
        "customer_email": "a@example.com",
        "customer": "cus_123",
        "metadata": {
            "user_id": user_id,
            "product": PRODUCT,
            "price_id": price,
            "purchase": "one_time",
        },
        "line_items": {"data": [{"price": {"id": price}}]},
    }


def test_forged_unlock_attempt_is_rejected():
    paid = _paid()
    forged = commit_unlock(
        session=paid,
        user_id="user-1",
        email="a@example.com",
        existing_rows=[],
        now_iso=NOW,
        expected_price_id=PRICE,
        token="not-the-recording-token",
        configured_token=TOKEN,
    )
    assert forged["recorded"] is False
    assert forged["reason"] == "forged"
    assert forged["update"] is None

    missing = unlock_record_decision(
        caller_id="user-1",
        session_id="cs_test_paid",
        token=None,
        configured_token=TOKEN,
        existing_rows=[],
    )
    assert missing["reason"] == "forged"
    assert missing["write"] is False

    short = unlock_record_decision(
        caller_id="user-1",
        session_id="cs_test_paid",
        token="short-token",
        configured_token="short-token",
        existing_rows=[],
    )
    assert short["reason"] == "forged"


def test_unpaid_session_does_not_unlock():
    unpaid = _paid()
    unpaid["payment_status"] = "unpaid"
    result = commit_unlock(
        session=unpaid,
        user_id="user-1",
        email="a@example.com",
        existing_rows=[],
        now_iso=NOW,
        expected_price_id=PRICE,
        token=TOKEN,
        configured_token=TOKEN,
    )
    assert result["recorded"] is False
    assert result["reason"] == "unpaid"

    wrong_price = _paid(price="price_other")
    rejected = commit_unlock(
        session=wrong_price,
        user_id="user-1",
        email="a@example.com",
        existing_rows=[],
        now_iso=NOW,
        expected_price_id=PRICE,
        token=TOKEN,
        configured_token=TOKEN,
    )
    assert rejected["recorded"] is False
    assert rejected["reason"] == "price_mismatch"

    disagreed = _paid()
    disagreed["line_items"] = {"data": [{"price": {"id": "price_other"}}]}
    line_item = commit_unlock(
        session=disagreed,
        user_id="user-1",
        email="a@example.com",
        existing_rows=[],
        now_iso=NOW,
        expected_price_id=PRICE,
        token=TOKEN,
        configured_token=TOKEN,
    )
    assert line_item["recorded"] is False
    assert line_item["reason"] == "price_mismatch"


def test_session_reused_by_another_user_does_not_unlock():
    paid = _paid(user_id="user-1", session_id="cs_test_once")
    stolen = commit_unlock(
        session=paid,
        user_id="user-2",
        email="b@example.com",
        existing_rows=[],
        now_iso=NOW,
        expected_price_id=PRICE,
        token=TOKEN,
        configured_token=TOKEN,
    )
    assert stolen["recorded"] is False
    assert stolen["reason"] == "user_mismatch"

    already = [
        {
            "user_id": "user-1",
            "product": PRODUCT,
            "stripe_checkout_session_id": "cs_test_once",
        }
    ]
    reused = unlock_record_decision(
        caller_id="user-2",
        session_id="cs_test_once",
        token=TOKEN,
        configured_token=TOKEN,
        existing_rows=already,
    )
    assert reused["reason"] == "session_reused"
    assert reused["write"] is False

    # The paid user can return again. That does not write a second row.
    again = commit_unlock(
        session=paid,
        user_id="user-1",
        email="a@example.com",
        existing_rows=already,
        now_iso=NOW,
        expected_price_id=PRICE,
        token=TOKEN,
        configured_token=TOKEN,
    )
    assert again["recorded"] is False
    assert again["reason"] == "already_unlocked"


def test_paid_matching_session_may_be_recorded_once():
    result = commit_unlock(
        session=_paid(),
        user_id="user-1",
        email="a@example.com",
        existing_rows=[],
        now_iso=NOW,
        expected_price_id=PRICE,
        token=TOKEN,
        configured_token=TOKEN,
    )
    assert result["recorded"] is True
    assert result["update"]["user_id"] == "user-1"
    assert result["update"]["stripe_checkout_session_id"] == "cs_test_paid"
    assert "is_paid_user" not in result["update"]


def test_new_migration_removes_user_writes_and_leaves_the_applied_file_alone():
    sql = MIGRATION.read_text(encoding="utf-8")
    lowered = sql.lower()
    assert 'drop policy if exists "users insert own unlocks"' in lowered
    assert 'drop policy if exists "users update own unlocks"' in lowered
    assert 'drop policy if exists "users delete own unlocks"' in lowered
    assert "revoke insert, update, delete on table public.unlocks from authenticated, anon, public" in lowered
    assert "grant select on table public.unlocks to authenticated" in lowered
    assert "security definer" in lowered
    assert "set search_path = ''" in lowered
    assert "auth.uid()" in lowered
    assert "session already used" in lowered
    assert "not allowed" in lowered
    assert "extensions.digest" in lowered
    assert "grant execute on function public.record_loan_unlock(text, text) to authenticated" in lowered
    assert "revoke all on function public.record_loan_unlock(text, text) from public, anon" in lowered
    assert "alter table public.user_profiles" not in lowered
    assert "alter table public.scenarios" not in lowered
    assert "PASTE_UNLOCK_RECORD_TOKEN" in sql

    applied = APPLIED.read_text(encoding="utf-8")
    assert 'create policy "Users insert own unlocks"' in applied
    assert "record_loan_unlock" not in applied
