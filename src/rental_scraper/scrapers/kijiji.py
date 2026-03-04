"""Kijiji Vancouver scraper for room rentals."""

from __future__ import annotations

import logging
import re
from typing import Optional
from urllib.parse import urlencode

from rental_scraper.models import Listing, ListingSource, ListingType
from rental_scraper.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

# Kijiji room rentals in Greater Vancouver
BASE_URL = "https://www.kijiji.ca/b-room-rental-roommate/vancouver/c36l1700287"


class KijijiScraper(BaseScraper):
    """Scrape rental listings from Kijiji Vancouver room rentals.

    Uses data-testid attributes for selector stability. Kijiji's React-based
    frontend uses these consistently for testing hooks.

    Usage:
        async with KijijiScraper() as scraper:
            listings = await scraper.scrape(max_listings=20, min_price=500, max_price=1500)
    """

    def __init__(self, headless: bool = True):
        super().__init__(headless=headless)

    def _build_search_url(
        self,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        page_num: int = 1,
    ) -> str:
        """Build Kijiji search URL with price filters."""
        url = BASE_URL

        # Kijiji uses path-based price filtering
        price_parts = []
        if min_price is not None:
            price_parts.append(f"price__{min_price}")
        if max_price is not None:
            price_parts.append(f"{max_price if not price_parts else ''}")

        params = {}
        if min_price is not None or max_price is not None:
            params["price-type"] = "FIXED"
            if min_price is not None:
                params["ll-price"] = min_price
            if max_price is not None:
                params["ul-price"] = max_price

        if page_num > 1:
            params["page"] = page_num

        if params:
            return f"{url}?{urlencode(params)}"
        return url

    async def scrape(
        self,
        max_listings: int = 50,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        fetch_details: bool = False,
    ) -> list[Listing]:
        """Scrape Kijiji search results.

        Args:
            max_listings: Maximum listings to return.
            min_price: Minimum monthly rent filter.
            max_price: Maximum monthly rent filter.
            fetch_details: If True, visit each listing for full details.

        Returns:
            List of Listing objects.
        """
        page = await self.new_page()
        listings: list[Listing] = []
        page_num = 1

        try:
            while len(listings) < max_listings:
                url = self._build_search_url(min_price, max_price, page_num)
                logger.info(f"Fetching Kijiji page {page_num}: {url}")

                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await self.human_delay(2.0, 4.0)

                # Wait for listing cards to render (React app)
                try:
                    await page.wait_for_selector(
                        '[data-testid="listing-card"], [data-testid="search-listing-card"], .search-item',
                        timeout=10000,
                    )
                except Exception:
                    logger.info("No listing cards found, page may be empty.")
                    break

                batch = await self._extract_search_results(page)
                if not batch:
                    logger.info("No more results, stopping.")
                    break

                for listing in batch:
                    if len(listings) >= max_listings:
                        break
                    listings.append(listing)

                logger.info(f"Extracted {len(batch)} listings (total: {len(listings)})")

                page_num += 1
                if len(batch) < 10:
                    break

            if fetch_details:
                for i, listing in enumerate(listings):
                    if listing.url:
                        logger.info(f"Fetching details {i+1}/{len(listings)}: {listing.url}")
                        await self._fetch_listing_details(page, listing)
                        await self.human_delay(2.0, 4.0)

            # Enrich all listings with description parsing
            for listing in listings:
                self.enrich_from_description(listing)

        except Exception as e:
            logger.error(f"Error scraping Kijiji: {e}")

        finally:
            await page.close()

        return listings

    async def _extract_search_results(self, page) -> list[Listing]:
        """Extract listings from Kijiji search results page."""
        listings = []

        # Kijiji uses data-testid for listing cards
        cards = await page.query_selector_all(
            '[data-testid="listing-card"], [data-testid="search-listing-card"], '
            '.search-item, [data-listing-id]'
        )

        for card in cards:
            try:
                listing = await self._parse_search_card(card)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.debug(f"Failed to parse Kijiji card: {e}")
                continue

        return listings

    async def _parse_search_card(self, card) -> Optional[Listing]:
        """Parse a single Kijiji search result card."""
        listing = Listing(source=ListingSource.KIJIJI)

        # Title and URL
        title_el = await card.query_selector(
            '[data-testid="listing-title"], [data-testid="listing-link"], '
            'a.title, .title a, h3 a'
        )
        if title_el:
            listing.title = self.clean_text(await title_el.inner_text())
            href = await title_el.get_attribute("href") or ""
            if href:
                if not href.startswith("http"):
                    href = f"https://www.kijiji.ca{href}"
                listing.url = href

        # Price
        price_el = await card.query_selector(
            '[data-testid="listing-price"], .price, [class*="price"]'
        )
        if price_el:
            price_text = await price_el.inner_text()
            listing.price = self.extract_price(price_text)

        # Location
        loc_el = await card.query_selector(
            '[data-testid="listing-location"], .location, [class*="location"]'
        )
        if loc_el:
            listing.location = self.clean_text(await loc_el.inner_text())

        # Date
        date_el = await card.query_selector(
            '[data-testid="listing-date"], .date-posted, [class*="date"]'
        )
        if date_el:
            date_text = self.clean_text(await date_el.inner_text())
            listing.posted_date = self.parse_relative_date(date_text)

        # Description snippet
        desc_el = await card.query_selector(
            '[data-testid="listing-description"], .description, [class*="description"]'
        )
        if desc_el:
            listing.description = self.clean_text(await desc_el.inner_text())

        # Extract Kijiji listing ID from URL
        if listing.url:
            id_match = re.search(r'/(\d+)$', listing.url)
            if id_match:
                listing.id = f"kj-{id_match.group(1)}"

        # Image
        img_el = await card.query_selector("img[src], picture img")
        if img_el:
            src = await img_el.get_attribute("src") or ""
            if src and src.startswith("http"):
                listing.image_urls.append(src)

        listing.listing_type = ListingType.ROOM_PRIVATE
        self._classify_listing_type(listing)

        return listing if listing.title else None

    async def _fetch_listing_details(self, page, listing: Listing):
        """Visit individual listing page for full details."""
        try:
            await page.goto(listing.url, wait_until="domcontentloaded", timeout=30000)
            await self.human_delay(1.0, 2.0)

            # Full description
            desc_el = await page.query_selector(
                '[data-testid="listing-description"], #vip-body, '
                '[class*="descriptionContainer"], .description'
            )
            if desc_el:
                listing.description = self.clean_text(await desc_el.inner_text())

            # All images
            images = await page.query_selector_all(
                '[data-testid="gallery-image"] img, .gallery img, '
                '[class*="imageGallery"] img'
            )
            listing.image_urls = []
            for img in images:
                src = await img.get_attribute("src") or ""
                if src and src.startswith("http") and "placeholder" not in src:
                    listing.image_urls.append(src)

            # Attributes table
            attr_rows = await page.query_selector_all(
                '[data-testid="attribute-row"], .attributeList li, '
                '[class*="attributeGroupContainer"] li'
            )
            for row in attr_rows:
                text = (await row.inner_text()).lower()
                if "furnished" in text and ("yes" in text or "furnished" in text):
                    listing.furnished = True
                elif "pet" in text and "yes" in text:
                    listing.pets_allowed = True
                elif "parking" in text and "yes" in text:
                    listing.parking_included = True
                elif "laundry" in text and ("unit" in text or "suite" in text):
                    listing.laundry_in_unit = True
                elif "utilities" in text and ("included" in text or "yes" in text):
                    listing.utilities_included = True

                # Square footage
                sqft_match = re.search(r'(\d+)\s*(?:sq|ft|sqft)', text)
                if sqft_match:
                    listing.square_feet = int(sqft_match.group(1))

            # Map coordinates from page
            map_el = await page.query_selector('[data-testid="map"], #MapContainer, .mapContainer')
            if map_el:
                lat = await map_el.get_attribute("data-lat") or await map_el.get_attribute("data-latitude")
                lon = await map_el.get_attribute("data-lng") or await map_el.get_attribute("data-longitude")
                if lat and lon:
                    try:
                        listing.latitude = float(lat)
                        listing.longitude = float(lon)
                    except ValueError:
                        pass

        except Exception as e:
            logger.warning(f"Failed to fetch Kijiji details for {listing.url}: {e}")

    @staticmethod
    def _classify_listing_type(listing: Listing):
        """Infer listing type from title and description."""
        text = f"{listing.title} {listing.description}".lower()

        if any(w in text for w in ["basement suite", "basement apt"]):
            listing.listing_type = ListingType.BASEMENT_SUITE
        elif any(w in text for w in ["studio", "bachelor"]):
            listing.listing_type = ListingType.STUDIO
        elif any(w in text for w in ["laneway", "lane way", "coach house"]):
            listing.listing_type = ListingType.LANEWAY
        elif any(w in text for w in ["shared room", "share room"]):
            listing.listing_type = ListingType.ROOM_SHARED
        elif any(w in text for w in ["private room", "room in", "room for rent"]):
            listing.listing_type = ListingType.ROOM_PRIVATE
