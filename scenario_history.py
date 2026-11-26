"""Build and sort scenario-history rows. No network calls."""

from __future__ import annotations

import hashlib
import json


def scenarios_table_missing(message: str) -> bool:
    """True when Supabase says the scenarios table has not been created yet."""
    text = (message or "").lower()
    if "scenario" not in text:
        return False
    return any(
        phrase in text
        for phrase in (
            "does not exist",
            "could not find",
            "schema cache",
            "pgrst205",
            "not found",
        )
    )


def scenario_fingerprint(inputs: dict, score, percent_covered) -> str:
    raw = json.dumps(
        {"inputs": inputs, "score": score, "percent_covered": percent_covered},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def scenario_record(user_id: str, name: str, inputs: dict, results: dict, created_at: str) -> dict:
    """One history row. `inputs` is the audit the person entered, not only the last score."""
    label = (name or "").strip() or "My scenario"
    return {
        "user_id": user_id,
        "name": label,
        "inputs": inputs,
        "score": results.get("score"),
        "score_label": results.get("score_label"),
        "monthly_need": results.get("monthly_need"),
        "monthly_need_today": results.get("monthly_need_today"),
        "monthly_covered": results.get("monthly_covered"),
        "percent_covered": results.get("coverage_pct"),
        "created_at": created_at,
    }


def sort_scenarios_newest_first(rows: list[dict]) -> list[dict]:
    return sorted(rows or [], key=lambda row: row.get("created_at") or "", reverse=True)
