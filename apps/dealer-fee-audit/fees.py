"""State doc-fee limits and line-item categories for Dealer Fee Check.

Every dollar limit here was read from a state statute, rule, or agency notice
(see `source`) and is dated RULES_DATE. Limits change, often every January.
The app says "above the limit we found", never "illegal".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

RULES_DATE = "November 27, 2026"

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

# Categories, in the order they are shown.
CAT_PRICE = "vehicle_price"
CAT_GOV = "government"
CAT_DOC = "doc_fee"
CAT_DEST = "destination"
CAT_MARKUP = "market_adjustment"
CAT_ADDON = "dealer_addon"
CAT_FI = "fi_product"
CAT_DISCOUNT = "discount"
CAT_OTHER = "other"

CATEGORY_LABELS = {
    CAT_GOV: "Taxes and government fees",
    CAT_DOC: "Dealer documentation fee",
    CAT_DEST: "Destination / freight",
    CAT_MARKUP: "Market adjustment / markup",
    CAT_ADDON: "Dealer add-ons",
    CAT_FI: "Finance-office products",
    CAT_DISCOUNT: "Discounts and rebates",
    CAT_OTHER: "Other / unclear",
}

# Picker options shown next to each line. "Auto" uses the keyword match.
CATEGORY_PICKER = ("Auto-detect",) + tuple(CATEGORY_LABELS[key] for key in CATEGORY_LABELS)
PICKER_TO_CAT = {label: key for key, label in CATEGORY_LABELS.items()}


@dataclass(frozen=True)
class DocFeeRule:
    state: str
    kind: str  # "cap", "presumed", or "none"
    cap: float | None = None
    pct_cap: float | None = None  # fraction of the vehicle price, for "lesser of" rules
    note: str = ""
    citation: str = ""
    source: str = ""

    def limit_for(self, vehicle_price: float) -> float | None:
        if self.kind == "none" or self.cap is None:
            return None
        limit = float(self.cap)
        if self.pct_cap is not None and vehicle_price > 0:
            limit = min(limit, round(vehicle_price * self.pct_cap, 2))
        return limit


_RULES = (
    DocFeeRule("AR", "cap", 129, None, "Must be the same for every retail customer.",
               "Ark. Code § 23-112-317; Arkansas Motor Vehicle Commission Rule 8", "https://www.amvc.arkansas.gov/"),
    DocFeeRule("CA", "cap", 85, None,
               "$85 if the dealer is a DMV private industry partner, $70 if not. It may not be presented as a government fee.",
               "Cal. Vehicle Code § 4456.5", "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?sectionNum=4456.5.&lawCode=VEH"),
    DocFeeRule("IL", "cap", 377.63, None, "Adjusted each year for inflation. The 2026 figure is the one published for dealers.",
               "815 ILCS 375/11.1", "https://www.ilga.gov/legislation/ilcs/fulltext.asp?DocName=081503750K11.1"),
    DocFeeRule("IN", "cap", 261.72, None,
               "The Secretary of State will not take enforcement action at or below this amount (as of July 1, 2026).",
               "Ind. Code § 9-32-13-7(b); Auto Dealer Services memo, July 1, 2026", "https://www.in.gov/sos/dealer/files/Doc-Fees-in-2026.pdf"),
    DocFeeRule("IA", "cap", 180, None, "Must be included in advertised prices.",
               "Iowa Code § 322.19A", "https://www.legis.iowa.gov/docs/code/2026/322.19A.pdf"),
    DocFeeRule("LA", "cap", 436, None, "Adjusted each calendar year.",
               "La. R.S. 6:969.18; Louisiana Motor Vehicle Commission Bulletin B-2026-001", "https://lmvc.la.gov/"),
    DocFeeRule("MD", "cap", 800, None, "Must be shown on the contract as not required by law.",
               "Md. Code, Transportation § 15-311.1", "https://mgaleg.maryland.gov/"),
    DocFeeRule("MI", "cap", 280, 0.05, "The lesser of $280 or 5% of the cash price.",
               "MCL 492.113(2)(a); DIFS Bulletin 2025-03-CF", "https://www.michigan.gov/difs"),
    DocFeeRule("MN", "cap", 350, 0.10, "The lesser of $350 or 10% of the sale value.",
               "Minn. Stat. § 168.27, subd. 31", "https://www.revisor.mn.gov/statutes/cite/168.27"),
    DocFeeRule("MS", "cap", 425, None, "",
               "Mississippi Motor Vehicle Commission Regulation 8", "https://www.mmvc.ms.gov/sites/mmvc/files/rules/Regulation8.pdf"),
    DocFeeRule("MO", "cap", 620.79, None, "Maximum administrative fee for licensure year 2026 (effective Feb. 1, 2026).",
               "RSMo § 301.558; 12 CSR 10-26.231", "https://dor.mo.gov/motor-vehicle/dealers-lienholders/"),
    DocFeeRule("NY", "cap", 175, None,
               "Optional dealer fee for title/registration processing. It is not a DMV fee; $5 more is allowed for special plates.",
               "15 NYCRR § 78.19", "https://www.law.cornell.edu/regulations/new-york/15-NYCRR-78.19"),
    DocFeeRule("OH", "cap", 398, 0.10, "The lesser of $398 (2026) or 10% of the price.",
               "Ohio Rev. Code § 4517.261", "https://autodealers.ohio.gov/resources-for-dealers/resources/documentary-service-charge"),
    DocFeeRule("OR", "cap", 250, None, "$250 if the dealer registers electronically, $200 if not.",
               "ORS 822.043", "https://oregon.public.law/statutes/ors_822.043"),
    DocFeeRule("PA", "cap", 490, None, "$490 if the dealer registers online, $409 if titlework is done manually (2026).",
               "63 P.S. § 818.327(c); State Board of Vehicle Manufacturers, Dealers and Salespersons notice, Jan. 13, 2026",
               "https://www.pa.gov/content/dam/copapwp-pagov/en/dos/department-and-offices/bpoa/vehicle/Annual%20Fee.pdf"),
    DocFeeRule("RI", "cap", 400, None, "",
               "R.I. Gen. Laws § 31-5-1 et seq. (dealer documentary fee)", "https://dmv.ri.gov/"),
    DocFeeRule("WA", "cap", 200, None, "",
               "RCW 46.12.042", "https://app.leg.wa.gov/rcw/default.aspx?cite=46.12.042"),
    DocFeeRule("TX", "presumed", 225, None,
               "$225 is presumed reasonable. A dealer charging more must have filed its costs with the state.",
               "Texas Finance Code § 348.006; Texas OCCC rule", "https://occc.texas.gov/"),
    DocFeeRule("SC", "presumed", 225, None,
               "$225 is presumed reasonable. A dealer charging more must have filed with the state.",
               "S.C. Code § 37-2-307", "https://consumer.sc.gov/"),
)

DOC_FEE_RULES = {rule.state: rule for rule in _RULES}


def doc_fee_rule(state: str | None) -> DocFeeRule:
    code = normalize_state(state)
    if code in DOC_FEE_RULES:
        return DOC_FEE_RULES[code]
    return DocFeeRule(code or "", "none", None, None,
                      "We found no state dollar limit. The dealer sets this fee, so treat it as part of the price you negotiate.")


def normalize_state(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    upper = text.upper()
    if upper in STATE_NAMES:
        return upper
    for name, code in STATE_CHOICES:
        if name.lower() == text.lower():
            return code
    return None


def residence_gate(state: str | None) -> str:
    """'ok' or 'missing'. No state is blocked for this product (see legal.md)."""
    return "ok" if normalize_state(state) else "missing"


# Keyword rules, checked in order. First match wins.
_PATTERNS: tuple[tuple[str, str], ...] = (
    (CAT_DISCOUNT, r"\b(rebate|discount|incentive|cash back|bonus cash|loyalty|conquest|savings)\b"),
    (CAT_DOC, r"\b(doc(ument(ary|ation)?)?|admin(istrative)?|processing|dealer service|conveyance|handling)\s*(fee|charge|prep)?\b"),
    (CAT_GOV, r"\b(sales tax|tax|title|registration|regist|license|licen[cs]e plate|plates?|tag|dmv|smog|tire fee|state fee|county fee|inspection fee|e-?filing|electronic filing|lien)\b"),
    (CAT_DEST, r"\b(destination|freight|delivery charge|dest\.?)\b"),
    (CAT_MARKUP, r"\b(market (value )?adjust\w*|adm|additional dealer markup|markup|dealer premium|addendum|second sticker)\b"),
    (CAT_FI, r"\b(gap|service contract|extended warranty|warranty|vsc|maintenance plan|prepaid maintenance|oil change\w*|tire (and|&) wheel|key replacement|dent|windshield|credit life|disability|theft protection plan|lease protection|appearance protection plan)\b"),
    (CAT_ADDON, r"\b(nitrogen|vin etch\w*|etch\w*|paint protection|fabric|interior protection|ceramic|sealant|undercoat|rust ?proof|tint\w*|pinstripe|wheel locks?|door edge|mud ?flaps|splash guards|floor mats|theft deterr\w*|lojack|gps|tracking|protection package|appearance package|dealer prep|prep fee|reconditioning|recon|accessor\w*|cargo|tow|hitch|clear bra|ppf|film)\b"),
)


def classify(label: str) -> str:
    text = (label or "").lower()
    for category, pattern in _PATTERNS:
        if re.search(pattern, text):
            return category
    return CAT_OTHER


# California CARS Act items a dealer may not charge for (Cal. Civ. Code § 1784.42(a)).
CA_NO_BENEFIT_PATTERNS = (
    (r"nitrogen", "Nitrogen tire products under 95% purity"),
    (r"oil change", "Oil changes on an electric vehicle"),
    (r"catalytic|cat(alytic)? converter", "Catalytic converter markings on a car without one"),
)
