"""Personalized action plan from audit numbers.

The written plan is either the model's answer to a fixed prompt (temperature 0)
or, when that call is unavailable, the same three sections filled in from the
audit math. Neither version promises a return.
"""

from __future__ import annotations

import hashlib
import json

EDUCATIONAL_NOTE = "Educational, not financial advice."
SAVINGS_GROWTH_RATE = 0.07
MODEL_NAME = "gpt-4.1-mini"


def money(amount: float) -> str:
    return f"${amount:,.0f}"


def illustrated_extra_annual_savings(gap: float, years: int, annual_rate: float = SAVINGS_GROWTH_RATE) -> float | None:
    """Level annual savings that would close `gap` in `years` at a stated rate.

    This is an illustration, not a forecast. The rate is an assumption the
    caller has to disclose next to the dollar figure.
    """
    if gap <= 0 or years <= 0:
        return None
    if annual_rate == 0:
        return gap / years
    return gap * annual_rate / ((1 + annual_rate) ** years - 1)


def four_percent_gap(total_invest: float, annual_withdrawal: float) -> float:
    """How much more balance a 4% illustration would need to cover this withdrawal."""
    if annual_withdrawal <= 0:
        return 0.0
    needed = annual_withdrawal / 0.04
    return max(needed - float(total_invest or 0), 0.0)


def plan_fingerprint(inputs: dict) -> str:
    payload = {key: inputs.get(key) for key in sorted(inputs)}
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def action_plan_prompt(inputs: dict) -> tuple[str, str]:
    """Fixed instructions plus the audit numbers. Call with temperature 0."""
    instructions = """
You write a short retirement action plan from calculator results inside Retirement Audit.
Rules:
- Use only the numbers in the user message. Do not invent balances, ages, or benefits.
- Use these exact headings, in this order, each on its own line:
  What to change first
  How much to save
  Social Security claiming note
- No guarantees of investment returns, Social Security payments, or how long money will last.
- Do not present yourself as a licensed financial advisor.
- Do not give tax, legal, or regulated investment advice.
- If the withdrawal rate is above 4%, say that rate is aggressive for a long retirement.
- Keep each section to 2-4 sentences.
- End with this exact sentence: Educational, not financial advice.
""".strip()
    user_message = f"""
Planning for: {inputs.get("planning_for")}
Current age: {inputs.get("current_age")}
Retirement age: {inputs.get("retirement_age")}
Years until retirement in this audit: {inputs.get("years_to_retirement")}
Projected investments at retirement: {money(float(inputs.get("total_invest") or 0))}
Annual contributions already entered: {money(float(inputs.get("annual_contributions") or 0))}
Average annual earnings entered: {money(float(inputs.get("earnings") or 0))}
Withdrawal rate: {float(inputs.get("withdrawal_rate_pct") or 0):.1f}%
Expected portfolio growth in retirement: {float(inputs.get("growth_pct") or 0):.1f}%
First-year withdrawal: {money(float(inputs.get("annual_withdrawal") or 0))}
Portfolio depletion illustration: {inputs.get("depletion_label")}
Retirement score: {inputs.get("score")}/100 ({inputs.get("score_label")})
Annual Social Security estimate: {money(float(inputs.get("ss_annual") or 0))}
Social Security claim age used for the primary person: {inputs.get("ss_claim_age")}
Manual Social Security amounts: {bool(inputs.get("manual_ss"))}
Annual pension: {money(float(inputs.get("pension_annual") or 0))}
""".strip()
    return instructions, user_message


