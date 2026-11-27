"""Row builders for dealer_fee_quotes and unlocks. No network calls."""

from __future__ import annotations

from engine import QuoteAudit, QuoteInput, quote_to_dict

PRODUCT = "dealer_fee_audit"


def quote_row(user_id: str, name: str, quote: QuoteInput, audit: QuoteAudit, now_iso: str) -> dict:
    label = (name or "").strip() or (quote.vehicle or "").strip() or "My quote"
    return {
        "user_id": user_id,
        "name": label[:120],
        "inputs": quote_to_dict(quote),
        "summary": {
            "out_the_door": audit.out_the_door,
            "removable_total": audit.removable_total,
            "flagged_count": audit.flagged_count,
            "state": audit.state,
        },
        "created_at": now_iso,
        "updated_at": now_iso,
    }


def unlock_is_active(row: dict | None) -> bool:
    if not row:
        return False
    return row.get("product") == PRODUCT and bool(row.get("stripe_checkout_session_id") or row.get("paid_at"))


def sort_newest_first(rows: list[dict]) -> list[dict]:
    return sorted(rows or [], key=lambda row: row.get("updated_at") or row.get("created_at") or "", reverse=True)
