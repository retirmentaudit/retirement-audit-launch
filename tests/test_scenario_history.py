"""Scenario history rows. No Stripe, Supabase, or Streamlit."""

from scenario_history import (
    scenario_fingerprint,
    scenario_record,
    scenarios_table_missing,
    sort_scenarios_newest_first,
)


def test_missing_table_errors_are_recognized():
    assert scenarios_table_missing("Could not find the table 'public.scenarios' in the schema cache")
    assert scenarios_table_missing('relation "public.scenarios" does not exist')
    assert not scenarios_table_missing("permission denied for table scenarios")
    assert not scenarios_table_missing("network down")


def test_scenario_row_stores_inputs_score_and_coverage():
    results = {
        "score": 69,
        "score_label": "Moderate",
        "monthly_need": 4000,
        "monthly_need_today": 4000,
        "monthly_covered": 3179,
        "coverage_pct": 79,
    }
    row = scenario_record("user-1", "  Winter plan  ", {"retirement_age": 65}, results, "2026-11-26T12:00:00+00:00")
    assert row["user_id"] == "user-1"
    assert row["name"] == "Winter plan"
    assert row["inputs"]["retirement_age"] == 65
    assert row["score"] == 69
    assert row["percent_covered"] == 79
    assert row["monthly_need"] == 4000
    assert row["created_at"] == "2026-11-26T12:00:00+00:00"


def test_same_result_has_a_stable_fingerprint_and_list_is_newest_first():
    inputs = {"retirement_age": 65, "avg_earn_sp1": 60000}
    first = scenario_fingerprint(inputs, 69, 79)
    second = scenario_fingerprint({"avg_earn_sp1": 60000, "retirement_age": 65}, 69, 79)
    changed = scenario_fingerprint(inputs, 70, 79)
    assert first == second
    assert first != changed
    rows = sort_scenarios_newest_first([
        {"name": "Older", "created_at": "2026-01-01T00:00:00+00:00"},
        {"name": "Newer", "created_at": "2026-06-01T00:00:00+00:00"},
    ])
    assert [row["name"] for row in rows] == ["Newer", "Older"]
