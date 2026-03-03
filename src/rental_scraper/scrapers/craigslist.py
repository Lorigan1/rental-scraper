"""Craigslist Vancouver scraper for rooms & shares."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode

from rental_scraper.models import Listing, ListingSource, ListingType
from rental_scraper.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

# Craigslist rooms & shares search for Vancouver
BASE_URL = "https://vancouver.craigslist.org/search/roo"


class CraigslistScraper(BaseScraper):
    """Scrape rental listings from Craigslist Vancouver rooms & shares.

    Extracts listing cards from search results, then optionally visits
    individual listing pages for full details (description, images, amenities).

    Usage:
        async with CraigslistScraper() as scraper:
            listings = await scraper.scrape(max_listings=20, min_price=500, max_price=1500)
    """

    def __init__(self, headless: bool = True):
        super().__init__(headless=headless)

    def _build_search_url(
        self,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        offset: int = 0,
    ) -> str:
        """Build Craigslist search URL with optional price filters."""
        params = {}
        if min_price is not None:
            params["min_price"] = min_price
        if max_price is not None:
            params["max_price"] = max_price
        if offset > 0:
            params["s"] = offset

        if params:
            return f"{BASE_URL}?{urlencode(params)}"
        return BASE_URL

    async def scrape(
        self,
        max_listings: int = 50,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        fetch_details: bool = False,
    ) -> list[Listing]:
        """Scrape Craigslist search results.

        Args:
            max_listings: Maximum number of listings to return.
            min_price: Minimum monthly rent filter.
            max_price: Maximum monthly rent filter.
            fetch_details: If True, visit each listing page for full details.

        Returns:
            List of Listing objects.
        """
        page = await self.new_page()
        listings: list[Listing] = []
        offset = 0

        try:
            while len(listings) < max_listings:
                url = self._build_search_url(min_price, max_price, offset)
                logger.info(f"Fetching Craigslist page: {url}")
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await self.human_delay(1.5, 3.0)

                # Extract listing cards from search results
                batch = await self._extract_search_results(page)
                if not batch:
                    logger.info("No more results found, stopping.")
                    break

                for listing in batch:
                    if len(listings) >= max_listings:
                        break
                    listings.append(listing)

                logger.info(f"Extracted {len(batch)} listings (total: {len(listings)})")

                # Craigslist paginates in groups of 120
                offset += 120
                if len(batch) < 10:
                    break  # Likely last page

            # Optionally fetch full details for each listing
            if fetch_details:
                for i, listing in enumerate(listings):
                    if listing.url:
                        logger.info(f"Fetching details {i+1}/{len(listings)}: {listing.url}")
                        await self._fetch_listing_details(page, listing)
                        await self.human_delay(2.0, 4.0)

        except Exception as e:
            logger.error(f"Error scraping Craigslist: {e}")

        finally:
            await page.close()

        return listings

    async def _extract_search_results(self, page) -> list[Listing]:
        """Extract listings from a Craigslist search results page."""
        listings = []

        # Craigslist uses .cl-search-result or .result-row for listing cards
        # Try the newer gallery/list layout first, then fall back
        cards = await page.query_selector_all("li.cl-search-result, .result-row")
        if not cards:
            # Try alternate selector for gallery view
            cards = await page.query_selector_all(".cl-search-result")

        for card in cards:
            try:
                listing = await self._parse_search_card(card)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.debug(f"Failed to parse card: {e}")
                continue

        return listings

    async def _parse_search_card(self, card) -> Optional[Listing]:
        """Parse a single search result card into a Listing."""
        listing = Listing(source=ListingSource.CRAIGSLIST)

        # Title and URL - try multiple selector patterns
        title_el = await card.query_selector("a.titlestring, a.result-title, .title-blob a")
        if title_el:
            listing.title = self.clean_text(await title_el.inner_text())
            listing.url = await title_el.get_attribute("href") or ""
            # Ensure absolute URL
            if listing.url and not listing.url.startswith("http"):
                listing.url = f"https://vancouver.craigslist.org{listing.url}"

        # Price
        price_el = await card.query_selector(".priceinfo, .result-price, .price")
        if price_el:
            price_text = await price_el.inner_text()
            listing.price = self.extract_price(price_text)

        # Location / neighborhood
        hood_el = await card.query_selector(".meta .subreddit, .result-hood, .neighborhoods")
        if hood_el:
            listing.location = self.clean_text(await hood_el.inner_text())
            # Remove parentheses that Craigslist wraps neighborhoods in
            listing.location = listing.location.strip("() ")

        # Posted date
        date_el = await card.query_selector("time, .date, .result-date")
        if date_el:
            datetime_attr = await date_el.get_attribute("datetime")
            if datetime_attr:
                try:
                    listing.posted_date = datetime.fromisoformat(datetime_attr.replace("Z", "+00:00"))
                except ValueError:
                    date_text = await date_el.inner_text()
                    listing.posted_date = self.parse_relative_date(date_text)
            else:
                date_text = await date_el.inner_text()
                listing.posted_date = self.parse_relative_date(date_text)

        # Craigslist rooms section defaults to room_private
        listing.listing_type = ListingType.ROOM_PRIVATE

        # Use URL as stable ID
        if listing.url:
            # Extract Craigslist post ID from URL
            id_match = re.search(r'/(\d+)\.html', listing.url)
            if id_match:
                listing.id = f"cl-{id_match.group(1)}"

        return listing if listing.title else None

    async def _fetch_listing_details(self, page, listing: Listing):
        """Visit a listing page to extract full details."""
        try:
            await page.goto(listing.url, wait_until="domcontentloaded", timeout=30000)
            await self.human_delay(1.0, 2.0)

            # Description
            body_el = await page.query_selector("#postingbody")
            if body_el:
                text = await body_el.inner_text()
                # Remove the "QR Code Link to This Post" boilerplate
                text = re.sub(r'QR Code Link.*', '', text, flags=re.IGNORECASE)
                listing.description = self.clean_text(text)

            # Images
            images = await page.query_selector_all("#thumbs a, .gallery img, .swipe img")
            for img in images:
                src = await img.get_attribute("href") or await img.get_attribute("src") or ""
                if src and src.startswith("http"):
                    listing.image_urls.append(src)

            # Map coordinates
            map_el = await page.query_selector("#map")
            if map_el:
                lat = await map_el.get_attribute("data-latitude")
                lon = await map_el.get_attribute("data-longitude")
                if lat and lon:
                    try:
                        listing.latitude = float(lat)
                        listing.longitude = float(lon)
                    except ValueError:
                        pass

            # Parse amenities from attribute groups
            attrs = await page.query_selector_all(".mapAndAttrs .attrgroup span")
            attr_texts = []
            for attr in attrs:
                attr_texts.append((await attr.inner_text()).lower())

            attr_blob = " ".join(attr_texts)

            if "furnished" in attr_blob:
                listing.furnished = True
            if "cats" in attr_blob or "dogs" in attr_blob or "pets" in attr_blob:
                listing.pets_allowed = True
            if "laundry in unit" in attr_blob or "w/d in unit" in attr_blob:
                listing.laundry_in_unit = True
            if "parking" in attr_blob or "carport" in attr_blob or "garage" in attr_blob:
                listing.parking_included = True

            # Try to extract sqft
            for text in attr_texts:
                sqft_match = re.search(r'(\d+)\s*ft', text)
                if sqft_match:
                    listing.square_feet = int(sqft_match.group(1))

            # Classify listing type from description
            self._classify_listing_type(listing)

        except Exception as e:
            logger.warning(f"Failed to fetch details for {listing.url}: {e}")

    @staticmethod
    def _classify_listing_type(listing: Listing):
        """Infer listing type from title and description text."""
        text = f"{listing.title} {listing.description}".lower()

        if any(w in text for w in ["basement suite", "basement apt"]):
            listing.listing_type = ListingType.BASEMENT_SUITE
        elif any(w in text for w in ["studio", "bachelor"]):
            listing.listing_type = ListingType.STUDIO
        elif any(w in text for w in ["laneway", "lane way", "coach house"]):
            listing.listing_type = ListingType.LANEWAY
        elif any(w in text for w in ["shared room", "share room", "shared bedroom"]):
            listing.listing_type = ListingType.ROOM_SHARED
        elif any(w in text for w in ["private room", "room in", "room for rent"]):
            listing.listing_type = ListingType.ROOM_PRIVATE
        elif "1 br" in text or "1 bed" in text or "one bed" in text:
            listing.listing_type = ListingType.ONE_BEDROOM
        elif "2 br" in text or "2 bed" in text or "two bed" in text:
            listing.listing_type = ListingType.TWO_BEDROOM
