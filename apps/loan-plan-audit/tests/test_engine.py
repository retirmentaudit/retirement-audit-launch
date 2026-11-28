"""Plan math. No Streamlit, Stripe, or network."""

from datetime import date

import pytest

from engine import (
    PLAN_EXTENDED,
    PLAN_GRADUATED,
    PLAN_IBR10,
    PLAN_IBR15,
    PLAN_ICR,
    PLAN_PAYE,
    PLAN_RAP,
    PLAN_STANDARD,
    PLAN_TIERED,
    LoanInput,
    amort_payment,
    apply_rap_month,
    build_audit,
    make_scenario,
    months_until,
    poverty_guideline,
    icr_monthly,
    income_percentage_factor,
    rap_payment_dollars,
    rap_percent_points,
    scenario_from_dict,
    scenario_to_dict,
    sort_plans,
    tiered_term_months,
    weighted_rate_pct,
    PAYE_SUNSET,
)


def _plans(scenario=None, **overrides):
    audit = build_audit(scenario or make_scenario(**overrides))
    assert audit.ok, audit.errors
    assert "primary" in audit.worlds
    return {plan.plan_id: plan for plan in audit.worlds["primary"]}


def test_ed_examples_and_boundaries():
    assert rap_payment_dollars(53_000, 0) == 221
    assert rap_payment_dollars(53_000, 1) == 171
    assert rap_payment_dollars(10_000, 0) == 10
    assert rap_payment_dollars(10_000, 4) == 10
    assert rap_payment_dollars(11_000, 0) == 10
    assert rap_percent_points(10_000) is None
    assert rap_percent_points(10_000.01) == 1
    assert rap_percent_points(20_000) == 1
    assert rap_percent_points(20_000.01) == 2
    assert rap_percent_points(53_000) == 5
    assert rap_percent_points(100_000) == 9
    assert rap_percent_points(100_000.01) == 10
    assert rap_percent_points(250_000) == 10
    assert rap_payment_dollars(20_000, 0) == 17
    assert rap_payment_dollars(100_000, 0) == 750
    assert rap_payment_dollars(0, 0) == 10


def test_tier_thresholds():
    assert tiered_term_months(24_999) == 120
    assert tiered_term_months(25_000) == 180
    assert tiered_term_months(49_999) == 180
    assert tiered_term_months(50_000) == 240
    assert tiered_term_months(99_999) == 240
    assert tiered_term_months(100_000) == 300
    low = _plans(loans=(LoanInput(24_999, 5, "Direct Unsubsidized", "yes"),))
    high = _plans(loans=(LoanInput(25_000, 5, "Direct Unsubsidized", "yes"),))
    assert low[PLAN_TIERED].term_months == 120
    assert high[PLAN_TIERED].term_months == 180


def test_rap_month_subsidy_and_match():
    record, balance = apply_rap_month(10_000, 0.005, 40)
    assert record.principal == pytest.approx(0)
    assert record.waived == pytest.approx(10)
    assert record.matched == pytest.approx(40)
    assert balance == pytest.approx(9_960)

    record, balance = apply_rap_month(10_000, 0.005, 80)
    assert record.principal == pytest.approx(30)
    assert record.matched == pytest.approx(20)
    assert balance == pytest.approx(9_950)

    record, balance = apply_rap_month(10_000, 0.005, 221)
    assert record.principal == pytest.approx(171)
    assert record.matched == pytest.approx(0)
    assert balance == pytest.approx(9_829)

    record, balance = apply_rap_month(10_000, 0.01, 10)
    assert record.waived == pytest.approx(90)
    assert record.matched == pytest.approx(10)
    assert balance == pytest.approx(9_990)

    record, balance = apply_rap_month(1_000, 0.0, 10)
    assert record.matched == pytest.approx(0)
    assert record.waived == pytest.approx(0)
    assert balance == pytest.approx(990)


def test_subsidy_balance_does_not_grow_and_match_accumulates():
    plans = _plans(
        loans=(LoanInput(80_000, 6, "Direct Unsubsidized", "no"),),
        agi=30_000,
        annual_raise=0,
        poverty_inflation=0,
    )
    rap = plans[PLAN_RAP]
    assert rap.first_year_monthly == 50
    assert rap.end_reason == "idr_discharge"
    assert rap.end_month == 360
    assert rap.forgiven_amount == pytest.approx(62_000, abs=1)
    assert rap.estimated_tax == pytest.approx(62_000 * 0.22, abs=1)
    assert rap.principal_matched == pytest.approx(50 * 360, abs=1)
    assert rap.interest_waived > 0
    balances = [row["balance"] for row in rap.yearly]
    assert balances[0] < 80_000
    assert all(later <= earlier + 0.05 for earlier, later in zip(balances, balances[1:]))


