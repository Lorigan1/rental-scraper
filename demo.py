#!/usr/bin/env python3
"""Demo script for Craigslist + Kijiji scrapers.

Tests both scrapers with 10 listings each and displays results.
Run: python demo.py
"""

import asyncio
import json
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("demo")


def print_listing_table(listings, source_name: str):
    """Print listings in a readable table format."""
    print(f"\n{'='*80}")
    print(f"  {source_name} Results: {len(listings)} listings")
    print(f"{'='*80}")

    if not listings:
        print("  No listings found.")
        return

    for i, listing in enumerate(listings, 1):
        price = f"${listing.price}/mo" if listing.price else "N/A"
        location = listing.location[:25] if listing.location else "N/A"
        title = listing.title[:50] if listing.title else "No title"
        print(f"  {i:>2}. {price:<12} {location:<27} {title}")

    # Summary stats
    prices = [l.price for l in listings if l.price]
    if prices:
        avg = sum(prices) / len(prices)
        print(f"\n  Price range: ${min(prices)} - ${max(prices)}/mo")
        print(f"  Average:     ${avg:.0f}/mo")
        print(f"  Median:      ${sorted(prices)[len(prices)//2]}/mo")
        print(f"  With price:  {len(prices)}/{len(listings)} listings")


async def demo_craigslist():
    """Demo Craigslist scraper."""
    from rental_scraper.scrapers.craigslist import CraigslistScraper

    logger.info("Starting Craigslist scraper demo...")

    async with CraigslistScraper(headless=True) as scraper:
        listings = await scraper.scrape(
            max_listings=10,
            min_price=500,
            max_price=2000,
        )

    print_listing_table(listings, "Craigslist Vancouver")
    return listings


async def demo_kijiji():
    """Demo Kijiji scraper."""
    from rental_scraper.scrapers.kijiji import KijijiScraper

    logger.info("Starting Kijiji scraper demo...")

    async with KijijiScraper(headless=True) as scraper:
        listings = await scraper.scrape(
            max_listings=10,
            min_price=500,
            max_price=2000,
        )

    print_listing_table(listings, "Kijiji Vancouver")
    return listings


async def main():
    print("\n" + "="*80)
    print("  Vancouver Rental Scraper - Demo")
    print("  Scraping Craigslist + Kijiji for rooms & shares")
    print("="*80)

    all_listings = []

    # Run both scrapers
    try:
        cl_listings = await demo_craigslist()
        all_listings.extend(cl_listings)
    except Exception as e:
        logger.error(f"Craigslist scraper failed: {e}")

    try:
        kj_listings = await demo_kijiji()
        all_listings.extend(kj_listings)
    except Exception as e:
        logger.error(f"Kijiji scraper failed: {e}")

    # Combined summary
    print(f"\n{'='*80}")
    print(f"  Combined Results")
    print(f"{'='*80}")
    print(f"  Total listings: {len(all_listings)}")

    prices = [l.price for l in all_listings if l.price]
    if prices:
        print(f"  Price range:   ${min(prices)} - ${max(prices)}/mo")
        print(f"  Average:       ${sum(prices)/len(prices):.0f}/mo")

    # Export sample as JSON
    if all_listings:
        sample = all_listings[0].to_dict()
        print(f"\n  Sample listing (JSON):")
        print(f"  {json.dumps(sample, indent=2, default=str)[:500]}")

    print()


if __name__ == "__main__":
    asyncio.run(main())
