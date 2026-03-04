"""Parse Vancouver rental listing descriptions for structured fields.

V2 — Comprehensive extraction covering:
- Neighbourhood normalization (Vancouver + surrounding municipalities)
- Occupancy preferences (gender, couples, smoking, age, vibe)
- Lease terms, availability, price ranges
- Property classification (building, domicile, room type, shared living)
- Furnished details (bedroom vs common areas)
- Bathroom & laundry
- Transit proximity
- Amenities (dishwasher, balcony, fireplace, A/C, gym, EV, storage, views)
- Existing boolean fields (utilities, parking, pets)
- Bedroom/bathroom count extraction from text
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional


# ── Vancouver neighbourhood normalization ────────────────────────
#
# Maps regex patterns to canonical neighbourhood names.
# Specific matches (e.g., "Metrotown") come before general ones
# ("Burnaby") so the first match wins.

NEIGHBOURHOOD_PATTERNS: list[tuple[re.Pattern, str]] = [
    # ── Vancouver: Downtown & surrounds ──
    (re.compile(r'\bcoal\s+harbour\b', re.I), "Coal Harbour"),
    (re.compile(r'\bgastown\b', re.I), "Gastown"),
    (re.compile(r'\byaletown\b', re.I), "Yaletown"),
    (re.compile(r'\bcrosstown\b', re.I), "Crosstown"),
    (re.compile(r'\bchinatown\b', re.I), "Strathcona"),
    (re.compile(r'\b(?:west\s+end|english\s+bay|davie\s+village|denman\s+(?:st|street))\b', re.I), "West End"),
    (re.compile(r'\b(?:downtown|dt\s+van(?:couver)?)\b', re.I), "Downtown"),

    # ── Vancouver: West Side ──
    (re.compile(r'\b(?:west\s+point\s+grey|wpg|jericho)\b', re.I), "West Point Grey"),
    (re.compile(r'\bubc\b|university\s+endowment|wesbrook\b|uel\b', re.I), "UBC"),
    (re.compile(r'\b(?:kitsilano|kits)\b', re.I), "Kitsilano"),
    (re.compile(r'\b(?:arbutus[\s-]?ridge|arbutus)\b', re.I), "Arbutus Ridge"),
    (re.compile(r'\b(?:kerrisdale)\b', re.I), "Kerrisdale"),
    (re.compile(r'\b(?:dunbar[\s-]?southlands|dunbar|southlands)\b', re.I), "Dunbar-Southlands"),
    (re.compile(r'\b(?:shaughnessy)\b', re.I), "Shaughnessy"),
    (re.compile(r'\b(?:south\s+granville)\b', re.I), "South Granville"),
    (re.compile(r'\bfairview\b', re.I), "Fairview"),
    (re.compile(r'\b(?:south\s+cambie|cambie\s+village|cambie\s+corridor)\b', re.I), "South Cambie"),
    (re.compile(r'\b(?:oakridge)\b', re.I), "Oakridge"),
    (re.compile(r'\b(?:langara)\b', re.I), "Langara"),
    (re.compile(r'\b(?:marpole)\b', re.I), "Marpole"),

    # ── Vancouver: Central ──
    (re.compile(r'\b(?:mount\s+pleasant|mt\.?\s+pleasant)\b', re.I), "Mount Pleasant"),
    (re.compile(r'\b(?:riley[\s-]?park|little\s+mountain|queen\s+elizabeth)\b', re.I), "Riley Park"),
    (re.compile(r'\bstrathcona\b', re.I), "Strathcona"),

    # ── Vancouver: East Side ──
    (re.compile(r'\b(?:grandview[\s-]?woodland|commercial\s+dr(?:ive)?|the\s+drive)\b', re.I), "Grandview-Woodland"),
    (re.compile(r'\b(?:hastings[\s-]?sunrise|east\s+hastings)\b', re.I), "Hastings-Sunrise"),
    (re.compile(r'\b(?:joyce[\s-]?collingwood)\b', re.I), "Renfrew-Collingwood"),
    (re.compile(r'\b(?:renfrew[\s-]?collingwood|renfrew\s+heights)\b', re.I), "Renfrew-Collingwood"),
    (re.compile(r'\b(?:collingwood)\b', re.I), "Renfrew-Collingwood"),
    (re.compile(r'\b(?:renfrew)\b', re.I), "Renfrew-Collingwood"),
    (re.compile(r'\b(?:kensington[\s-]?cedar\s+cottage|cedar\s+cottage)\b', re.I), "Kensington-Cedar Cottage"),
    (re.compile(r'\b(?:kensington)\b', re.I), "Kensington-Cedar Cottage"),

    # ── Vancouver: South ──
    (re.compile(r'\b(?:sunset)\b', re.I), "Sunset"),
    (re.compile(r'\b(?:punjabi\s+market)\b', re.I), "Sunset"),
    (re.compile(r'\b(?:victoria[\s-]?fraserview|fraserview)\b', re.I), "Victoria-Fraserview"),
    (re.compile(r'\b(?:killarney)\b', re.I), "Killarney"),
    (re.compile(r'\b(?:champlain\s+heights|champlain)\b', re.I), "Killarney"),
    (re.compile(r'\b(?:river\s+district|south\s+marine)\b', re.I), "River District"),
    (re.compile(r'\b(?:south\s+van(?:couver)?)\b', re.I), "South Vancouver"),
    (re.compile(r'\b(?:east\s+van(?:couver)?|east\s+side)\b', re.I), "East Vancouver"),

    # ── Burnaby (specific first, then general) ──
    (re.compile(r'\bmetrotown\b', re.I), "Burnaby — Metrotown"),
    (re.compile(r'\b(?:brentwood)\b', re.I), "Burnaby — Brentwood"),
    (re.compile(r'\b(?:edmonds|highgate)\b', re.I), "Burnaby — Edmonds"),
    (re.compile(r'\b(?:lougheed)\b', re.I), "Burnaby — Lougheed"),
    (re.compile(r'\bburquitlam\b', re.I), "Burnaby — Lougheed"),
    (re.compile(r'\b(?:sfu|simon\s+fraser|univercity|burnaby\s+mountain)\b', re.I), "Burnaby — SFU"),
    (re.compile(r'\bburnaby\b', re.I), "Burnaby"),

    # ── Other municipalities ──
    (re.compile(r'\b(?:sapperton|queensborough)\b', re.I), "New Westminster"),
    (re.compile(r'\b(?:new\s+west(?:minster)?)\b', re.I), "New Westminster"),
    (re.compile(r'\b(?:lonsdale|lynn\s+valley|deep\s+cove|lower\s+lonsdale)\b', re.I), "North Vancouver"),
    (re.compile(r'\b(?:north\s+van(?:couver)?)\b', re.I), "North Vancouver"),
    (re.compile(r'\b(?:ambleside|park\s+royal)\b', re.I), "West Vancouver"),
    (re.compile(r'\b(?:west\s+van(?:couver)?)\b', re.I), "West Vancouver"),
    (re.compile(r'\b(?:steveston|brighouse|richmond\s+centre)\b', re.I), "Richmond"),
    (re.compile(r'\brichmond\b', re.I), "Richmond"),
    (re.compile(r'\b(?:coquitlam\s+centre|burke\s+mountain)\b', re.I), "Coquitlam"),
    (re.compile(r'\bcoquitlam\b', re.I), "Coquitlam"),
    (re.compile(r'\b(?:inlet\s+centre|moody\s+centre)\b', re.I), "Port Moody"),
    (re.compile(r'\bport\s+moody\b', re.I), "Port Moody"),
    (re.compile(r'\b(?:port\s+coquitlam|poco)\b', re.I), "Port Coquitlam"),
    (re.compile(r'\btri[\s-]?cit(?:y|ies)\b', re.I), "Tri-Cities"),
    (re.compile(r'\b(?:surrey\s+central|whalley|king\s+george|guildford|fleetwood|newton)\b', re.I), "Surrey"),
    (re.compile(r'\bsurrey\b', re.I), "Surrey"),
    (re.compile(r'\b(?:langley\s+city|walnut\s+grove|willoughby)\b', re.I), "Langley"),
    (re.compile(r'\blangley\b', re.I), "Langley"),
    (re.compile(r'\bwhite\s+rock\b', re.I), "White Rock"),
    (re.compile(r'\bmaple\s+ridge\b', re.I), "Maple Ridge"),
    (re.compile(r'\bpitt\s+meadows\b', re.I), "Pitt Meadows"),
    (re.compile(r'\b(?:ladner|tsawwassen)\b', re.I), "Delta"),
    (re.compile(r'\bdelta\b', re.I), "Delta"),

    # ── Intersection / landmark-based (less specific, last) ──
    (re.compile(r'\bbroadway\s*(?:&|and)\s*cambie\b', re.I), "Fairview"),
    (re.compile(r'\bbroadway\s*(?:&|and)\s*(?:commercial|victoria|clark)\b', re.I), "Mount Pleasant"),
    (re.compile(r'\bmain\s*(?:&|and)\s*(?:broadway|king\s+edward)\b', re.I), "Mount Pleasant"),
    (re.compile(r'\bcommercial\s*(?:&|and)\s*broadway\b', re.I), "Grandview-Woodland"),
    (re.compile(r'\bbroadway\s*(?:&|and)\s*(?:yew|macdonald|alma)\b', re.I), "Kitsilano"),
    (re.compile(r'\b(?:41st|49th)\s*(?:&|and)\s*(?:cambie|oak|main)\b', re.I), "Oakridge"),
    (re.compile(r'\b(?:victoria\s+dr(?:ive)?)\b', re.I), "Victoria-Fraserview"),
    (re.compile(r'\b(?:main\s+st(?:reet)?)\b', re.I), "Mount Pleasant"),
    (re.compile(r'\bcambie\b', re.I), "South Cambie"),
]


class DescriptionParser:
    """Parse rental listing descriptions for structured fields.

    All methods are static — no instance state needed.
    Call parse_all() for a complete extraction pass.
    """

    @staticmethod
    def parse_all(description: str, title: str = "", location: str = "") -> dict:
        """Extract all structured fields from listing text.

        Returns dict with keys matching Listing model field names.
        Values are None when no signal detected.
        """
        text = f"{title} {description}".strip()
        loc_text = f"{location} {title} {description}"

        return {
            # Occupancy preferences
            "gender_preference": DescriptionParser.extract_gender_preference(text),
            "couples_allowed": DescriptionParser.extract_couples_allowed(text),
            "smoking_allowed": DescriptionParser.extract_smoking(text),
            **DescriptionParser.extract_age_range(text),
            "vibe": DescriptionParser.extract_vibe(text),

            # Lease & availability
            "lease_type": DescriptionParser.extract_lease_type(text),
            "min_lease_months": DescriptionParser.extract_min_lease_months(text),
            "available_from": DescriptionParser.extract_available_from(text),
            **DescriptionParser.extract_price_range(text),

            # Property classification
            "building_type": DescriptionParser.extract_building_type(text),
            "domicile_type": DescriptionParser.extract_domicile_type(text),
            "room_type": DescriptionParser.extract_room_type(text),
            "shared_living": DescriptionParser.extract_shared_living(text),

            # Furnished details
            "furniture_level": DescriptionParser.extract_furniture_level(text),
            "furnished_bedroom": DescriptionParser.extract_furnished_bedroom(text),
            "furnished_common": DescriptionParser.extract_furnished_common(text),

            # Bathroom & laundry
            "bathroom_type": DescriptionParser.extract_bathroom_type(text),
            "laundry_type": DescriptionParser.extract_laundry_type(text),

            # Transit
            "transit_proximity": DescriptionParser.extract_transit_proximity(text),
            "transit_description": DescriptionParser.extract_transit_description(text),

            # Amenities
            "dishwasher": DescriptionParser.extract_dishwasher(text),
            "balcony": DescriptionParser.extract_balcony(text),
            "fireplace": DescriptionParser.extract_fireplace(text),
            "air_conditioning": DescriptionParser.extract_ac(text),
            "ev_charging": DescriptionParser.extract_ev_charging(text),
            "gym_access": DescriptionParser.extract_gym(text),
            "storage_locker": DescriptionParser.extract_storage(text),
            "close_to_amenities": DescriptionParser.extract_amenities_proximity(text),
            "has_views": DescriptionParser.extract_views(text),

            # Existing booleans (from description)
            "utilities_included": DescriptionParser.extract_utilities(text),
            "parking_included": DescriptionParser.extract_parking(text),
            "pets_allowed": DescriptionParser.extract_pets(text),

            # Numeric from description
            "num_bedrooms": DescriptionParser.extract_bedrooms(text),
            "num_bathrooms": DescriptionParser.extract_bathrooms(text),

            # Location
            "neighbourhood": DescriptionParser.normalize_neighbourhood(loc_text),
        }

    # ── Gender preference ────────────────────────────────────────

    @staticmethod
    def extract_gender_preference(text: str) -> Optional[str]:
        t = text.lower()

        if re.search(
            r'\b(?:no\s+couples?|sorry\s+no\s+couples?|couples?\s+not\s+(?:allowed|accepted|welcome)|single\s+occupancy\s+only)\b',
            t,
        ):
            return "no_couples"

        if re.search(r'\bcouples?\s+(?:welcome|ok|okay|allowed|accepted|friendly)\b', t):
            return "couples_welcome"

        if re.search(
            r'\b(?:female|women|woman|girl|lady|ladies)\s*(?:only|preferred|pref)\b'
            r'|\bonly\s+(?:female|women|ladies)\b'
            r'|\bfor\s+(?:a\s+)?(?:female|woman|lady)\b',
            t,
        ):
            return "female_only"

        if re.search(
            r'\b(?:male|men|man|guy|gentleman)\s*(?:only|preferred|pref)\b'
            r'|\bonly\s+(?:male|men|gentleman)\b'
            r'|\bfor\s+(?:a\s+)?(?:male|man|gentleman)\b',
            t,
        ):
            return "male_only"

        return None

    # ── Couples allowed ──────────────────────────────────────────

    @staticmethod
    def extract_couples_allowed(text: str) -> Optional[bool]:
        t = text.lower()

        if re.search(
            r'\b(?:no\s+couples?|couples?\s+not\s+(?:allowed|accepted|welcome)|single\s+occupancy\s+only)\b',
            t,
        ):
            return False

        if re.search(r'\bcouples?\s+(?:welcome|ok|okay|allowed|accepted|friendly)\b', t):
            return True

        return None

    # ── Smoking ──────────────────────────────────────────────────

    @staticmethod
    def extract_smoking(text: str) -> Optional[bool]:
        t = text.lower()

        if re.search(
            r'\b(?:no\s+smok(?:ing|ers?)|smoke[\s-]?free|non[\s-]?smok(?:ing|ers?)|doesn.t\s+smoke)\b',
            t,
        ):
            return False

        if re.search(r'\bsmok(?:ing|ers?)\s+(?:ok|okay|allowed|welcome|friendly)\b', t):
            return True

        return None

    # ── Age range ────────────────────────────────────────────────

    @staticmethod
    def extract_age_range(text: str) -> dict:
        """Returns dict with age_range_min and age_range_max (or None)."""
        t = text.lower()

        # Pattern: "in their 20-30's" / "20's - 30's" / "ages 20-35"
        m = re.search(
            r'(?:in\s+their|ages?|aged?)\s+(\d{2})[\s\-\']*(?:s\s*[\-–to]+\s*)?(\d{2})[\s\']*s?\b',
            t,
        )
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            if 18 <= lo <= 80 and 18 <= hi <= 80:
                return {"age_range_min": lo, "age_range_max": hi}

        # Pattern: "20s and 30s" / "20's and 30's"
        m = re.search(r"(\d{2})[\'\u2019]?s\s+(?:and|or|to)\s+(\d{2})[\'\u2019]?s", t)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            if 18 <= lo <= 80 and 18 <= hi <= 80:
                return {"age_range_min": lo, "age_range_max": hi}

        # Pattern: "between 25-40" / "ages 25 to 40"
        m = re.search(r'(?:between|ages?)\s+(\d{2})\s*[\-–to]+\s*(\d{2})', t)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            if 18 <= lo <= 80 and 18 <= hi <= 80:
                return {"age_range_min": lo, "age_range_max": hi}

        return {"age_range_min": None, "age_range_max": None}

    # ── Vibe ─────────────────────────────────────────────────────

    @staticmethod
    def extract_vibe(text: str) -> Optional[str]:
        t = text.lower()

        if re.search(r'\b(?:quiet|peaceful|low[\s-]?key|laid[\s-]?back|calm|tranquil|easy[\s-]?going)\b', t):
            return "quiet"
        if re.search(r'\b(?:professional|working\s+professional)\b', t):
            return "professional"
        if re.search(r'\b(?:student|university|college|studying)\b', t):
            return "student"
        if re.search(r'\b(?:social|outgoing|friendly\s+house|party|420[\s-]?friendly)\b', t):
            return "social"

        return None

    # ── Lease type ───────────────────────────────────────────────

    @staticmethod
    def extract_lease_type(text: str) -> Optional[str]:
        t = text.lower()

        if re.search(r'month[\s-]?to[\s-]?month|m2m|mth[\s-]?to[\s-]?mth|no\s+lease', t):
            return "month_to_month"

        if re.search(
            r'(?:minimum|min\.?)\s+\d+[\s-]*(?:month|mth)'
            r'|\d+[\s-]*(?:month|mth)\s+(?:minimum|min|lease|commitment|sublet|term)'
            r'|\b(?:fixed|annual|yearly|one[\s-]?year)\s+(?:term|lease)\b'
            r'|\blease\s+(?:required|agreement|contract)\b',
            t,
        ):
            return "fixed_term"

        return None

    @staticmethod
    def extract_min_lease_months(text: str) -> Optional[int]:
        t = text.lower()
        patterns = [
            r'(?:minimum|min\.?)\s*:?\s*(\d+)[\s-]*(?:month|mth)',
            r'(\d+)[\s-]*(?:month|mth)\s*(?:minimum|min|lease|commitment|term|sublet)',
            r'(?:lease|term)\s*:?\s*(\d+)[\s-]*(?:month|mth)',
            r'(\d+)[\s-]*(?:year|yr)\s*(?:minimum|min|lease|commitment|term)',
            r'(?:minimum|min\.?)\s*:?\s*(\d+)[\s-]*(?:year|yr)',
        ]

        for pattern in patterns:
            match = re.search(pattern, t)
            if match:
                val = int(match.group(1))
                if re.search(r'year|yr', match.group(0)):
                    val *= 12
                if 1 <= val <= 60:
                    return val

        return None

    # ── Available from ───────────────────────────────────────────

    @staticmethod
    def extract_available_from(text: str) -> Optional[str]:
        """Extract move-in / availability date as ISO string."""
        t = text.lower()

        # "available April 1, 2026" / "available April 1st 2026"
        months = r'(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
        m = re.search(
            rf'(?:available|move[\s-]?in|starting|from)\s+{months}\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s*(\d{{4}})',
            t,
        )
        if m:
            month_str, day_str, year_str = m.group(1), m.group(2), m.group(3)
            for fmt in ("%B %d %Y", "%b %d %Y"):
                try:
                    d = datetime.strptime(f"{month_str} {day_str} {year_str}", fmt)
                    return d.strftime("%Y-%m-%d")
                except ValueError:
                    continue

        # "available 2026-04-01" / "available 04/01/2026"
        m = re.search(r'(?:available|move[\s-]?in|starting|from)\s+(\d{4})[/-](\d{1,2})[/-](\d{1,2})', t)
        if m:
            try:
                d = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                return d.strftime("%Y-%m-%d")
            except ValueError:
                pass

        # "available immediately" / "available now"
        if re.search(r'(?:available|move[\s-]?in)\s+(?:immediately|now|asap|right\s+away)', t):
            return "immediate"

        return None

    # ── Price range ──────────────────────────────────────────────

    @staticmethod
    def extract_price_range(text: str) -> dict:
        """Extract price range if listing shows min-max pricing."""
        t = text
        # "$1,300 – $2,300/month" or "$1300-$2300"
        m = re.search(
            r'\$\s*([\d,]+)\s*[\-–—to]+\s*\$\s*([\d,]+)\s*(?:/\s*(?:mo(?:nth)?|mth))?',
            t, re.I,
        )
        if m:
            lo = int(m.group(1).replace(",", ""))
            hi = int(m.group(2).replace(",", ""))
            if 100 <= lo <= 10000 and 100 <= hi <= 10000 and lo < hi:
                return {"price_min": lo, "price_max": hi}

        return {"price_min": None, "price_max": None}

    # ── Building type ────────────────────────────────────────────

    @staticmethod
    def extract_building_type(text: str) -> Optional[str]:
        t = text.lower()

        if re.search(r'\b(?:high[\s-]?rise|hi[\s-]?rise|tower)\b', t):
            return "high_rise"
        if re.search(r'\b(?:low[\s-]?rise)\b', t):
            return "low_rise"
        if re.search(r'\b(?:walk[\s-]?up)\b', t):
            return "walk_up"
        if re.search(r'\b(?:townhouse|town[\s-]?home|row[\s-]?house)\b', t):
            return "townhouse"
        if re.search(r'\b(?:laneway|lane[\s-]?way)\b', t):
            return "laneway"
        if re.search(r'\b(?:basement|below[\s-]?grade|ground[\s-]?level\s+suite)\b', t):
            return "basement"
        if re.search(r'\b(?:detached|single\s+family|house)\b', t):
            return "house"

        return None

    # ── Domicile type ────────────────────────────────────────────

    @staticmethod
    def extract_domicile_type(text: str) -> Optional[str]:
        t = text.lower()

        if re.search(r'\b(?:condo(?:minium)?)\b', t):
            return "condo"
        if re.search(r'\b(?:townhouse|town[\s-]?home)\b', t):
            return "townhouse"
        if re.search(r'\b(?:studio|bachelor)\b', t):
            return "studio"
        if re.search(r'\b(?:basement\s+suite|garden\s+suite)\b', t):
            return "suite"
        if re.search(r'\b(?:detached\s+house|single\s+family\s+house|whole\s+house)\b', t):
            return "house"
        if re.search(r'\bapartment\b', t):
            return "apartment"

        return None

    # ── Room type ────────────────────────────────────────────────

    @staticmethod
    def extract_room_type(text: str) -> Optional[str]:
        t = text.lower()

        if re.search(r'\b(?:master\s+bed(?:room)?|primary\s+(?:bed)?room)\b', t):
            return "master"
        if re.search(r'\b(?:den|flex\s+room|converted\s+den)\b', t):
            return "den"
        if re.search(r'\b(?:shared\s+room|sharing\s+(?:a\s+)?room|bunk)\b', t):
            return "shared_room"
        if re.search(r'\b(?:private\s+room|private\s+bed(?:room)?|your\s+own\s+room)\b', t):
            return "private_room"
        if re.search(r'\b(?:single\s+room|small\s+room|second\s+bed(?:room)?)\b', t):
            return "single"

        return None

    # ── Shared living ────────────────────────────────────────────

    @staticmethod
    def extract_shared_living(text: str) -> Optional[bool]:
        t = text.lower()

        if re.search(
            r'\b(?:shared\s+(?:apartment|house|home|accommodation|living|space|place))\b'
            r'|\b(?:looking\s+for\s+(?:a\s+)?roommate|housemate|flatmate)\b'
            r'|\b(?:roommate\s+(?:wanted|needed))\b'
            r'|\b(?:room\s+(?:available|for\s+rent)\s+in\s+(?:a\s+)?(?:shared|[23]\s*(?:bed|br)))\b',
            t,
        ):
            return True

        if re.search(r'\b(?:entire\s+(?:unit|suite|apartment)|whole\s+(?:apartment|house|unit)|no\s+roommates?)\b', t):
            return False

        return None

    # ── Furnished bedroom ────────────────────────────────────────

    @staticmethod
    def extract_furnished_bedroom(text: str) -> Optional[bool]:
        t = text.lower()

        if re.search(
            r'\b(?:furnished\s+(?:private\s+)?bed(?:room)?)\b'
            r'|\b(?:private\s+furnished\s+bed(?:room)?)\b'
            r'|\b(?:bed(?:room)?\s+(?:is\s+)?(?:fully\s+)?furnished)\b'
            r'|\b(?:room\s+(?:comes?\s+)?(?:fully\s+)?furnished)\b',
            t,
        ):
            return True

        if re.search(
            r'\b(?:unfurnished\s+(?:private\s+)?bed(?:room)?|bed(?:room)?\s+(?:is\s+)?unfurnished)\b'
            r'|\b(?:bring\s+your\s+own\s+(?:bed|furniture))\b'
            r'|\b(?:bed(?:room)?\s+not\s+furnished)\b',
            t,
        ):
            return False

        return None

    # ── Furnished common areas ───────────────────────────────────

    @staticmethod
    def extract_furnished_common(text: str) -> Optional[bool]:
        t = text.lower()

        if re.search(
            r'\b(?:shared\s+(?:spaces?|areas?)\s+(?:are\s+)?(?:fully\s+)?furnished)\b'
            r'|\b(?:fully\s+furnished\s+(?:shared\s+)?(?:kitchen|living|common))\b'
            r'|\b(?:furnished\s+(?:common|shared|living)\s+(?:area|space))\b'
            r'|\b(?:(?:common|shared)\s+areas?\s+(?:fully\s+)?furnished)\b',
            t,
        ):
            return True

        return None

    # ── Furniture level ──────────────────────────────────────────

    @staticmethod
    def extract_furniture_level(text: str) -> Optional[str]:
        t = text.lower()

        if re.search(
            r'\b(?:unfurnished|un[\s-]?furnished|no\s+furniture|not\s+furnished|bring\s+your\s+own\s+furniture)\b',
            t,
        ):
            return "unfurnished"

        if re.search(
            r'\b(?:fully|completely|100%)\s+furnished\b'
            r'|\bfurnished\s+(?:with\s+)?(?:everything|all)\b'
            r'|\bturn[\s-]?key\b',
            t,
        ):
            return "fully_furnished"

        if re.search(
            r'\b(?:partially|partly|semi[\s-]?)\s*furnished\b'
            r'|\bfurnished\s+(?:with|includes?)\b'
            r'|\b(?:bed|desk|dresser|table)\s+(?:included|provided)\b',
            t,
        ):
            return "partially_furnished"

        if re.search(r'\bfurnished\b', t):
            return "fully_furnished"

        return None

    # ── Bathroom type ────────────────────────────────────────────

    @staticmethod
    def extract_bathroom_type(text: str) -> Optional[str]:
        t = text.lower()

        if re.search(
            r'\b(?:private|own|ensuite|en[\s-]?suite|personal|full\s+private)\s+(?:bath(?:room)?|washroom|shower)\b'
            r'|\b(?:bath(?:room)?|washroom)\s+(?:private|ensuite|en[\s-]?suite)\b'
            r'|\byour\s+own\s+(?:bath(?:room)?|washroom)\b',
            t,
        ):
            return "private"

        if re.search(
            r'\b(?:shared|share|common|communal)\s+(?:bath(?:room)?|washroom|shower)\b'
            r'|\b(?:bath(?:room)?|washroom)\s+(?:shared|share)\b',
            t,
        ):
            return "shared"

        return None

    # ── Laundry type ─────────────────────────────────────────────

    @staticmethod
    def extract_laundry_type(text: str) -> Optional[str]:
        t = text.lower()

        if re.search(
            r'\b(?:in[\s-]?(?:suite|unit)\s+(?:washer|laundry|w/d))\b'
            r'|\b(?:laundry|washer|w/d|washer[\s/&]+dryer)\s+(?:in|inside)\s+(?:unit|suite|apartment|home)\b'
            r'|\bin[\s-]?(?:unit|suite)\s+(?:laundry|washer|w/d)\b'
            r'|\bw/d\s+in\s+(?:unit|suite)\b',
            t,
        ):
            return "in_unit"

        if re.search(
            r'\b(?:laundry|washer)\s+(?:in[\s-]?building|on[\s-]?site|shared|common|downstairs)\b'
            r'|\b(?:shared|common|coin)\s+(?:laundry|washer)\b'
            r'|\blaundry\s+(?:room|facilities?)\s+(?:available|on|in)\b',
            t,
        ):
            return "in_building"

        return None

    # ── Transit proximity ────────────────────────────────────────

    _SKYTRAIN_STATIONS = (
        r'waterfront|burrard|granville|stadium|main\s+st|commercial[\s-]broadway'
        r'|nanaimo|29th\s+ave|joyce[\s-]collingwood|patterson|metrotown'
        r'|royal\s+oak|edmonds|new\s+westminster|columbia|scott\s+road'
        r'|gateway|surrey\s+central|king\s+george'
        r'|vcc[\s-]clark|renfrew|rupert|gilmore|brentwood|holdom|sperling'
        r'|lake\s+city|production\s+way|lougheed|burquitlam'
        r'|moody\s+centre|inlet\s+centre|coquitlam\s+central|lincoln|lafarge'
        r'|yaletown|olympic\s+village|broadway[\s-]city\s+hall|king\s+edward'
        r'|oakridge|langara|marine\s+drive|bridgeport|templeton'
        r'|sea\s+island|yvr[\s-]airport|aberdeen|lansdowne|richmond[\s-]brighouse'
    )

    @staticmethod
    def extract_transit_proximity(text: str) -> Optional[str]:
        t = text.lower()

        if re.search(
            r'\b(?:near|close\s+to|next\s+to|steps?\s+(?:from|to)|walk(?:ing)?\s+(?:distance\s+)?(?:from|to)|'
            r'block[s]?\s+(?:from|to)|min(?:ute)?s?\s+(?:from|to|walk))\s+'
            r'(?:the\s+)?(?:skytrain|sky[\s-]?train)\b',
            t,
        ):
            return "near_skytrain"

        if re.search(
            rf'\b(?:near|close|walk|block|min)\b.*?\b(?:{DescriptionParser._SKYTRAIN_STATIONS})\s*(?:station|skytrain|sky\s+train)\b',
            t,
        ):
            return "near_skytrain"

        if re.search(
            r'\b(?:near|close\s+to|steps?\s+to|walk(?:ing)?\s+to)\s+(?:the\s+)?(?:bus|b[\s-]?line|transit\s+stop)\b'
            r'|\b(?:bus\s+(?:stop|route)\s+(?:near|close|outside|steps?))\b'
            r'|\b(?:on\s+(?:a\s+)?(?:bus|transit)\s+(?:route|line))\b',
            t,
        ):
            return "near_bus"

        if re.search(
            r'\b(?:excellent|great|good|convenient|easy)\s+(?:access\s+to\s+)?'
            r'(?:transit|transportation|public\s+transit|public\s+transport)\b'
            r'|\btransit[\s-]?(?:friendly|oriented|accessible)\b',
            t,
        ):
            return "good_transit"

        return None

    @staticmethod
    def extract_transit_description(text: str) -> Optional[str]:
        t = text.lower()

        patterns = [
            r'(\d+[\s-]?(?:minute|min|block)s?\s+(?:walk\s+)?(?:from|to)\s+[^.,;!]{3,40}?(?:skytrain|sky[\s-]?train|station))',
            r'((?:close|near|next|adjacent|walking\s+distance)\s+(?:to\s+)?[^.,;!]{3,40}?(?:skytrain|sky[\s-]?train|station))',
            r'(\d+[\s-]?(?:minute|min|block)s?\s+(?:walk\s+)?(?:from|to)\s+[^.,;!]{3,30}?(?:bus|transit|b[\s-]?line))',
        ]

        for pattern in patterns:
            match = re.search(pattern, t)
            if match:
                return match.group(1).strip()

        return None

    # ── Amenities: dishwasher ────────────────────────────────────

    @staticmethod
    def extract_dishwasher(text: str) -> Optional[bool]:
        t = text.lower()
        if re.search(r'\bdishwasher\b', t):
            return True
        return None

    # ── Amenities: balcony ───────────────────────────────────────

    @staticmethod
    def extract_balcony(text: str) -> Optional[bool]:
        t = text.lower()
        if re.search(r'\b(?:balcon(?:y|ies)|patio|deck|terrace|outdoor\s+space)\b', t):
            return True
        return None

    # ── Amenities: fireplace ─────────────────────────────────────

    @staticmethod
    def extract_fireplace(text: str) -> Optional[bool]:
        t = text.lower()
        if re.search(r'\b(?:fireplace|gas\s+fireplace|electric\s+fireplace)\b', t):
            return True
        return None

    # ── Amenities: A/C ───────────────────────────────────────────

    @staticmethod
    def extract_ac(text: str) -> Optional[bool]:
        t = text.lower()
        if re.search(r'\b(?:air\s+condition(?:ing|er|ed)|a/?c|central\s+air|portable\s+ac|mini[\s-]?split)\b', t):
            return True
        return None

    # ── Amenities: EV charging ───────────────────────────────────

    @staticmethod
    def extract_ev_charging(text: str) -> Optional[bool]:
        t = text.lower()
        if re.search(r'\b(?:ev\s+charg(?:ing|er)|electric\s+vehicle\s+charg(?:ing|er)|level\s+2\s+charg)\b', t):
            return True
        return None

    # ── Amenities: gym ───────────────────────────────────────────

    @staticmethod
    def extract_gym(text: str) -> Optional[bool]:
        t = text.lower()
        if re.search(r'\b(?:gym|fitness\s+(?:centre|center|room)|exercise\s+room|work[\s-]?out\s+(?:room|facility))\b', t):
            return True
        return None

    # ── Amenities: storage ───────────────────────────────────────

    @staticmethod
    def extract_storage(text: str) -> Optional[bool]:
        t = text.lower()
        if re.search(r'\b(?:storage\s+locker|locker\s+(?:included|available)|storage\s+(?:unit|space|included))\b', t):
            return True
        return None

    # ── Close to amenities ───────────────────────────────────────

    @staticmethod
    def extract_amenities_proximity(text: str) -> Optional[bool]:
        t = text.lower()
        if re.search(
            r'\b(?:walkable\s+to\s+(?:lots\s+of\s+)?(?:shops?|stores?|restaurants?|cafes?|groceries|grocery|amenities))\b'
            r'|\b(?:close\s+to\s+(?:shops?|stores?|restaurants?|amenities|everything))\b'
            r'|\b(?:steps?\s+(?:from|to)\s+(?:shops?|restaurants?|cafes?|amenities))\b'
            r'|\b(?:near\s+(?:all\s+)?amenities)\b'
            r'|\b(?:walking\s+distance\s+to\s+(?:shops?|restaurants?|groceries|amenities))\b',
            t,
        ):
            return True

        return None

    # ── Views ────────────────────────────────────────────────────

    @staticmethod
    def extract_views(text: str) -> Optional[bool]:
        t = text.lower()
        if re.search(
            r'\b(?:city\s+view|mountain\s+view|ocean\s+view|water\s+view|park\s+view)\b'
            r'|\b(?:views?\s+of\s+(?:the\s+)?(?:city|mountains?|ocean|water|park|inlet|harbour))\b'
            r'|\b(?:with\s+(?:a\s+)?(?:beautiful|stunning|gorgeous|amazing)?\s*views?)\b'
            r'|\b(?:rooms?\s+with\s+(?:city\s+)?views?)\b',
            t,
        ):
            return True

        return None

    # ── Utilities included ───────────────────────────────────────

    @staticmethod
    def extract_utilities(text: str) -> Optional[bool]:
        t = text.lower()

        if re.search(
            r'\b(?:no\s+utilities|utilities\s+not\s+included|utilities\s+extra|hydro\s+extra)\b',
            t,
        ):
            return False

        if re.search(
            r'\b(?:utilities?\s+included|all\s+(?:bills?|utilities?)\s+included)\b'
            r'|\b(?:hydro\s+included|heat\s+included|internet\s+included)\b'
            r'|\b(?:includes?\s+(?:all\s+)?utilit(?:y|ies))\b'
            r'|\b(?:all[\s-]?inclusive|everything\s+included)\b',
            t,
        ):
            return True

        return None

    # ── Parking included ─────────────────────────────────────────

    @staticmethod
    def extract_parking(text: str) -> Optional[bool]:
        t = text.lower()

        if re.search(
            r'\b(?:no\s+parking|parking\s+not\s+included|street\s+parking\s+only)\b',
            t,
        ):
            return False

        if re.search(
            r'\b(?:parking\s+(?:included|available|spot|space|stall))\b'
            r'|\b(?:underground\s+parking|covered\s+parking)\b'
            r'|\b(?:(?:1|one|two|2)\s+parking\s+(?:spot|space|stall))\b'
            r'|\b(?:includes?\s+parking)\b',
            t,
        ):
            return True

        return None

    # ── Pets allowed ─────────────────────────────────────────────

    @staticmethod
    def extract_pets(text: str) -> Optional[bool]:
        t = text.lower()

        if re.search(
            r'\b(?:no\s+pets?|pets?\s+not\s+allowed|sorry\s+no\s+pets?|pet[\s-]?free)\b',
            t,
        ):
            return False

        if re.search(
            r'\b(?:pet[\s-]?friendly|pets?\s+(?:ok|okay|welcome|allowed))\b'
            r'|\b(?:cats?\s+(?:ok|okay|welcome|allowed))\b'
            r'|\b(?:dogs?\s+(?:ok|okay|welcome|allowed))\b'
            r'|\b(?:small\s+pets?\s+(?:ok|allowed))\b',
            t,
        ):
            return True

        return None

    # ── Bedroom count from description ───────────────────────────

    @staticmethod
    def extract_bedrooms(text: str) -> Optional[int]:
        t = text.lower()
        m = re.search(
            r'(\d)\s*[\-]?\s*(?:br|bed(?:room)?s?|bdrm|bdr)\b'
            r'|(\d)\s*[\-]?\s*bedroom',
            t,
        )
        if m:
            val = int(m.group(1) or m.group(2))
            if 1 <= val <= 10:
                return val
        return None

    # ── Bathroom count from description ──────────────────────────

    @staticmethod
    def extract_bathrooms(text: str) -> Optional[int]:
        t = text.lower()
        # "2 bath" / "2-bathroom" / "1.5 bath"
        m = re.search(r'(\d+(?:\.\d)?)\s*[\-]?\s*(?:bath(?:room)?s?|ba)\b', t)
        if m:
            val = float(m.group(1))
            if 1 <= val <= 10:
                return int(val) if val == int(val) else int(val) + 1
        return None

    # ── Neighbourhood normalization ──────────────────────────────

    @staticmethod
    def normalize_neighbourhood(text: str) -> Optional[str]:
        for pattern, name in NEIGHBOURHOOD_PATTERNS:
            if pattern.search(text):
                return name
        return None
