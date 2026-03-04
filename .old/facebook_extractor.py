"""LLM-powered extraction of structured listings from Facebook posts.

Facebook housing group posts are messy, inconsistent, and lack structured
fields. This module uses Claude to parse raw post text into structured
Listing objects with price, location, amenities, etc.

Two modes:
    1. Automated: Process RawFacebookPost objects from the scraper
    2. Manual dump: User copy/pastes posts separated by "---"
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from rental_scraper.models import Listing, ListingSource, ListingType

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are extracting structured rental listing data from a Facebook housing group post.

Analyze this post and extract the following fields. Return valid JSON only - no markdown, no explanation.

Post text:
<post>
{post_text}
</post>

Return a JSON object with these fields:
{{
    "is_offering": true/false,  // true if offering accommodation, false if seeking
    "title": "brief descriptive title",
    "price": null or integer (monthly rent in CAD, e.g. 1200),
    "location": "neighborhood or area in Vancouver",
    "listing_type": "room_shared|room_private|basement_suite|studio|1br|2br|3br|house|laneway|other",
    "available_date": "YYYY-MM-DD or null",
    "num_bedrooms": null or integer,
    "num_roommates": null or integer (number of existing roommates),
    "utilities_included": null or true/false,
    "furnished": null or true/false,
    "pets_allowed": null or true/false,
    "parking_included": null or true/false,
    "laundry_in_unit": null or true/false,
    "description": "clean summary of the listing (2-3 sentences)",
    "gender_preference": "female_only|male_only|couples_welcome|no_couples|null",
    "lease_type": "month_to_month|fixed_term|null",
    "min_lease_months": null or integer (minimum lease length in months),
    "bathroom_type": "private|shared|null",
    "laundry_type": "in_unit|in_building|null",
    "transit_proximity": "near_skytrain|near_bus|good_transit|null",
    "transit_description": "free-text transit details or null (e.g. '5 min to Commercial-Broadway SkyTrain')",
    "furniture_level": "fully_furnished|partially_furnished|unfurnished|null"
}}

Important:
- If a field cannot be determined from the post, use null
- Price should be monthly rent only. If weekly, multiply by 4. If daily, multiply by 30.
- For listing_type, choose the closest match
- Only set is_offering=true for posts that are renting OUT a place, not looking FOR a place
- For gender_preference, look for mentions like "female only", "no couples", etc.
- For lease_type, look for "month to month", "minimum X months", etc.
- For bathroom_type, look for "private bath", "ensuite", "shared bathroom", etc.
- For transit_proximity, look for mentions of SkyTrain stations, bus routes, or transit descriptions
- Return ONLY the JSON object, no other text
"""


