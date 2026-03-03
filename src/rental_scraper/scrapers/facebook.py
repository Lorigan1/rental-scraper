"""Facebook Groups scraper using browser attachment via CDP.

This scraper connects to an existing Chrome session where the user is
already logged into Facebook. It does NOT create accounts or automate login.

Architecture:
    1. User launches Chrome with remote debugging enabled
    2. User manually logs into Facebook and navigates to a housing group
    3. This scraper connects to that session via CDP (Chrome DevTools Protocol)
    4. Scrolls through the feed and extracts post content
    5. Raw post text is returned for LLM processing (see facebook_extractor.py)

This is the "browser attachment" pattern - it uses the user's real session,
avoiding bot detection and ToS issues with fake accounts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from playwright.async_api import async_playwright, Browser, Page

from rental_scraper.models import Listing, ListingSource

logger = logging.getLogger(__name__)

# Default CDP endpoint for Chrome with remote debugging
DEFAULT_CDP_URL = "http://localhost:9222"


@dataclass
class RawFacebookPost:
    """Raw post data extracted from Facebook before LLM processing."""
    text: str = ""
    author: str = ""
    timestamp: str = ""
    image_urls: list[str] = field(default_factory=list)
    post_url: str = ""
    extracted_at: datetime = field(default_factory=datetime.now)


class FacebookGroupsScraper:
    """Scrape Facebook housing group posts via browser attachment.

    Connects to an existing Chrome browser session using CDP. The user
    must already be logged into Facebook and viewing a housing group.

    Setup:
        1. Launch Chrome with remote debugging:
           chrome --remote-debugging-port=9222 --user-data-dir="/tmp/chrome-debug"

        2. Log into Facebook manually in that Chrome window

        3. Navigate to a housing group (e.g., Vancouver Housing, Rooms for Rent)

        4. Run this scraper - it connects to your existing session

    Usage:
        scraper = FacebookGroupsScraper()
        async with scraper:
            posts = await scraper.scrape_current_page(max_posts=20)
            # Then process with FacebookExtractor for structured data
    """

    def __init__(self, cdp_url: str = DEFAULT_CDP_URL):
        self.cdp_url = cdp_url
        self._playwright = None
        self._browser: Optional[Browser] = None

    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        try:
            self._browser = await self._playwright.chromium.connect_over_cdp(self.cdp_url)
            logger.info(f"Connected to Chrome via CDP at {self.cdp_url}")
        except Exception as e:
            logger.error(
                f"Failed to connect to Chrome at {self.cdp_url}. "
                f"Make sure Chrome is running with --remote-debugging-port=9222\n"
                f"Error: {e}"
            )
            raise
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Don't close the browser - it's the user's session!
        # Just disconnect playwright
        if self._playwright:
            await self._playwright.stop()

    async def scrape_current_page(
        self,
        max_posts: int = 30,
        max_scrolls: int = 15,
    ) -> list[RawFacebookPost]:
        """Scrape posts from the currently visible Facebook group page.

        The user should already be on a Facebook group page. This method
        scrolls through the feed and extracts post content.

        Args:
            max_posts: Maximum posts to extract.
            max_scrolls: Maximum scroll iterations (prevents infinite scrolling).

        Returns:
            List of RawFacebookPost objects with text and metadata.
        """
        if not self._browser:
            raise RuntimeError("Not connected to Chrome. Use 'async with' context manager.")

        # Get the first context and page (user's active tab)
        contexts = self._browser.contexts
        if not contexts:
            raise RuntimeError("No browser contexts found. Is Chrome open with a page?")

        pages = contexts[0].pages
        if not pages:
            raise RuntimeError("No pages found. Navigate to a Facebook group first.")

        # Use the last active page
        page = pages[-1]

        # Verify we're on Facebook
        current_url = page.url
        if "facebook.com" not in current_url:
            logger.warning(
                f"Current page ({current_url}) doesn't appear to be Facebook. "
                f"Navigate to a Facebook housing group first."
            )

        logger.info(f"Scraping Facebook page: {current_url}")

        posts: list[RawFacebookPost] = []
        seen_texts: set[str] = set()

        import asyncio

        for scroll_num in range(max_scrolls):
            if len(posts) >= max_posts:
                break

            # Extract posts currently visible
            new_posts = await self._extract_visible_posts(page, seen_texts)
            posts.extend(new_posts)

            logger.info(
                f"Scroll {scroll_num + 1}/{max_scrolls}: "
                f"found {len(new_posts)} new posts (total: {len(posts)})"
            )

            if len(posts) >= max_posts:
                break

            # Scroll down with human-like behavior
            await page.evaluate("window.scrollBy(0, window.innerHeight * 0.8)")
            # Random delay between 2-4 seconds to look human
            import random
            delay = random.uniform(2.0, 4.0)
            await asyncio.sleep(delay)

        return posts[:max_posts]

    async def _extract_visible_posts(
        self,
        page: Page,
        seen_texts: set[str],
    ) -> list[RawFacebookPost]:
        """Extract post data from currently visible Facebook posts."""
        new_posts = []

        # Facebook posts use role="article" for feed items
        articles = await page.query_selector_all('[role="article"]')

        for article in articles:
            try:
                post = await self._parse_article(article)

                # Deduplicate by text content (first 100 chars)
                text_key = post.text[:100] if post.text else ""
                if text_key and text_key not in seen_texts:
                    seen_texts.add(text_key)
                    new_posts.append(post)

            except Exception as e:
                logger.debug(f"Failed to parse Facebook article: {e}")
                continue

        return new_posts

    async def _parse_article(self, article) -> RawFacebookPost:
        """Parse a single Facebook article element."""
        post = RawFacebookPost()

        # Extract all text content from the article
        try:
            post.text = await article.inner_text()
            # Clean up the text - remove excessive whitespace
            import re
            post.text = re.sub(r'\n{3,}', '\n\n', post.text).strip()
        except Exception:
            pass

        # Try to get author name (usually first strong/bold element or h2/h3)
        try:
            author_el = await article.query_selector(
                'h2 a strong, h3 a strong, [data-ad-preview="message"] strong, '
                'a[role="link"] strong'
            )
            if author_el:
                post.author = (await author_el.inner_text()).strip()
        except Exception:
            pass

        # Try to get timestamp
        try:
            time_el = await article.query_selector(
                'a[role="link"] span[aria-labelledby], '
                'abbr, [data-utime], a > span > span'
            )
            if time_el:
                post.timestamp = (await time_el.inner_text()).strip()
        except Exception:
            pass

        # Extract image URLs
        try:
            images = await article.query_selector_all("img[src]")
            for img in images:
                src = await img.get_attribute("src") or ""
                # Filter out tiny icons and emoji images
                if src and "scontent" in src and "emoji" not in src:
                    width = await img.get_attribute("width")
                    if width and int(width) > 100:
                        post.image_urls.append(src)
        except Exception:
            pass

        # Try to get post permalink
        try:
            links = await article.query_selector_all("a[href*='/posts/'], a[href*='/permalink/']")
            for link in links:
                href = await link.get_attribute("href") or ""
                if "/posts/" in href or "/permalink/" in href:
                    post.post_url = href
                    break
        except Exception:
            pass

        return post

    async def get_group_info(self) -> dict:
        """Get info about the currently viewed Facebook group."""
        if not self._browser:
            raise RuntimeError("Not connected.")

        page = self._browser.contexts[0].pages[-1]
        return {
            "url": page.url,
            "title": await page.title(),
        }