def test_ibr_cap_and_zero_interest():
    cap = amort_payment(30_000, 0.06 / 12, 120)
    plans = _plans(
        loans=(LoanInput(30_000, 6, "Direct Unsubsidized", "no"),),
        agi=500_000,
        annual_raise=0,
        poverty_inflation=0,
    )
    assert plans[PLAN_IBR15].first_year_monthly == pytest.approx(cap, abs=0.02)
    assert plans[PLAN_STANDARD].first_year_monthly == pytest.approx(cap, abs=0.02)
    modest = _plans(agi=53_000, annual_raise=0, poverty_inflation=0)
    assert modest[PLAN_IBR15].first_year_monthly < modest[PLAN_STANDARD].first_year_monthly
    assert modest[PLAN_RAP].first_year_monthly == 221

    assert amort_payment(12_000, 0, 120) == pytest.approx(100)
    zero = _plans(
        loans=(LoanInput(12_000, 0, "Direct Unsubsidized", "no"),),
        agi=200_000,
        annual_raise=0,
    )
    assert zero[PLAN_STANDARD].first_year_monthly == pytest.approx(100)
    assert zero[PLAN_STANDARD].end_reason == "paid_off"
    assert zero[PLAN_STANDARD].end_month == 120
    assert zero[PLAN_STANDARD].interest_paid == pytest.approx(0, abs=0.05)
    assert zero[PLAN_STANDARD].forgiven_amount == pytest.approx(0, abs=0.05)
    assert zero[PLAN_STANDARD].total_paid == pytest.approx(12_000, abs=0.05)
    assert zero[PLAN_IBR15].first_year_monthly == pytest.approx(100, abs=0.05)


def test_parent_plus_and_ffel_hide_rap():
    parent = _plans(loans=(LoanInput(40_000, 6.5, "Parent PLUS", "no"),))
    assert parent[PLAN_RAP].eligible is False
    assert "Parent PLUS" in parent[PLAN_RAP].chips[0]
    assert parent[PLAN_STANDARD].eligible is True
    assert parent[PLAN_GRADUATED].eligible is True
    assert parent[PLAN_IBR15].eligible is False
    assert parent[PLAN_PAYE].eligible is False
    assert parent[PLAN_ICR].eligible is False

    ffel = _plans(loans=(LoanInput(40_000, 6.5, "FFEL", "no"),))
    assert ffel[PLAN_RAP].eligible is False
    assert "FFEL" in ffel[PLAN_RAP].chips[0]
    assert ffel[PLAN_IBR15].eligible is True
    assert ffel[PLAN_PAYE].eligible is False
    assert ffel[PLAN_ICR].eligible is False

    consolidation = _plans(
        loans=(LoanInput(40_000, 6.5, "Consolidation", "no", True),),
    )
    assert consolidation[PLAN_RAP].eligible is False
    assert consolidation[PLAN_PAYE].eligible is False
    assert consolidation[PLAN_IBR15].eligible is False
    assert consolidation[PLAN_ICR].eligible is True
    assert "July 1, 2028" in " ".join(consolidation[PLAN_ICR].chips)


def test_post_2026_only_rap_and_tiered_and_not_sure_shows_both():
    post = _plans(loans=(LoanInput(40_000, 6.5, "Direct Unsubsidized", "yes"),))
    assert post[PLAN_RAP].eligible is True
    assert post[PLAN_TIERED].eligible is True
    assert post[PLAN_STANDARD].eligible is False
    assert post[PLAN_GRADUATED].eligible is False
    assert post[PLAN_EXTENDED].eligible is False
    assert post[PLAN_IBR15].eligible is False
    assert post[PLAN_PAYE].eligible is False
    assert post[PLAN_ICR].eligible is False

    mixed = _plans(
        loans=(
            LoanInput(10_000, 5, "Direct Subsidized", "no"),
            LoanInput(5_000, 6, "Direct Unsubsidized", "yes"),
        )
    )
    assert mixed[PLAN_STANDARD].eligible is False
    assert mixed[PLAN_RAP].eligible is True

    audit = build_audit(make_scenario(loans=(LoanInput(40_000, 6.5, "Direct Unsubsidized", "not_sure"),)))
    assert audit.uncertain is True
    assert "pre_july_2026" in audit.worlds
    assert "on_or_after_july_2026" in audit.worlds
    pre = {plan.plan_id: plan for plan in audit.worlds["pre_july_2026"]}
    after = {plan.plan_id: plan for plan in audit.worlds["on_or_after_july_2026"]}
    assert pre[PLAN_STANDARD].eligible is True
    assert after[PLAN_TIERED].eligible is True
    assert after[PLAN_STANDARD].eligible is False


