"""Data models for rental listings across all sources."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ListingType(str, Enum):
    """Type of rental accommodation."""
    ROOM_SHARED = "room_shared"          # Shared room (multiple people)
    ROOM_PRIVATE = "room_private"        # Private room in shared house
    BASEMENT_SUITE = "basement_suite"    # Basement suite
    STUDIO = "studio"                    # Studio/bachelor
    ONE_BEDROOM = "1br"                  # 1 bedroom apartment
    TWO_BEDROOM = "2br"                  # 2 bedroom apartment
    THREE_BEDROOM = "3br"               # 3+ bedroom apartment
    HOUSE = "house"                      # Whole house
    LANEWAY = "laneway"                  # Laneway house
    OTHER = "other"                      # Catch-all


class ListingSource(str, Enum):
    """Source platform for the listing."""
    CRAIGSLIST = "craigslist"
    KIJIJI = "kijiji"
    FACEBOOK = "facebook"


@dataclass
class Listing:
    """Unified listing model across all rental sources.

    Every scraper produces Listing objects with the same schema,
    enabling cross-source comparison and analysis.
    """

    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: ListingSource = ListingSource.CRAIGSLIST
    url: str = ""
    title: str = ""

    # Pricing
    price: Optional[int] = None  # Monthly rent in CAD

    # Location
    location: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Description
    description: str = ""

    # Dates
    posted_date: Optional[datetime] = None
    available_date: Optional[datetime] = None
    extracted_at: datetime = field(default_factory=datetime.now)

    # Classification
    listing_type: ListingType = ListingType.OTHER

    # Property details
    num_bedrooms: Optional[int] = None
    num_bathrooms: Optional[int] = None
    num_roommates: Optional[int] = None
    square_feet: Optional[int] = None

    # Amenities (basic booleans — kept for backward compatibility)
    utilities_included: Optional[bool] = None
    furnished: Optional[bool] = None
    pets_allowed: Optional[bool] = None
    parking_included: Optional[bool] = None
    laundry_in_unit: Optional[bool] = None

    # Enhanced fields (extracted from descriptions)
    gender_preference: Optional[str] = None    # female_only | male_only | couples_welcome | no_couples
    lease_type: Optional[str] = None           # month_to_month | fixed_term
    min_lease_months: Optional[int] = None     # minimum lease length in months
    bathroom_type: Optional[str] = None        # private | shared
    laundry_type: Optional[str] = None         # in_unit | in_building
    transit_proximity: Optional[str] = None    # near_skytrain | near_bus | good_transit
    transit_description: Optional[str] = None  # free text, e.g. "5 min to Granville SkyTrain"
    furniture_level: Optional[str] = None      # fully_furnished | partially_furnished | unfurnished
    neighbourhood: Optional[str] = None        # normalized Vancouver neighbourhood

    # Media
    image_urls: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON/CSV export."""
        data = {}
        for k, v in self.__dict__.items():
            if isinstance(v, Enum):
                data[k] = v.value
            elif isinstance(v, datetime):
                data[k] = v.isoformat()
            elif isinstance(v, list):
                data[k] = v.copy()
            else:
                data[k] = v
        return data

    def summary(self) -> str:
        """One-line human-readable summary."""
        price_str = f"${self.price}/mo" if self.price else "Price N/A"
        loc = self.location or "Location N/A"
        return f"[{self.source.value}] {price_str} - {self.title[:60]} ({loc})"

    def __repr__(self) -> str:
        price_str = f"${self.price}" if self.price else "N/A"
        return (
            f"Listing(source={self.source.value!r}, price={price_str}, "
            f"title={self.title[:40]!r}, location={self.location!r})"
        )
