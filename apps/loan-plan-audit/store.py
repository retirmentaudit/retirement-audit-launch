"""Row builders for loan_scenarios and unlocks. No network calls."""

from __future__ import annotations

import hashlib
import json

from engine import AuditResult, PlanResult, ScenarioInput, scenario_to_dict


def table_missing(message: str, table: str) -> bool:
    text = (message or "").lower()
    if table not in text and "schema cache" not in text and "pgrst205" not in text:
        return False
    return any(
        phrase in text
        for phrase in (
            "does not exist",
            "could not find",
            "schema cache",
            "pgrst205",
            "not found",
            table,
        )
    )


def summary_from_audit(audit: AuditResult) -> dict:
    """Compact numbers for the scenario list. The full path is recomputed on open."""
    worlds = {}
    for key, plans in audit.worlds.items():
        worlds[key] = [
            {
                "plan_id": plan.plan_id,
                "label": plan.label,
                "eligible": plan.eligible,
                "first_year_monthly": plan.first_year_monthly,
                "total_paid": plan.total_paid,
                "end_date": plan.end_date,
                "end_reason": plan.end_reason,
            }
            for plan in plans
        ]
    return {
        "worlds": worlds,
        "total_balance": audit.total_balance,
        "agi_used": audit.agi_used,
        "uncertain": audit.uncertain,
        "state": audit.state,
    }


def scenario_row(user_id: str, name: str, scenario: ScenarioInput, audit: AuditResult, now_iso: str) -> dict:
    label = (name or "").strip() or "My scenario"
    return {
        "user_id": user_id,
        "name": label,
        "inputs": scenario_to_dict(scenario),
        "summary": summary_from_audit(audit),
        "created_at": now_iso,
        "updated_at": now_iso,
    }


def scenario_fingerprint(scenario: ScenarioInput) -> str:
    raw = json.dumps(scenario_to_dict(scenario), sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def sort_newest_first(rows: list[dict]) -> list[dict]:
    return sorted(rows or [], key=lambda row: row.get("updated_at") or row.get("created_at") or "", reverse=True)


def unlock_is_active(row: dict | None) -> bool:
    if not row:
        return False
    return row.get("product") == "loan_plan_audit" and bool(row.get("stripe_checkout_session_id") or row.get("paid_at"))


def diff_plans(left: list[PlanResult], right: list[PlanResult]) -> list[dict]:
    """Estimated difference, right minus left, for plans that are eligible on both sides."""
    right_by_id = {plan.plan_id: plan for plan in right if plan.eligible}
    rows = []
    for plan in left:
        other = right_by_id.get(plan.plan_id)
        if not plan.eligible or other is None or plan.first_year_monthly is None or other.first_year_monthly is None:
            continue
        rows.append(
            {
                "plan_id": plan.plan_id,
                "label": plan.label,
                "monthly_difference": round(other.first_year_monthly - plan.first_year_monthly, 2),
                "total_difference": None
                if plan.total_paid is None or other.total_paid is None
                else round(other.total_paid - plan.total_paid, 2),
            }
        )
    return rows
