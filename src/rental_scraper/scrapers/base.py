"""Base scraper with shared utilities for all rental sources."""

from __future__ import annotations

import asyncio
import logging
import random
import re
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from rental_scraper.models import Listing

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class for rental scrapers.

    Provides shared utilities: price parsing, date parsing, text cleaning,
    human-like delay, and Playwright browser lifecycle management.

    Usage as async context manager:
        async with CraigslistScraper() as scraper:
            listings = await scraper.scrape(max_listings=20)
    """

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def new_page(self) -> Page:
        """Create a new page in the browser context."""
        if not self._context:
            raise RuntimeError("Scraper not initialized. Use 'async with' context manager.")
        return await self._context.new_page()

    @abstractmethod
    async def scrape(self, max_listings: int = 50, **kwargs) -> list[Listing]:
        """Scrape listings from the source. Subclasses must implement."""
        ...

    # ── Utility methods ─────────────────────────────────────────────

    @staticmethod
    def extract_price(text: str) -> Optional[int]:
        """Extract monthly rent from text.

        Handles formats like: $1,200/month, $1200, 1,200/mo, $850
        Returns None if no valid price found or outside $100-$10,000 range.
        """
        if not text:
            return None

        # Remove common non-price noise
        cleaned = text.strip()

        # Match dollar amounts: $1,200 or 1200 with optional /mo /month
        patterns = [
            r'\$\s*([\d,]+)',        # $1,200 or $ 1200
            r'([\d,]+)\s*/\s*mo',    # 1200/mo
            r'([\d,]+)\s*/\s*month', # 1200/month
            r'([\d,]+)\s*(?:per|a)\s*month',  # 1200 per month
        ]

        for pattern in patterns:
            match = re.search(pattern, cleaned, re.IGNORECASE)
            if match:
                price_str = match.group(1).replace(",", "")
                try:
                    price = int(price_str)
                    # Sanity check: Vancouver room rents are $100-$10,000/mo
                    if 100 <= price <= 10_000:
                        return price
                except ValueError:
                    continue

        return None

    @staticmethod
    def parse_relative_date(text: str) -> Optional[datetime]:
        """Parse relative date strings into datetime.

        Handles: '2 hours ago', '3 days ago', 'an hour ago',
                 'a minute ago', 'just now', 'today', 'yesterday'
        """
        if not text:
            return None

        text = text.strip().lower()
        now = datetime.now()

        if text in ("just now", "moments ago"):
            return now

        if text == "today":
            return now.replace(hour=0, minute=0, second=0, microsecond=0)

        if text == "yesterday":
            return (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

        # Handle "a/an" as 1
        text = re.sub(r'\ban?\b', '1', text)

        # Match "N unit(s) ago"
        match = re.match(r'(\d+)\s+(second|minute|hour|day|week|month)s?\s+ago', text)
        if match:
            amount = int(match.group(1))
            unit = match.group(2)

            deltas = {
                "second": timedelta(seconds=amount),
                "minute": timedelta(minutes=amount),
                "hour": timedelta(hours=amount),
                "day": timedelta(days=amount),
                "week": timedelta(weeks=amount),
                "month": timedelta(days=amount * 30),  # Approximate
            }

            delta = deltas.get(unit)
            if delta:
                return now - delta

        # Try parsing absolute dates as fallback
        try:
            from dateutil import parser as dateutil_parser
            return dateutil_parser.parse(text)
        except (ValueError, TypeError):
            pass

        return None

    @staticmethod
    def clean_text(text: str) -> str:
        """Normalize whitespace and clean text content.

        Removes extra spaces, newlines, tabs. Strips leading/trailing whitespace.
        """
        if not text:
            return ""
        # Replace various whitespace chars with single space
        cleaned = re.sub(r'[\s\xa0]+', ' ', text)
        return cleaned.strip()

    @staticmethod
    async def human_delay(min_seconds: float = 1.0, max_seconds: float = 3.0):
        """Sleep for a random duration to mimic human browsing."""
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)

    @staticmethod
    async def safe_get_text(page: Page, selector: str) -> str:
        """Safely extract text from a selector, returning empty string on failure."""
        try:
            el = await page.query_selector(selector)
            if el:
                return (await el.inner_text()).strip()
        except Exception:
            pass
        return ""

    @staticmethod
    async def safe_get_attr(page: Page, selector: str, attr: str) -> str:
        """Safely get an attribute from a selector."""
        try:
            el = await page.query_selector(selector)
            if el:
                val = await el.get_attribute(attr)
                return val or ""
        except Exception:
            pass
        return ""

    @staticmethod
    def enrich_from_description(listing: Listing):
        """Parse listing description for enhanced structured fields.

        Extracts gender preference, lease type, bathroom, laundry,
        transit, furniture level, and normalized neighbourhood.
        Modifies the listing in-place.
        """
        from rental_scraper.description_parser import DescriptionParser

        parsed = DescriptionParser.parse_all(
            listing.description,
            listing.title,
            listing.location,
        )

        for field, value in parsed.items():
            if value is not None:
                setattr(listing, field, value)
