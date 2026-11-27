"""Quote analysis rules. No network."""

import pytest

from engine import (
    V_ASK,
    V_EXPECTED,
    V_HIGH,
    V_OPTIONAL,
    V_OVER,
    V_VERIFY,
    LineItem,
    QuoteInput,
    amortized_payment,
    build_audit,
    counter_offer_text,
    flagged_lines,
    make_sample_quote,
    quote_from_dict,
    quote_to_dict,
)
from fees import CAT_DOC, CAT_GOV, DOC_FEE_RULES, classify, doc_fee_rule


def _quote(state="NY", items=None, price=30_000.0, condition="new", **kw):
    return QuoteInput(state=state, condition=condition, vehicle_price=price, items=items or [], **kw)


def _verdict(audit, label):
    return next(line for line in audit.lines if line.label == label).verdict


@pytest.mark.parametrize(
    "label,category",
    [
        ("Doc fee", "doc_fee"),
        ("Documentation Fee", "doc_fee"),
        ("Administrative fee", "doc_fee"),
        ("Sales tax", "government"),
        ("Title & registration", "government"),
        ("Destination", "destination"),
        ("Freight", "destination"),
        ("Market adjustment", "market_adjustment"),
        ("ADM", "market_adjustment"),
        ("VIN etching", "dealer_addon"),
        ("Nitrogen tires", "dealer_addon"),
        ("Window tint", "dealer_addon"),
        ("Paint protection", "dealer_addon"),
        ("GAP", "fi_product"),
        ("Extended warranty", "fi_product"),
        ("Manufacturer rebate", "discount"),
        ("Mystery charge", "other"),
    ],
)
def test_classify(label, category):
    assert classify(label) == category


def test_nineteen_states_have_rules_and_others_have_none():
    assert len(DOC_FEE_RULES) == 19
    assert sum(1 for r in DOC_FEE_RULES.values() if r.kind == "cap") == 17
    assert {code for code, r in DOC_FEE_RULES.items() if r.kind == "presumed"} == {"TX", "SC"}
    assert doc_fee_rule("FL").kind == "none"
    assert doc_fee_rule("Florida").limit_for(30_000) is None


def test_percentage_caps_use_the_lesser_amount():
    assert doc_fee_rule("MI").limit_for(30_000) == 280
    assert doc_fee_rule("MI").limit_for(4_000) == 200
    assert doc_fee_rule("MN").limit_for(2_000) == 200
    assert doc_fee_rule("OH").limit_for(50_000) == 398


def test_doc_fee_over_cap_is_flagged_with_the_excess_only():
    audit = build_audit(_quote("NY", [LineItem("Doc fee", 300.0)]))
    line = audit.lines[0]
    assert line.verdict == V_OVER
    assert line.removable == 125.0
    assert "limit we found" in line.headline
    assert "illegal" not in (line.headline + line.detail).lower()


def test_doc_fee_at_cap_is_fine_and_multiple_doc_lines_add_up():
    at_cap = build_audit(_quote("NY", [LineItem("Doc fee", 175.0)]))
    assert at_cap.lines[0].verdict == V_EXPECTED
    split = build_audit(_quote("NY", [LineItem("Doc fee", 150.0), LineItem("Processing fee", 100.0)]))
    assert [l.verdict for l in split.lines] == [V_EXPECTED, V_OVER]
    assert split.lines[1].removable == 75.0
    assert split.doc_fee_total == 250.0


def test_presumed_states_ask_instead_of_claiming_over_limit():
    audit = build_audit(_quote("TX", [LineItem("Doc fee", 399.0)]))
    assert audit.lines[0].verdict == V_HIGH
    assert audit.lines[0].removable == 0.0


def test_no_cap_state_is_verify_only():
    audit = build_audit(_quote("FL", [LineItem("Doc fee", 999.0)]))
    assert audit.lines[0].verdict == V_VERIFY
    assert audit.removable_total == 0.0


