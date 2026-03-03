#!/usr/bin/env python3
"""Complete demo script for all 3 sources: Craigslist, Kijiji, and Facebook.

Interactive menu to choose which scrapers to run.
Run: python demo_complete.py
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
logger = logging.getLogger("demo_complete")


def print_listing_table(listings, source_name: str):
    """Print listings in a readable table format."""
    print(f"\n{'='*80}")
    print(f"  {source_name}: {len(listings)} listings")
    print(f"{'='*80}")

    if not listings:
        print("  No listings found.")
        return

    for i, listing in enumerate(listings, 1):
        price = f"${listing.price}/mo" if listing.price else "N/A"
        location = listing.location[:25] if listing.location else "N/A"
        title = listing.title[:50] if listing.title else "No title"
        ltype = listing.listing_type.value if listing.listing_type else "?"
        print(f"  {i:>2}. {price:<12} {ltype:<15} {location:<25} {title}")

    prices = [l.price for l in listings if l.price]
    if prices:
        avg = sum(prices) / len(prices)
        print(f"\n  Stats: ${min(prices)}-${max(prices)}/mo | avg ${avg:.0f} | {len(prices)} with price")


async def scrape_craigslist(max_listings=10):
    """Run Craigslist scraper."""
    from rental_scraper.scrapers.craigslist import CraigslistScraper
    async with CraigslistScraper(headless=True) as scraper:
        return await scraper.scrape(max_listings=max_listings)


async def scrape_kijiji(max_listings=10):
    """Run Kijiji scraper."""
    from rental_scraper.scrapers.kijiji import KijijiScraper
    async with KijijiScraper(headless=True) as scraper:
        return await scraper.scrape(max_listings=max_listings)


async def scrape_facebook(max_posts=10):
    """Run Facebook scraper (requires Chrome with remote debugging)."""
    from rental_scraper.scrapers.facebook import FacebookGroupsScraper
    from rental_scraper.facebook_extractor import FacebookExtractor

    print("\n  Facebook scraper requires Chrome with remote debugging.")
    print("  Launch Chrome with: chrome --remote-debugging-port=9222 --user-data-dir=\"/tmp/chrome-debug\"")
    print("  Then log into Facebook and navigate to a housing group.\n")

    try:
        async with FacebookGroupsScraper() as scraper:
            group_info = await scraper.get_group_info()
            print(f"  Connected! Current page: {group_info['title']}")

            posts = await scraper.scrape_current_page(max_posts=max_posts)
            print(f"  Extracted {len(posts)} raw posts")

            if posts:
                extractor = FacebookExtractor()
                listings = extractor.extract_from_posts(posts, max_posts=max_posts)
                return listings
            return []

    except Exception as e:
        logger.error(f"Facebook scraper failed: {e}")
        print(f"\n  Could not connect to Chrome. Error: {e}")
        print("  Falling back to manual dump mode...\n")
        return await facebook_manual_fallback()


async def facebook_manual_fallback():
    """Manual Facebook extraction - user pastes post text."""
    from rental_scraper.facebook_extractor import FacebookExtractor

    print("  Paste Facebook posts below, separated by '---' on its own line.")
    print("  When done, enter 'END' on its own line.\n")

    lines = []
    while True:
        try:
            line = input()
            if line.strip().upper() == "END":
                break
            lines.append(line)
        except EOFError:
            break

    dump_text = "\n".join(lines)
    if not dump_text.strip():
        print("  No posts entered.")
        return []

    extractor = FacebookExtractor()
    return extractor.extract_from_dump(dump_text)


async def main():
    print("\n" + "="*80)
    print("  Vancouver Rental Scraper - Complete Demo")
    print("="*80)
    print()
    print("  Which sources would you like to scrape?")
    print("  1. Craigslist only")
    print("  2. Kijiji only")
    print("  3. Craigslist + Kijiji")
    print("  4. Facebook Groups (requires Chrome setup)")
    print("  5. All sources")
    print("  6. Facebook manual dump (paste posts)")
    print()

    choice = input("  Enter choice (1-6): ").strip()

    all_listings = []

    if choice in ("1", "3", "5"):
        try:
            listings = await scrape_craigslist()
            print_listing_table(listings, "Craigslist")
            all_listings.extend(listings)
        except Exception as e:
            logger.error(f"Craigslist failed: {e}")

    if choice in ("2", "3", "5"):
        try:
            listings = await scrape_kijiji()
            print_listing_table(listings, "Kijiji")
            all_listings.extend(listings)
        except Exception as e:
            logger.error(f"Kijiji failed: {e}")

    if choice in ("4", "5"):
        try:
            listings = await scrape_facebook()
            print_listing_table(listings, "Facebook Groups")
            all_listings.extend(listings)
        except Exception as e:
            logger.error(f"Facebook failed: {e}")

    if choice == "6":
        try:
            listings = await facebook_manual_fallback()
            print_listing_table(listings, "Facebook (Manual)")
            all_listings.extend(listings)
        except Exception as e:
            logger.error(f"Facebook manual failed: {e}")

    # Combined results
    if len(all_listings) > 0:
        print(f"\n{'='*80}")
        print(f"  COMBINED RESULTS: {len(all_listings)} total listings")
        print(f"{'='*80}")

        prices = [l.price for l in all_listings if l.price]
        if prices:
            sorted_prices = sorted(prices)
            print(f"  Range:    ${min(prices)} - ${max(prices)}/mo")
            print(f"  Average:  ${sum(prices)/len(prices):.0f}/mo")
            print(f"  Median:   ${sorted_prices[len(sorted_prices)//2]}/mo")
            print(f"  25th pct: ${sorted_prices[len(sorted_prices)//4]}/mo")
            print(f"  75th pct: ${sorted_prices[3*len(sorted_prices)//4]}/mo")

        # By source
        from collections import Counter
        sources = Counter(l.source.value for l in all_listings)
        print(f"\n  By source: {dict(sources)}")

        # By type
        types = Counter(l.listing_type.value for l in all_listings)
        print(f"  By type:   {dict(types)}")

        # Export option
        print(f"\n  Export all as JSON? (y/n): ", end="")
        if input().strip().lower() == "y":
            data = [l.to_dict() for l in all_listings]
            filename = "listings_export.json"
            with open(filename, "w") as f:
                json.dump(data, f, indent=2, default=str)
            print(f"  Exported to {filename}")

    print()


if __name__ == "__main__":
    asyncio.run(main())
