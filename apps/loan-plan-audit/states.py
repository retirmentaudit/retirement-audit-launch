"""State of residence helpers. Poverty region and the paid-report gate."""

from __future__ import annotations

# Full name, postal code. Alphabetical by name. DC included.
STATE_CHOICES: tuple[tuple[str, str], ...] = (
    ("Alabama", "AL"),
    ("Alaska", "AK"),
    ("Arizona", "AZ"),
    ("Arkansas", "AR"),
    ("California", "CA"),
    ("Colorado", "CO"),
    ("Connecticut", "CT"),
    ("Delaware", "DE"),
    ("District of Columbia", "DC"),
    ("Florida", "FL"),
    ("Georgia", "GA"),
    ("Hawaii", "HI"),
    ("Idaho", "ID"),
    ("Illinois", "IL"),
    ("Indiana", "IN"),
    ("Iowa", "IA"),
    ("Kansas", "KS"),
    ("Kentucky", "KY"),
    ("Louisiana", "LA"),
    ("Maine", "ME"),
    ("Maryland", "MD"),
    ("Massachusetts", "MA"),
    ("Michigan", "MI"),
    ("Minnesota", "MN"),
    ("Mississippi", "MS"),
    ("Missouri", "MO"),
    ("Montana", "MT"),
    ("Nebraska", "NE"),
    ("Nevada", "NV"),
    ("New Hampshire", "NH"),
    ("New Jersey", "NJ"),
    ("New Mexico", "NM"),
    ("New York", "NY"),
    ("North Carolina", "NC"),
    ("North Dakota", "ND"),
    ("Ohio", "OH"),
    ("Oklahoma", "OK"),
    ("Oregon", "OR"),
    ("Pennsylvania", "PA"),
    ("Rhode Island", "RI"),
    ("South Carolina", "SC"),
    ("South Dakota", "SD"),
    ("Tennessee", "TN"),
    ("Texas", "TX"),
    ("Utah", "UT"),
    ("Vermont", "VT"),
    ("Virginia", "VA"),
    ("Washington", "WA"),
    ("West Virginia", "WV"),
    ("Wisconsin", "WI"),
    ("Wyoming", "WY"),
)

STATE_NAMES = {code: name for name, code in STATE_CHOICES}
_LOOKUP = {code.lower(): code for code in STATE_NAMES}
_LOOKUP.update({name.lower(): code for name, code in STATE_CHOICES})

# Paid software report stays off until counsel clears these states.
BLOCKED_PAID_REPORT = frozenset({"CA", "IL"})


def normalize_state(value: str | None) -> str | None:
    """Return a postal code, or None when the value is empty or unknown."""
    if value is None:
        return None
    key = str(value).strip().lower()
    if not key:
        return None
    return _LOOKUP.get(key)


def poverty_region(state: str | None) -> str:
    """HHS table key: AK, HI, or contiguous (48 states and DC)."""
    code = normalize_state(state)
    if code == "AK":
        return "AK"
    if code == "HI":
        return "HI"
    return "contiguous"


def residence_gate(state: str | None) -> str:
    """missing, blocked, or ok. Blocked states still get the free comparison."""
    code = normalize_state(state)
    if code is None:
        return "missing"
    if code in BLOCKED_PAID_REPORT:
        return "blocked"
    return "ok"


def paid_report_available(state: str | None) -> bool:
    return residence_gate(state) == "ok"


def blocked_state_note(state: str | None) -> str:
    code = normalize_state(state)
    name = STATE_NAMES.get(code or "", "your state")
    return (
        f"The full report isn't available in {name} yet. "
        "You can still use the free comparison on this page. "
        "Free tools are at StudentAid.gov."
    )
