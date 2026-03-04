"""Parse Vancouver rental listing descriptions for structured fields.

Uses regex patterns and keyword matching to extract:
- Gender/occupancy preferences
- Lease terms and minimum stay
- Bathroom type (private vs shared)
- Laundry details (in-unit, in-building)
- Transit proximity
- Furniture level
- Normalized Vancouver neighbourhood
"""

from __future__ import annotations

import re
from typing import Optional


# ── Vancouver neighbourhood normalization ────────────────────────

# Maps regex patterns to canonical neighbourhood names.
# Ordered roughly west-to-east, north-to-south.
NEIGHBOURHOOD_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\b(?:downtown|dt|west\s+end|yaletown|coal\s+harbour|gastown|crosstown)\b', re.I), "Downtown"),
    (re.compile(r'\b(?:west\s+point\s+grey|wpg)\b', re.I), "West Point Grey"),
    (re.compile(r'\bubc\b', re.I), "UBC"),
    (re.compile(r'\b(?:kitsilano|kits)\b', re.I), "Kitsilano"),
    (re.compile(r'\bfairview\b', re.I), "Fairview"),
    (re.compile(r'\b(?:mount\s+pleasant|mt\s+pleasant)\b', re.I), "Mount Pleasant"),
    (re.compile(r'\b(?:cambie|cambie\s+village)\b', re.I), "Cambie"),
    (re.compile(r'\b(?:south\s+cambie|riley\s+park|riley[\s-]park)\b', re.I), "Riley Park"),
    (re.compile(r'\b(?:kerrisdale)\b', re.I), "Kerrisdale"),
    (re.compile(r'\b(?:dunbar|dunbar[\s-]southlands)\b', re.I), "Dunbar"),
    (re.compile(r'\b(?:arbutus[\s-]?ridge|arbutus)\b', re.I), "Arbutus Ridge"),
    (re.compile(r'\b(?:shaughnessy)\b', re.I), "Shaughnessy"),
    (re.compile(r'\b(?:oakridge)\b', re.I), "Oakridge"),
    (re.compile(r'\b(?:marpole)\b', re.I), "Marpole"),
    (re.compile(r'\b(?:south\s+vancouver|south\s+van)\b', re.I), "South Vancouver"),
    (re.compile(r'\b(?:sunset)\b', re.I), "Sunset"),
    (re.compile(r'\b(?:victoria[\s-]?fraserview|victoria\s+dr|vic[\s-]?fraserview)\b', re.I), "Victoria-Fraserview"),
    (re.compile(r'\b(?:killarney)\b', re.I), "Killarney"),
    (re.compile(r'\b(?:champlain\s+heights|champlain)\b', re.I), "Champlain Heights"),
    (re.compile(r'\b(?:river\s+district|south\s+marine)\b', re.I), "River District"),
    (re.compile(r'\b(?:east\s+van(?:couver)?|east\s+side)\b', re.I), "East Vancouver"),
    (re.compile(r'\b(?:strathcona|chinatown)\b', re.I), "Strathcona"),
    (re.compile(r'\b(?:grandview[\s-]?woodland|commercial\s+dr(?:ive)?|the\s+drive)\b', re.I), "Grandview-Woodland"),
    (re.compile(r'\b(?:hastings[\s-]?sunrise)\b', re.I), "Hastings-Sunrise"),
    (re.compile(r'\b(?:renfrew[\s-]?collingwood|renfrew|collingwood)\b', re.I), "Renfrew-Collingwood"),
    (re.compile(r'\b(?:kensington[\s-]?cedar\s+cottage|kensington|cedar\s+cottage)\b', re.I), "Kensington-Cedar Cottage"),
    (re.compile(r'\b(?:joyce[\s-]?collingwood|joyce)\b', re.I), "Joyce-Collingwood"),
    (re.compile(r'\b(?:metrotown)\b', re.I), "Metrotown"),
    (re.compile(r'\b(?:burnaby)\b', re.I), "Burnaby"),
    (re.compile(r'\b(?:new\s+west(?:minster)?)\b', re.I), "New Westminster"),
    (re.compile(r'\b(?:north\s+van(?:couver)?)\b', re.I), "North Vancouver"),
    (re.compile(r'\b(?:richmond)\b', re.I), "Richmond"),
    (re.compile(r'\b(?:coquitlam|port\s+coquitlam|poco)\b', re.I), "Coquitlam"),
    (re.compile(r'\b(?:surrey)\b', re.I), "Surrey"),
]


