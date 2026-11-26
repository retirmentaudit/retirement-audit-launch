"""Behavior checks for the retirement wizard fixes.

These run the Streamlit script with local dummy secrets (gitignored) and do not
call OpenAI, Stripe, or a real Supabase project.
"""

from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = str(ROOT / "app.py")


def _markdown_text(at: AppTest) -> str:
    parts = [getattr(el, "value", "") or "" for el in at.markdown]
    parts.extend(getattr(el, "value", "") or "" for el in at.caption)
    return "\n".join(parts)


def _labels(widgets) -> list[str]:
    return [getattr(widget, "label", "") or "" for widget in widgets]


def _boot(**state) -> AppTest:
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.session_state["started"] = True
    for key, value in state.items():
        at.session_state[key] = value
    at.run()
    assert not at.exception, at.exception
    return at


def test_just_me_hides_spouse_fields_and_ignores_spouse_balances():
    at = _boot(wizard_step=2, planning_for="Just me", spouse2_age=70)
    labels = _labels(at.number_input)
    assert "Your current age" in labels
    assert "Target retirement age" in labels
    assert not any("Spouse" in label for label in labels)

    at.session_state["wizard_step"] = 4
    at.run()
    assert not at.exception, at.exception
    labels = _labels(at.number_input)
    assert "Your average annual earnings" in labels
    assert not any(label.startswith("Spouse") for label in labels)

    at.session_state["wizard_step"] = 7
    at.session_state["spouse2_use_traditional_401k"] = True
    at.session_state["spouse2_trad_401k_bal"] = 250000
    at.session_state["spouse2_trad_401k_cont"] = 10000
    at.session_state["avg_earn_sp2"] = 120000
    at.session_state["pen_sp2"] = 40000
    at.session_state["use_pension"] = True
    at.run()
    assert not at.exception, at.exception
    text = _markdown_text(at)
    assert "Enter a balance or income to see your score" in text
    assert "41 / 100" not in text
    assert "$250,000" not in text


def test_me_plus_spouse_shows_spouse_fields_and_uses_spouse_balance():
    at = _boot(wizard_step=2, planning_for="Me + spouse")
    labels = _labels(at.number_input)
    assert "Spouse's current age" in labels

    at.session_state["wizard_step"] = 4
    at.run()
    assert not at.exception, at.exception
    labels = _labels(at.number_input)
    assert any(label.startswith("Spouse") for label in labels)

    at.session_state["wizard_step"] = 7
    at.session_state["spouse1_use_traditional_401k"] = True
    at.session_state["spouse1_trad_401k_bal"] = 10000
    at.run()
    assert not at.exception, at.exception
    text = _markdown_text(at)
    assert "Retirement Score:" in text
    assert "41 / 100" not in text
    assert "Enter a balance or income to see your score" not in text


def test_blank_plan_does_not_show_baseline_score():
    at = _boot(wizard_step=7, planning_for="Just me", avg_earn_sp1=0)
    text = _markdown_text(at)
    assert "Enter a balance or income to see your score" in text
    assert "41 / 100" not in text
    assert "Retirement Score:" not in text


def test_earnings_alone_show_score_with_explanation():
    at = _boot(wizard_step=7, planning_for="Just me", avg_earn_sp1=60000)
    text = _markdown_text(at)
    joined = text + "\n" + "\n".join(el.value for el in at.info)
    assert "Retirement Score:" in text
    assert "no investment balance" in joined


def test_target_retirement_age_cannot_default_below_current_age():
    at = _boot(
        wizard_step=2,
        planning_for="Just me",
        spouse1_age=72,
        retirement_age=65,
    )
    target = next(widget for widget in at.number_input if widget.label == "Target retirement age")
    assert target.min == 72
    assert target.max == 80
    assert int(at.session_state["retirement_age"]) >= 72
    assert "Your current age" in _labels(at.number_input)
    assert not any(widget.label == "Target retirement age" and widget.min == 40 for widget in at.number_input)


def test_younger_user_keeps_age_65_default_and_clear_range():
    at = _boot(wizard_step=2, planning_for="Just me", spouse1_age=35, retirement_age=65)
    target = next(widget for widget in at.number_input if widget.label == "Target retirement age")
    assert target.min == 40
    assert target.max == 80
    assert int(at.session_state["retirement_age"]) == 65
    assert "must be from 40 to 80" in _markdown_text(at)


def test_creator_footer_is_spelled_correctly_and_blank_text_rule_is_gone():
    at = _boot(wizard_step=1, planning_for="Just me")
    text = _markdown_text(at)
    assert "Created by retirementaudit" in text
    assert "Created by retirmentaudit" not in text
    assert "div, span { color: white !important; }" not in text
    assert 'toolbarMode = "minimal"' in (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
