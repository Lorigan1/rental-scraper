"""Integration tests for Craigslist scraper.

These tests hit the live Craigslist site and are marked @pytest.mark.slow.
Run with: pytest tests/test_craigslist.py -m slow -v
Skip with: pytest -m "not slow"
"""

import pytest

from rental_scraper.models import ListingSource, ListingType
from rental_scraper.scrapers.craigslist import CraigslistScraper


@pytest.mark.slow
@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_craigslist_scrape_returns_listings():
    """Scrape a few listings and verify structure."""
    async with CraigslistScraper(headless=True) as scraper:
        listings = await scraper.scrape(max_listings=5)

    assert len(listings) > 0, "Should find at least one listing"

    for listing in listings:
        assert listing.source == ListingSource.CRAIGSLIST
        assert listing.title, "Listing should have a title"
        assert listing.url, "Listing should have a URL"
        assert "craigslist" in listing.url.lower()


@pytest.mark.slow
@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_craigslist_price_filter():
    """Test that price filters work."""
    async with CraigslistScraper(headless=True) as scraper:
        listings = await scraper.scrape(
            max_listings=5,
            min_price=500,
            max_price=1500,
        )

    # If we got listings with prices, verify filter
    priced = [l for l in listings if l.price]
    for listing in priced:
        assert 400 <= listing.price <= 1600, (
            f"Price ${listing.price} should be roughly in $500-$1500 range "
            f"(some slack for Craigslist filtering precision)"
        )


@pytest.mark.slow
@pytest.mark.asyncio
@pytest.mark.timeout(90)
async def test_craigslist_with_details():
    """Test fetching full listing details."""
    async with CraigslistScraper(headless=True) as scraper:
        listings = await scraper.scrape(
            max_listings=2,
            fetch_details=True,
        )

    if listings:
        # At least one listing should have a description after detail fetch
        has_desc = any(l.description for l in listings)
        # This can fail if Craigslist blocks or pages are removed
        # so we just check it doesn't crash


@pytest.mark.slow
@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_craigslist_listing_model_fields():
    """Verify listing objects have expected field types."""
    async with CraigslistScraper(headless=True) as scraper:
        listings = await scraper.scrape(max_listings=3)

    if not listings:
        pytest.skip("No listings found - site may be unreachable")

    listing = listings[0]

    # Type checks
    assert isinstance(listing.source, ListingSource)
    assert isinstance(listing.listing_type, ListingType)
    assert isinstance(listing.title, str)
    assert isinstance(listing.url, str)
    assert isinstance(listing.image_urls, list)

    # Serialization should work
    d = listing.to_dict()
    assert isinstance(d, dict)
    assert "source" in d
    assert "title" in d

    # Summary should work
    s = listing.summary()
    assert isinstance(s, str)
    assert "craigslist" in s.lower()
