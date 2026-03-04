"""Craigslist Vancouver scraper for rooms & shares."""

from __future__ import annotations

import json
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

    Uses embedded JSON-LD data (ld_searchpage_results) as primary extraction
    method, falling back to DOM selectors if JSON is unavailable.

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

                # Try embedded JSON first (most reliable), fall back to DOM
                batch = await self._extract_from_json(page)
                if not batch:
                    logger.info("JSON extraction failed, trying DOM selectors...")
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

    # ── JSON-LD extraction (primary method) ──────────────────────

    async def _extract_from_json(self, page) -> list[Listing]:
        """Extract listings from embedded JSON-LD script tag.

        Craigslist embeds all search result data in a <script> tag with
        id="ld_searchpage_results" as JSON-LD. This is far more reliable
        than parsing DOM elements.
        """
        listings = []
        try:
            json_el = await page.query_selector("script#ld_searchpage_results")
            if not json_el:
                logger.debug("No ld_searchpage_results script tag found")
                return []

            raw = await json_el.inner_text()
            data = json.loads(raw)

            # JSON-LD wraps listings in an itemListElement array
            items = []
            if isinstance(data, dict):
                items = data.get("itemListElement", [])
            elif isinstance(data, list):
                items = data

            for item in items:
                listing = self._parse_json_item(item)
                if listing:
                    listings.append(listing)

            logger.info(f"JSON extraction: {len(listings)} listings from embedded data")

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse embedded JSON: {e}")
        except Exception as e:
            logger.warning(f"JSON extraction error: {e}")

        return listings

    def _parse_json_item(self, item: dict) -> Optional[Listing]:
        """Parse a single JSON-LD item into a Listing."""
        try:
            listing = Listing(source=ListingSource.CRAIGSLIST)

            listing.title = item.get("name", "")
            listing.url = item.get("url", "")
            listing.description = item.get("description", "")

            # Price - can be nested in offers or directly present
            offers = item.get("offers", {})
            if isinstance(offers, dict):
                price_val = offers.get("price") or offers.get("priceCurrency")
                if price_val:
                    listing.price = self.extract_price(str(price_val))
            # Also try top-level price
            if not listing.price and item.get("price"):
                listing.price = self.extract_price(str(item["price"]))

            # Location
            address = item.get("address", {})
            if isinstance(address, dict):
                parts = []
                if address.get("addressLocality"):
                    parts.append(address["addressLocality"])
                if address.get("addressRegion"):
                    parts.append(address["addressRegion"])
                if parts:
                    listing.location = ", ".join(parts)

            # Geo coordinates
            geo = item.get("geo", {})
            if isinstance(geo, dict):
                try:
                    if geo.get("latitude"):
                        listing.latitude = float(geo["latitude"])
                    if geo.get("longitude"):
                        listing.longitude = float(geo["longitude"])
                except (ValueError, TypeError):
                    pass

            # Date
            date_str = item.get("datePosted") or item.get("datePublished")
            if date_str:
                try:
                    listing.posted_date = datetime.fromisoformat(
                        date_str.replace("Z", "+00:00")
                    )
                except ValueError:
                    pass

            # Images
            images = item.get("image", [])
            if isinstance(images, str):
                images = [images]
            listing.image_urls = [img for img in images if isinstance(img, str) and img.startswith("http")]

            # Post ID from URL
            if listing.url:
                id_match = re.search(r'/(\d+)\.html', listing.url)
                if id_match:
                    listing.id = f"cl-{id_match.group(1)}"

            # Default listing type for rooms section
            listing.listing_type = ListingType.ROOM_PRIVATE
            self._classify_listing_type(listing)

            return listing if listing.title else None

        except Exception as e:
            logger.debug(f"Failed to parse JSON item: {e}")
            return None

    # ── DOM extraction (fallback method) ─────────────────────────

    async def _extract_search_results(self, page) -> list[Listing]:
        """Extract listings from DOM elements (fallback if JSON unavailable)."""
        listings = []

        # Craigslist uses div.cl-search-result with data-pid for listing cards
        cards = await page.query_selector_all("div.cl-search-result, li.cl-search-result, .result-row")
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
        title_el = await card.query_selector(
            "a.titlestring, a.posting-title, a.result-title, .title-blob a, a.cl-app-anchor"
        )
        if title_el:
            listing.title = self.clean_text(await title_el.inner_text())
            listing.url = await title_el.get_attribute("href") or ""
            # Ensure absolute URL
            if listing.url and not listing.url.startswith("http"):
                listing.url = f"https://vancouver.craigslist.org{listing.url}"

        # Price - try multiple selectors
        price_el = await card.query_selector(
            ".priceinfo, .price, .result-price, .meta .price"
        )
        if price_el:
            price_text = await price_el.inner_text()
            listing.price = self.extract_price(price_text)

        # Location / neighborhood
        hood_el = await card.query_selector(
            ".meta .subreddit, .result-hood, .neighborhoods, .location, .meta .nearby"
        )
        if hood_el:
            listing.location = self.clean_text(await hood_el.inner_text())
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

        # Data-pid attribute as ID
        pid = await card.get_attribute("data-pid")
        if pid:
            listing.id = f"cl-{pid}"
        elif listing.url:
            id_match = re.search(r'/(\d+)\.html', listing.url)
            if id_match:
                listing.id = f"cl-{id_match.group(1)}"

        # Default listing type
        listing.listing_type = ListingType.ROOM_PRIVATE

        return listing if listing.title else None

    # ── Detail page extraction ───────────────────────────────────

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