class FacebookExtractor:
    """Extract structured Listing data from Facebook posts using Claude API.

    Args:
        api_key: Anthropic API key. If None, reads from ANTHROPIC_API_KEY env var.
        model: Claude model to use for extraction.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
    ):
        self.model = model
        self._client = None
        self._api_key = api_key

    def _get_client(self):
        """Lazy-init the Anthropic client."""
        if self._client is None:
            import anthropic
            if self._api_key:
                self._client = anthropic.Anthropic(api_key=self._api_key)
            else:
                self._client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY env var
        return self._client

    def extract_from_post(self, post_text: str, post_url: str = "") -> Optional[Listing]:
        """Extract a structured Listing from a single Facebook post.

        Args:
            post_text: Raw text content of the Facebook post.
            post_url: URL of the post (if available).

        Returns:
            Listing object if extraction succeeds and post is an offering,
            None if the post is someone seeking housing or extraction fails.
        """
        if not post_text or len(post_text.strip()) < 20:
            logger.debug("Post text too short, skipping.")
            return None

        try:
            client = self._get_client()
            response = client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": EXTRACTION_PROMPT.format(post_text=post_text),
                    }
                ],
            )

            # Parse the JSON response
            response_text = response.content[0].text.strip()

            # Handle potential markdown wrapping
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])

            data = json.loads(response_text)

            # Skip posts that are seeking accommodation, not offering
            if not data.get("is_offering", False):
                logger.debug("Post is seeking, not offering. Skipping.")
                return None

            return self._data_to_listing(data, post_url)

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return None

    def extract_from_posts(
        self,
        posts: list,
        max_posts: Optional[int] = None,
    ) -> list[Listing]:
        """Extract Listings from a batch of RawFacebookPost objects.

        Args:
            posts: List of RawFacebookPost objects from the scraper.
            max_posts: Maximum posts to process (for API cost control).

        Returns:
            List of Listing objects (only offerings, not seekers).
        """
        listings = []
        to_process = posts[:max_posts] if max_posts else posts

        for i, post in enumerate(to_process):
            logger.info(f"Processing post {i+1}/{len(to_process)}")

            # Handle both RawFacebookPost objects and plain strings
            if hasattr(post, "text"):
                text = post.text
                url = getattr(post, "post_url", "")
            else:
                text = str(post)
                url = ""

            listing = self.extract_from_post(text, url)
            if listing:
                listings.append(listing)
                logger.info(f"  → Extracted: {listing.summary()}")
            else:
                logger.info(f"  → Skipped (seeking or extraction failed)")

        return listings

    def extract_from_dump(self, dump_text: str) -> list[Listing]:
        """Extract Listings from a manual text dump.

        Users can copy/paste multiple Facebook posts separated by "---".
        This is the fallback method when browser automation isn't feasible.

        Args:
            dump_text: Multiple posts separated by "---" delimiters.

        Returns:
            List of Listing objects.
        """
        posts = [p.strip() for p in dump_text.split("---") if p.strip()]
        logger.info(f"Processing {len(posts)} posts from manual dump")
        return self.extract_from_posts(posts)

    @staticmethod
    def _data_to_listing(data: dict, post_url: str = "") -> Listing:
        """Convert extracted JSON data to a Listing object."""
        # Map listing_type string to enum
        type_map = {
            "room_shared": ListingType.ROOM_SHARED,
            "room_private": ListingType.ROOM_PRIVATE,
            "basement_suite": ListingType.BASEMENT_SUITE,
            "studio": ListingType.STUDIO,
            "1br": ListingType.ONE_BEDROOM,
            "2br": ListingType.TWO_BEDROOM,
            "3br": ListingType.THREE_BEDROOM,
            "house": ListingType.HOUSE,
            "laneway": ListingType.LANEWAY,
            "other": ListingType.OTHER,
        }

        listing_type = type_map.get(
            data.get("listing_type", "other"),
            ListingType.OTHER,
        )

        # Parse available_date if provided
        available_date = None
        if data.get("available_date"):
            try:
                available_date = datetime.fromisoformat(data["available_date"])
            except (ValueError, TypeError):
                pass

        listing = Listing(
            source=ListingSource.FACEBOOK,
            url=post_url,
            title=data.get("title", "Facebook listing"),
            price=data.get("price"),
            location=data.get("location", ""),
            description=data.get("description", ""),
            available_date=available_date,
            listing_type=listing_type,
            num_bedrooms=data.get("num_bedrooms"),
            num_roommates=data.get("num_roommates"),
            utilities_included=data.get("utilities_included"),
            furnished=data.get("furnished"),
            pets_allowed=data.get("pets_allowed"),
            parking_included=data.get("parking_included"),
            laundry_in_unit=data.get("laundry_in_unit"),
            gender_preference=data.get("gender_preference"),
            lease_type=data.get("lease_type"),
            min_lease_months=data.get("min_lease_months"),
            bathroom_type=data.get("bathroom_type"),
            laundry_type=data.get("laundry_type"),
            transit_proximity=data.get("transit_proximity"),
            transit_description=data.get("transit_description"),
            furniture_level=data.get("furniture_level"),
        )

        # Normalize neighbourhood from location + description
        from rental_scraper.description_parser import DescriptionParser
        listing.neighbourhood = DescriptionParser.normalize_neighbourhood(
            f"{listing.location} {listing.title} {listing.description}"
        )

        return listing