class DescriptionParser:
    """Parse rental listing descriptions for structured fields.

    All methods are static — no instance state needed.
    Call parse_all() for a complete extraction pass.
    """

    @staticmethod
    def parse_all(description: str, title: str = "", location: str = "") -> dict:
        """Extract all structured fields from listing text.

        Args:
            description: Full listing description text.
            title: Listing title/headline.
            location: Raw location string from the listing.

        Returns:
            Dict with keys matching Listing model field names.
            Values are None when no signal detected.
        """
        text = f"{title} {description}".strip()

        return {
            "gender_preference": DescriptionParser.extract_gender_preference(text),
            "lease_type": DescriptionParser.extract_lease_type(text),
            "min_lease_months": DescriptionParser.extract_min_lease_months(text),
            "bathroom_type": DescriptionParser.extract_bathroom_type(text),
            "laundry_type": DescriptionParser.extract_laundry_type(text),
            "transit_proximity": DescriptionParser.extract_transit_proximity(text),
            "transit_description": DescriptionParser.extract_transit_description(text),
            "furniture_level": DescriptionParser.extract_furniture_level(text),
            "neighbourhood": DescriptionParser.normalize_neighbourhood(
                f"{location} {title} {description}"
            ),
        }

    # ── Gender preference ────────────────────────────────────────

    @staticmethod
    def extract_gender_preference(text: str) -> Optional[str]:
        """Extract gender/occupancy preferences.

        Returns: female_only | male_only | couples_welcome | no_couples | None
        """
        t = text.lower()

        # No couples (check before couples_welcome to avoid false positives)
        if re.search(
            r'\b(?:no\s+couples?|sorry\s+no\s+couples?|couples?\s+not\s+(?:allowed|accepted|welcome))\b',
            t,
        ):
            return "no_couples"

        # Couples welcome
        if re.search(
            r'\bcouples?\s+(?:welcome|ok|okay|allowed|accepted|friendly)\b',
            t,
        ):
            return "couples_welcome"

        # Female only
        if re.search(
            r'\b(?:female|women|woman|girl|lady|ladies)\s*(?:only|preferred|pref)\b'
            r'|\bonly\s+(?:female|women|ladies)\b'
            r'|\bfor\s+(?:a\s+)?(?:female|woman|lady)\b',
            t,
        ):
            return "female_only"

        # Male only
        if re.search(
            r'\b(?:male|men|man|guy|gentleman)\s*(?:only|preferred|pref)\b'
            r'|\bonly\s+(?:male|men|gentleman)\b'
            r'|\bfor\s+(?:a\s+)?(?:male|man|gentleman)\b',
            t,
        ):
            return "male_only"

        return None

    # ── Lease type ───────────────────────────────────────────────

    @staticmethod
    def extract_lease_type(text: str) -> Optional[str]:
        """Extract lease structure.

        Returns: month_to_month | fixed_term | None
        """
        t = text.lower()

        if re.search(r'month[\s-]?to[\s-]?month|m2m|mth[\s-]?to[\s-]?mth|no\s+lease', t):
            return "month_to_month"

        if re.search(
            r'(?:minimum|min\.?)\s+\d+\s*(?:month|mth)'
            r'|\d+\s*(?:month|mth)\s+(?:minimum|min|lease|commitment)'
            r'|\b(?:fixed|annual|yearly|one[\s-]?year)\s+(?:term|lease)\b'
            r'|\blease\s+(?:required|agreement|contract)\b',
            t,
        ):
            return "fixed_term"

        return None

    @staticmethod
    def extract_min_lease_months(text: str) -> Optional[int]:
        """Extract minimum lease length in months.

        Patterns:
            "6 month minimum", "minimum 3 months", "1 year lease",
            "lease: 12 months"
        """
        t = text.lower()
        patterns = [
            r'(?:minimum|min\.?)\s*:?\s*(\d+)\s*(?:month|mth)',
            r'(\d+)\s*(?:month|mth)\s*(?:minimum|min|lease|commitment|term)',
            r'(?:lease|term)\s*:?\s*(\d+)\s*(?:month|mth)',
            r'(\d+)\s*(?:year|yr)\s*(?:minimum|min|lease|commitment|term)',
            r'(?:minimum|min\.?)\s*:?\s*(\d+)\s*(?:year|yr)',
        ]

        for pattern in patterns:
            match = re.search(pattern, t)
            if match:
                val = int(match.group(1))
                # Convert years to months
                if re.search(r'year|yr', match.group(0)):
                    val *= 12
                if 1 <= val <= 60:
                    return val

        return None

    # ── Bathroom type ────────────────────────────────────────────

    @staticmethod
    def extract_bathroom_type(text: str) -> Optional[str]:
        """Extract bathroom sharing arrangement.

        Returns: private | shared | None
        """
        t = text.lower()

        if re.search(
            r'\b(?:private|own|ensuite|en[\s-]?suite|personal)\s+(?:bath(?:room)?|washroom|shower)\b'
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
        """Extract laundry availability.

        Returns: in_unit | in_building | None
        """
        t = text.lower()

        if re.search(
            r'\b(?:laundry|washer|w/d|washer[\s/&]+dryer)\s+(?:in|inside)\s+(?:unit|suite|apartment|home)\b'
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

    # SkyTrain station names for Vancouver area
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
        """Classify transit proximity.

        Returns: near_skytrain | near_bus | good_transit | None
        """
        t = text.lower()

        # Near SkyTrain (explicit mention or station name with proximity)
        if re.search(
            r'\b(?:near|close\s+to|next\s+to|steps?\s+(?:from|to)|walk(?:ing)?\s+(?:distance\s+)?(?:from|to)|'
            r'block[s]?\s+(?:from|to)|min(?:ute)?s?\s+(?:from|to|walk))\s+'
            r'(?:the\s+)?(?:skytrain|sky[\s-]?train)\b',
            t,
        ):
            return "near_skytrain"

        # Station name mentioned with proximity keywords
        if re.search(
            rf'\b(?:near|close|walk|block|min)\b.*?\b(?:{DescriptionParser._SKYTRAIN_STATIONS})\s*(?:station|skytrain|sky\s+train)\b',
            t,
        ):
            return "near_skytrain"

        # Near bus / B-Line
        if re.search(
            r'\b(?:near|close\s+to|steps?\s+to|walk(?:ing)?\s+to)\s+(?:the\s+)?(?:bus|b[\s-]?line|transit\s+stop)\b'
            r'|\b(?:bus\s+(?:stop|route)\s+(?:near|close|outside|steps?))\b'
            r'|\b(?:on\s+(?:a\s+)?(?:bus|transit)\s+(?:route|line))\b',
            t,
        ):
            return "near_bus"

        # Good transit generally
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
        """Extract detailed transit description for display.

        Returns human-readable snippet like "5 min walk to Commercial-Broadway SkyTrain".
        """
        t = text.lower()

        patterns = [
            # "5 min walk to X SkyTrain station"
            r'(\d+[\s-]?(?:minute|min|block)s?\s+(?:walk\s+)?(?:from|to)\s+[^.,;!]{3,40}?(?:skytrain|sky[\s-]?train|station))',
            # "close to X SkyTrain" / "near X station"
            r'((?:close|near|next|adjacent|walking\s+distance)\s+(?:to\s+)?[^.,;!]{3,40}?(?:skytrain|sky[\s-]?train|station))',
            # "X min to bus / transit"
            r'(\d+[\s-]?(?:minute|min|block)s?\s+(?:walk\s+)?(?:from|to)\s+[^.,;!]{3,30}?(?:bus|transit|b[\s-]?line))',
        ]

        for pattern in patterns:
            match = re.search(pattern, t)
            if match:
                return match.group(1).strip()

        return None

    # ── Furniture level ──────────────────────────────────────────

    @staticmethod
    def extract_furniture_level(text: str) -> Optional[str]:
        """Classify furniture availability.

        Returns: fully_furnished | partially_furnished | unfurnished | None
        """
        t = text.lower()

        # Unfurnished (check first — "unfurnished" contains "furnished")
        if re.search(
            r'\b(?:unfurnished|un[\s-]?furnished|no\s+furniture|not\s+furnished|bring\s+your\s+own\s+furniture)\b',
            t,
        ):
            return "unfurnished"

        # Fully furnished
        if re.search(
            r'\b(?:fully|completely|100%)\s+furnished\b'
            r'|\bfurnished\s+(?:with\s+)?(?:everything|all)\b'
            r'|\bturn[\s-]?key\b',
            t,
        ):
            return "fully_furnished"

        # Partially furnished (specific items mentioned)
        if re.search(
            r'\b(?:partially|partly|semi[\s-]?)\s*furnished\b'
            r'|\bfurnished\s+(?:with|includes?)\b'
            r'|\b(?:bed|desk|dresser|table)\s+(?:included|provided)\b',
            t,
        ):
            return "partially_furnished"

        # Bare "furnished" without qualifier defaults to fully
        if re.search(r'\bfurnished\b', t):
            return "fully_furnished"

        return None

    # ── Neighbourhood normalization ──────────────────────────────

    @staticmethod
    def normalize_neighbourhood(text: str) -> Optional[str]:
        """Map raw location/description text to a canonical Vancouver neighbourhood.

        Checks location string, title, and description for neighbourhood signals.
        Returns the first match found.
        """
        for pattern, name in NEIGHBOURHOOD_PATTERNS:
            if pattern.search(text):
                return name
        return None
