"""Integration tests for Kijiji scraper.

These tests hit the live Kijiji site and are marked @pytest.mark.slow.
Run with: pytest tests/test_kijiji.py -m slow -v
Skip with: pytest -m "not slow"
"""

import pytest

from rental_scraper.models import ListingSource, ListingType
from rental_scraper.scrapers.kijiji import KijijiScraper


@pytest.mark.slow
@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_kijiji_scrape_returns_listings():
    """Scrape a few listings and verify structure."""
    async with KijijiScraper(headless=True) as scraper:
        listings = await scraper.scrape(max_listings=5)

    assert len(listings) > 0, "Should find at least one listing"

    for listing in listings:
        assert listing.source == ListingSource.KIJIJI
        assert listing.title, "Listing should have a title"
        assert listing.url, "Listing should have a URL"
        assert "kijiji" in listing.url.lower()


@pytest.mark.slow
@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_kijiji_price_filter():
    """Test that price filters are applied."""
    async with KijijiScraper(headless=True) as scraper:
        listings = await scraper.scrape(
            max_listings=5,
            min_price=500,
            max_price=1500,
        )

    priced = [l for l in listings if l.price]
    for listing in priced:
        assert 400 <= listing.price <= 1600, (
            f"Price ${listing.price} should be roughly in filter range"
        )


@pytest.mark.slow
@pytest.mark.asyncio
@pytest.mark.timeout(90)
async def test_kijiji_with_details():
    """Test fetching full listing details."""
    async with KijijiScraper(headless=True) as scraper:
        listings = await scraper.scrape(
            max_listings=2,
            fetch_details=True,
        )

    # Just verify it doesn't crash - details depend on page structure


@pytest.mark.slow
@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_kijiji_listing_model_fields():
    """Verify listing objects have expected field types."""
    async with KijijiScraper(headless=True) as scraper:
        listings = await scraper.scrape(max_listings=3)

    if not listings:
        pytest.skip("No listings found - site may be unreachable")

    listing = listings[0]

    assert isinstance(listing.source, ListingSource)
    assert isinstance(listing.listing_type, ListingType)
    assert isinstance(listing.title, str)
    assert isinstance(listing.url, str)
    assert isinstance(listing.image_urls, list)

    d = listing.to_dict()
    assert isinstance(d, dict)
    assert d["source"] == "kijiji"

    s = listing.summary()
    assert isinstance(s, str)
    assert "kijiji" in s.lower()