def test_government_fees_are_never_called_optional():
    audit = build_audit(_quote("TX", [LineItem("Sales tax", 1875.0), LineItem("Registration", 90.0)]))
    assert all(line.verdict == V_VERIFY and line.category == CAT_GOV for line in audit.lines)
    assert audit.removable_total == 0.0
    assert audit.implied_tax_rate == 6.25


def test_destination_on_used_car_is_questioned():
    new = build_audit(_quote("TX", [LineItem("Destination", 1395.0)]))
    used = build_audit(_quote("TX", [LineItem("Destination", 1395.0)], condition="used"))
    assert new.lines[0].verdict == V_VERIFY
    assert used.lines[0].verdict == V_ASK


def test_addons_and_fi_products_are_optional_and_summed():
    audit = build_audit(
        _quote("TX", [LineItem("VIN etching", 299.0), LineItem("GAP", 895.0), LineItem("Market adjustment", 2000.0)])
    )
    assert {line.verdict for line in audit.lines} == {V_OPTIONAL}
    assert audit.removable_total == 3194.0
    assert audit.flagged_count == 3


def test_california_cars_act_notes():
    audit = build_audit(_quote("CA", [LineItem("Nitrogen tires", 199.0), LineItem("Oil change package", 300.0)]))
    nitrogen = audit.lines[0]
    assert "1784.42" in nitrogen.detail and "1784.41" in nitrogen.detail
    assert "no-benefit" in nitrogen.headline
    gas_car = audit.lines[1]
    assert "Oil changes" not in gas_car.detail
    ev = build_audit(_quote("CA", [LineItem("Oil change package", 300.0)], is_ev=True))
    assert "electric vehicle" in ev.lines[0].detail


def test_user_category_override_wins():
    audit = build_audit(_quote("NY", [LineItem("Mystery charge", 300.0, category=CAT_DOC)]))
    assert audit.lines[0].category == CAT_DOC
    assert audit.lines[0].verdict == V_OVER


def test_totals_and_payment_math():
    quote = make_sample_quote()
    audit = build_audit(quote)
    assert audit.ok
    assert audit.out_the_door == round(31_500 + sum(i.amount for i in quote.items), 2)
    assert audit.amount_financed == round(audit.out_the_door - 3_000, 2)
    assert audit.monthly_payment == amortized_payment(audit.amount_financed, 7.9, 72)
    assert audit.monthly_without_removable < audit.monthly_payment
    assert audit.finance_cost_of_removable > audit.removable_total  # interest makes add-ons cost more


def test_amortization_edges():
    assert amortized_payment(12_000, 0, 12) == 1000.0
    assert amortized_payment(0, 5, 60) == 0.0
    assert amortized_payment(30_000, 6, 60) == pytest.approx(579.98, abs=0.01)
    with pytest.raises(ValueError):
        amortized_payment(1000, 5, 0)


def test_validation():
    bad = build_audit(QuoteInput(state="", condition="new", vehicle_price=0))
    assert not bad.ok and len(bad.errors) == 2
    assert not build_audit(_quote(apr=55, term_months=60)).ok
    assert not build_audit(_quote(apr=5, term_months=120)).ok


def test_discount_reduces_total():
    audit = build_audit(_quote("TX", [LineItem("Manufacturer rebate", -1000.0)]))
    assert audit.out_the_door == 29_000.0
    assert audit.lines[0].verdict == V_EXPECTED


def test_counter_offer_lists_flagged_items_and_never_threatens():
    quote = make_sample_quote()
    audit = build_audit(quote)
    text = counter_offer_text(quote, audit)
    for line in flagged_lines(audit):
        assert line.label.lower() in text.lower()
    lowered = text.lower()
    for word in ("illegal", "lawsuit", "sue", "attorney general", "fraud"):
        assert word not in lowered
    clean = build_audit(_quote("TX", [LineItem("Sales tax", 100.0)]))
    assert "full out-the-door price" in counter_offer_text(_quote("TX"), clean)


def test_round_trip():
    quote = make_sample_quote("CA")
    assert quote_from_dict(quote_to_dict(quote)) == quote