def deterministic_action_plan(inputs: dict) -> str:
    """The same three sections, filled from the audit math with no model call."""
    total = float(inputs.get("total_invest") or 0)
    withdrawal = float(inputs.get("annual_withdrawal") or 0)
    rate = float(inputs.get("withdrawal_rate_pct") or 0)
    years = int(inputs.get("years_to_retirement") or 0)
    contributions = float(inputs.get("annual_contributions") or 0)
    earnings = float(inputs.get("earnings") or 0)
    gap = four_percent_gap(total, withdrawal)
    extra = illustrated_extra_annual_savings(gap, years)
    claim_age = int(inputs.get("ss_claim_age") or 67)
    ss_annual = float(inputs.get("ss_annual") or 0)

    if total <= 0:
        first = (
            f"What to change first: this audit does not have an investment balance yet, "
            f"so the first change is to start one. The retirement score is {inputs.get('score')}/100 "
            f"({inputs.get('score_label')}) and there is no withdrawal to test. "
            f"A balance has to exist before a withdrawal rate means anything in this illustration."
        )
    elif rate > 5:
        first = (
            f"What to change first: the {rate:.1f}% withdrawal is the first change. "
            f"At retirement age {inputs.get('retirement_age')} the audit projects {money(total)} of investments "
            f"and a first-year withdrawal of {money(withdrawal)}. The illustration runs out {inputs.get('depletion_label')}. "
            f"The retirement score is {inputs.get('score')}/100 ({inputs.get('score_label')}). "
            f"A withdrawal above 5% is aggressive for a long retirement in this illustration."
        )
    elif rate > 4:
        first = (
            f"What to change first: the {rate:.1f}% withdrawal is above a 4% illustration, so that rate is the first change "
            f"unless the balance gets larger. Projected investments at age {inputs.get('retirement_age')} are {money(total)}, "
            f"and the first-year withdrawal is {money(withdrawal)}. The illustration runs out {inputs.get('depletion_label')}. "
            f"The retirement score is {inputs.get('score')}/100 ({inputs.get('score_label')})."
        )
    else:
        first = (
            f"What to change first: keep the contributions you already entered and do not raise the {rate:.1f}% withdrawal. "
            f"Projected investments at age {inputs.get('retirement_age')} are {money(total)}, "
            f"with a first-year withdrawal of {money(withdrawal)}. The illustration runs out {inputs.get('depletion_label')}. "
            f"The retirement score is {inputs.get('score')}/100 ({inputs.get('score_label')})."
        )

    if total <= 0 and earnings <= 0:
        savings = (
            "How much to save: this audit has no investment balance and no earnings, so it cannot name a dollar amount yet. "
            "Enter a balance, a contribution, or average earnings, then come back to this plan."
        )
    elif total <= 0:
        low = earnings * 0.10
        high = earnings * 0.15
        savings = (
            f"How much to save: a common educational benchmark is 10% to 15% of pay, including any employer match. "
            f"On the {money(earnings)} of average earnings in this audit, that range is {money(low)} to {money(high)} per year. "
            f"It is an illustration, not a required amount, and it does not guarantee what the account will be worth later."
        )
    elif gap <= 0:
        savings = (
            f"How much to save: a 4% illustration of the projected {money(total)} balance covers the "
            f"{money(withdrawal)} first-year withdrawal you selected. Contributions already entered are {money(contributions)} per year. "
            f"Keeping that contribution going until retirement is the savings side of this plan. "
            f"This does not guarantee the balance or a {SAVINGS_GROWTH_RATE:.0%} return."
        )
    elif extra is None:
        covered = total * 0.04
        savings = (
            f"How much to save: there are no years left before the retirement age in this audit, so extra yearly savings "
            f"before that age cannot close the gap here. A 4% illustration of the projected balance is {money(covered)} "
            f"in the first year, compared with the {money(withdrawal)} withdrawal you selected "
            f"(about {money(gap)} more balance would cover that withdrawal at 4%). "
            f"This does not guarantee a return."
        )
    else:
        needed = withdrawal / 0.04
        savings = (
            f"How much to save: to support the same {money(withdrawal)} first-year withdrawal at a 4% illustration, "
            f"the projected balance would need to be about {money(needed)}, which is {money(gap)} more than the "
            f"{money(total)} this audit projects. Saving about {money(extra)} more per year for {years} years, "
            f"illustrated at {SAVINGS_GROWTH_RATE:.0%} growth, is one paper way to close that gap. "
            f"Contributions already entered are {money(contributions)} per year and are separate from that extra amount. "
            f"The {SAVINGS_GROWTH_RATE:.0%} figure is an assumption, not a forecast, and it does not guarantee that return."
        )

    if ss_annual <= 0:
        social = (
            "Social Security claiming note: no Social Security amount came out of the numbers in this audit. "
            "Add average earnings, or a manual benefit, and check the official estimate at ssa.gov. "
            "This note does not guarantee a benefit."
        )
    else:
        who = "combined" if inputs.get("planning_for") == "Me + spouse" else "estimated"
        timing = (
            f"The claim age entered for you is {claim_age}. "
            "Claiming before 67 generally lowers the monthly benefit, and delaying toward 70 generally raises it. "
            "That is an educational description of the program rules, not a recommendation for your household."
            if inputs.get("manual_ss") and claim_age != 67
            else
            "This estimate uses age 67, the full retirement age in the simplified formula. "
            "Claiming anywhere from 62 to 70 changes the monthly amount. This is not a recommendation."
        )
        social = (
            f"Social Security claiming note: the simplified {who} benefit in this audit is {money(ss_annual)} per year. "
            f"{timing} Confirm the figure in your own account at ssa.gov. This note does not guarantee a benefit."
        )

    closing = (
        "This illustration does not guarantee investment returns, Social Security payments, or how long money will last. "
        f"{EDUCATIONAL_NOTE}"
    )
    return "\n\n".join([first, savings, social, closing])


def _with_required_note(text: str) -> str:
    cleaned = (text or "").strip()
    if EDUCATIONAL_NOTE not in cleaned:
        cleaned = cleaned.rstrip() + "\n\n" + EDUCATIONAL_NOTE
    if "guarantee" not in cleaned.lower():
        cleaned += " This does not guarantee investment returns."
    return cleaned


def generate_action_plan(inputs: dict, client=None) -> tuple[str, str]:
    """Return (plan text, source) where source is "openai" or "calculator".

    The model call uses a fixed prompt and temperature 0. Any failure, missing
    client, or empty answer falls back to the calculator plan.
    """
    fallback = deterministic_action_plan(inputs)
    if client is None:
        return fallback, "calculator"
    instructions, user_message = action_plan_prompt(inputs)
    try:
        response = client.responses.create(
            model=MODEL_NAME,
            temperature=0,
            instructions=instructions,
            input=user_message,
        )
        text = _with_required_note(getattr(response, "output_text", "") or "")
    except Exception:
        return fallback, "calculator"
    if not text.strip():
        return fallback, "calculator"
    return text, "openai"
