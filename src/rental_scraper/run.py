"""Cloud Run job entry point — scrape all sources and store results.

This is the main entry point for the scheduled Cloud Run job.
It scrapes Craigslist and Kijiji, stores results in Cloud SQL,
and exports snapshots to Cloud Storage.

Environment variables:
    DB_HOST / DB_SOCKET_PATH  - PostgreSQL connection
    DB_NAME, DB_USER, DB_PASSWORD
    GCS_BUCKET               - Cloud Storage bucket for exports
    SCRAPE_MAX_LISTINGS       - Max listings per source (default: 50)
    SCRAPE_SOURCES            - Comma-separated sources (default: craigslist,kijiji)
"""

import asyncio
import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("rental_scraper.run")


async def scrape_source(source: str, max_listings: int) -> list:
    """Scrape a single source and return listings."""
    from rental_scraper.models import Listing

    if source == "craigslist":
        from rental_scraper.scrapers.craigslist import CraigslistScraper
        async with CraigslistScraper(headless=True) as scraper:
            return await scraper.scrape(max_listings=max_listings)

    elif source == "kijiji":
        from rental_scraper.scrapers.kijiji import KijijiScraper
        async with KijijiScraper(headless=True) as scraper:
            return await scraper.scrape(max_listings=max_listings)

    else:
        logger.warning(f"Unknown source: {source}")
        return []


async def main():
    max_listings = int(os.environ.get("SCRAPE_MAX_LISTINGS", "50"))
    sources_str = os.environ.get("SCRAPE_SOURCES", "craigslist,kijiji")
    sources = [s.strip() for s in sources_str.split(",") if s.strip()]

    logger.info(f"Starting scrape run: sources={sources}, max_listings={max_listings}")

    # Initialize storage (optional — skip if DB not configured)
    db = None
    gcs = None

    try:
        if os.environ.get("DB_HOST") or os.environ.get("DB_SOCKET_PATH"):
            from rental_scraper.storage import PostgresStore
            db = PostgresStore()
            db.init_schema()
            logger.info("PostgreSQL storage initialized.")
    except Exception as e:
        logger.warning(f"Database not available, running without storage: {e}")

    try:
        if os.environ.get("GCS_BUCKET"):
            from rental_scraper.storage import GCSExporter
            gcs = GCSExporter()
            logger.info(f"GCS exporter initialized: {gcs.bucket_name}")
    except Exception as e:
        logger.warning(f"GCS not available, running without export: {e}")

    # Scrape each source
    all_listings = []

    for source in sources:
        run_id = None
        if db:
            run_id = db.start_run(source)

        try:
            logger.info(f"Scraping {source}...")
            listings = await scrape_source(source, max_listings)
            logger.info(f"  {source}: {len(listings)} listings found")

            all_listings.extend(listings)

            if db and listings:
                db.store_listings(listings, run_id=run_id)

            if db:
                db.finish_run(run_id, len(listings), status="completed")

        except Exception as e:
            logger.error(f"  {source} failed: {e}")
            if db and run_id:
                db.finish_run(run_id, 0, status="failed")

    # Export combined results to GCS
    if gcs and all_listings:
        try:
            path = gcs.export_listings(all_listings)
            logger.info(f"Exported to {path}")
        except Exception as e:
            logger.error(f"GCS export failed: {e}")

    # Summary
    prices = [l.price for l in all_listings if l.price]
    logger.info(f"Run complete: {len(all_listings)} total listings")
    if prices:
        logger.info(f"  Price range: ${min(prices)} - ${max(prices)}/mo")
        logger.info(f"  Average: ${sum(prices)/len(prices):.0f}/mo")

    if db:
        db.close()

    return all_listings


if __name__ == "__main__":
    asyncio.run(main())