def test_pslf_is_tax_free_and_tiered_does_not_count():
    plans = _plans(
        loans=(LoanInput(80_000, 6, "Direct Unsubsidized", "no"),),
        agi=30_000,
        annual_raise=0,
        pslf_job=True,
        pslf_months_credited=33,
    )
    rap = plans[PLAN_RAP]
    assert rap.counts_for_pslf is True
    assert rap.end_reason == "pslf"
    assert rap.end_month == 87
    assert rap.forgiven_amount > 1000
    assert rap.estimated_tax == 0
    assert rap.pslf_date is not None

    post = _plans(
        loans=(LoanInput(40_000, 6.5, "Direct Unsubsidized", "yes"),),
        pslf_job=True,
        pslf_months_credited=33,
    )
    tier = post[PLAN_TIERED]
    assert tier.counts_for_pslf is False
    assert "Does not count toward PSLF" in tier.chips
    assert tier.end_reason == "paid_off"
    assert tier.end_month > 120
    assert tier.forgiven_amount == pytest.approx(0, abs=0.05)


def test_zero_payment_ibr_grows_and_is_taxed_unless_pslf():
    plans = _plans(
        loans=(LoanInput(10_000, 6, "Direct Unsubsidized", "no"),),
        agi=0,
        annual_raise=0,
        poverty_inflation=0,
    )
    ibr = plans[PLAN_IBR15]
    assert ibr.first_year_monthly == 0
    assert ibr.end_month == 300
    assert ibr.end_reason == "idr_discharge"
    assert ibr.forgiven_amount > 10_000
    assert ibr.estimated_tax == pytest.approx(ibr.forgiven_amount * 0.22, rel=0.01)

    pslf = _plans(
        loans=(LoanInput(10_000, 6, "Direct Unsubsidized", "no"),),
        agi=0,
        annual_raise=0,
        pslf_job=True,
    )
    assert pslf[PLAN_IBR15].end_reason == "pslf"
    assert pslf[PLAN_IBR15].end_month == 120
    assert pslf[PLAN_IBR15].estimated_tax == 0


def test_mfj_uses_spouse_income_and_mfs_does_not():
    separate = _plans(agi=30_000, spouse_agi=30_000, filing_status="mfs", annual_raise=0)
    joint = _plans(agi=30_000, spouse_agi=30_000, filing_status="mfj", annual_raise=0)
    assert separate[PLAN_RAP].first_year_monthly == 50
    assert joint[PLAN_RAP].first_year_monthly == 250


def test_poverty_tables_and_autopay_rate():
    assert poverty_guideline(1, "TX") == 15_960
    assert poverty_guideline(4, "CA") == 33_000
    assert poverty_guideline(1, "AK") == 19_950
    assert poverty_guideline(2, "HI") == 24_890
    assert poverty_guideline(1, "TX", year_offset=1, inflation=0.025) == pytest.approx(15_960 * 1.025)
    weighted = weighted_rate_pct(
        (
            LoanInput(10_000, 5, "Direct Subsidized", "no"),
            LoanInput(30_000, 7, "Direct Unsubsidized", "no"),
        )
    )
    assert weighted == pytest.approx(6.5)
    audit = build_audit(
        make_scenario(
            loans=(
                LoanInput(10_000, 5, "Direct Subsidized", "no"),
                LoanInput(30_000, 7, "Direct Unsubsidized", "no"),
            ),
            autopay=True,
        )
    )
    assert audit.modeled_rate_pct == pytest.approx(5.5)
    off = build_audit(make_scenario())
    assert off.modeled_rate_pct == pytest.approx(off.weighted_rate_pct)


def test_paye_sunset_and_sort_and_round_trip():
    assert months_until(date(2026, 12, 1), PAYE_SUNSET) == 19
    plans = _plans(annual_raise=0, poverty_inflation=0)
    paye = plans[PLAN_PAYE]
    assert paye.eligible is True
    assert "Closing by July 1, 2028" in paye.chips
    assert any("July 1, 2028" in note for note in paye.notes)
    ordered = sort_plans(list(plans.values()), "monthly")
    amounts = [plan.first_year_monthly for plan in ordered if plan.eligible]
    assert amounts == sorted(amounts)
    restored = scenario_from_dict(scenario_to_dict(make_scenario(state="NY", dependents=2)))
    assert restored.state == "NY"
    assert restored.dependents == 2
    assert restored.loans[0].balance == 40_000


def test_state_is_required_and_new_borrower_percent():
    missing = build_audit(make_scenario(state=""))
    assert missing.ok is False
    assert any("state" in error.lower() for error in missing.errors)
    ten = _plans(new_borrower_after_2014="yes", agi=53_000, annual_raise=0, poverty_inflation=0)
    fifteen = _plans(new_borrower_after_2014="no", agi=53_000, annual_raise=0, poverty_inflation=0)
    assert ten[PLAN_IBR10].eligible is True
    assert ten[PLAN_IBR15].eligible is False
    assert fifteen[PLAN_IBR10].eligible is False
    assert ten[PLAN_IBR10].first_year_monthly < fifteen[PLAN_IBR15].first_year_monthly
    assert ten[PLAN_IBR10].term_months == 240
    assert fifteen[PLAN_IBR15].term_months == 300


def test_icr_matches_the_2026_federal_register_examples():
    assert income_percentage_factor(50_000, "single") == pytest.approx(0.8683, abs=0.00001)
    assert income_percentage_factor(35_104, "single") == pytest.approx(0.7189, abs=0.00001)
    kesha = make_scenario(
        loans=(LoanInput(15_000, 6, "Direct Unsubsidized", "no"),),
        agi=35_104,
        filing_status="single",
        family_size=1,
        state="TX",
        annual_raise=0,
        poverty_inflation=0,
    )
    base = amort_payment(15_000, 0.06 / 12, 144)
    assert icr_monthly(35_104, kesha, 0, base) == pytest.approx(105.23, abs=0.05)
    plans = _plans(
        loans=(LoanInput(15_000, 6, "Direct Unsubsidized", "no"),),
        agi=35_104,
        annual_raise=0,
        poverty_inflation=0,
        family_size=1,
    )
    assert plans[PLAN_ICR].eligible is True
    assert plans[PLAN_ICR].first_year_monthly == pytest.approx(105.23, abs=0.05)
    assert "Closing by July 1, 2028" in plans[PLAN_ICR].chips

    santiago = make_scenario(
        loans=(LoanInput(60_000, 6, "Direct Unsubsidized", "no"),),
        agi=41_769,
        family_size=1,
        state="TX",
        annual_raise=0,
        poverty_inflation=0,
    )
    santiago_base = amort_payment(60_000, 0.06 / 12, 144)
    assert icr_monthly(41_769, santiago, 0, santiago_base) == pytest.approx(430.15, abs=0.05)


def test_graduated_and_extended_for_older_loans():
    zero = _plans(
        loans=(LoanInput(12_000, 0, "Direct Unsubsidized", "no"),),
        agi=40_000,
        annual_raise=0,
    )
    graduated = zero[PLAN_GRADUATED]
    assert graduated.eligible is True
    assert graduated.term_months == 120
    assert graduated.counts_for_pslf is False
    assert graduated.end_reason == "paid_off"
    assert graduated.total_paid == pytest.approx(12_000, abs=1)
    assert zero[PLAN_EXTENDED].eligible is False

    older = _plans(loans=(LoanInput(40_000, 6.5, "Direct Unsubsidized", "no"),))
    assert older[PLAN_EXTENDED].eligible is True
    assert older[PLAN_EXTENDED].term_months == 300
    assert older[PLAN_EXTENDED].counts_for_pslf is False
    assert older[PLAN_GRADUATED].first_year_monthly < older[PLAN_EXTENDED].first_year_monthly

    border = _plans(loans=(LoanInput(30_000, 5, "Direct Unsubsidized", "no"),))
    assert border[PLAN_EXTENDED].eligible is False
    above = _plans(loans=(LoanInput(30_000.01, 5, "Direct Unsubsidized", "no"),))
    assert above[PLAN_EXTENDED].eligible is True
