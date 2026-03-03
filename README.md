# Vancouver Rental Scraper

Multi-source rental listing scraper for Vancouver market analysis. Extracts structured data from Craigslist, Kijiji, and Facebook housing groups into a unified data model for price comparison and negotiation support.

## Quick Start

```bash
# Install
pip install -e ".[dev]"
playwright install chromium

# Run demo (Craigslist + Kijiji)
python demo.py

# Run unit tests
pytest tests/test_base_scraper.py -v

# Run integration tests (hits live sites)
pytest -m slow -v
```

## Architecture

Three scrapers produce the same `Listing` dataclass:

| Source | Method | Auth Required |
|--------|--------|--------------|
| Craigslist | Playwright scraping | No |
| Kijiji | Playwright scraping | No |
| Facebook | Browser attachment via CDP | User's own login |

### Data Model

Every listing has: price, location, listing type, amenities, dates, and source tracking. See `src/rental_scraper/models.py` for the full schema.

```python
from rental_scraper.models import Listing, ListingType, ListingSource

# All sources produce the same Listing object
listing = Listing(
    source=ListingSource.CRAIGSLIST,
    price=900,
    location="Kitsilano",
    listing_type=ListingType.ROOM_PRIVATE,
    utilities_included=True,
)
```

## Usage

### Craigslist

```python
import asyncio
from rental_scraper.scrapers.craigslist import CraigslistScraper

async def main():
    async with CraigslistScraper() as scraper:
        listings = await scraper.scrape(
            max_listings=20,
            min_price=500,
            max_price=1500,
            fetch_details=True,  # Visit each listing for full info
        )
    for l in listings:
        print(l.summary())

asyncio.run(main())
```

### Kijiji

```python
from rental_scraper.scrapers.kijiji import KijijiScraper

async with KijijiScraper() as scraper:
    listings = await scraper.scrape(max_listings=20)
```

### Facebook (Browser Attachment)

```bash
# 1. Launch Chrome with debugging
google-chrome --remote-debugging-port=9222 --user-data-dir="/tmp/chrome-debug"

# 2. Log into Facebook, navigate to a housing group

# 3. Run the scraper
python demo_complete.py  # Choose option 4
```

### Facebook (Manual Dump)

```python
from rental_scraper.facebook_extractor import FacebookExtractor

extractor = FacebookExtractor()  # Uses ANTHROPIC_API_KEY env var
listings = extractor.extract_from_dump("""
Room available in Kitsilano $850/mo. 2 roommates, utilities included.
Available March 1st. Furnished private room.
---
Looking for a room near downtown. Budget $900. Moving Feb 15.
---
Basement suite in East Van $1100/mo. 1br, pets ok, laundry in unit.
""")
# Returns 2 listings (skips the "seeking" post)
```

## Project Structure

```
rental-scraper/
├── src/rental_scraper/
│   ├── models.py              # Listing dataclass, enums
│   ├── scrapers/
│   │   ├── base.py            # Utilities: price/date parsing, delays
│   │   ├── craigslist.py      # Craigslist rooms & shares
│   │   ├── kijiji.py          # Kijiji room rentals
│   │   └── facebook.py        # Facebook CDP browser attachment
│   └── facebook_extractor.py  # Claude API extraction
├── tests/
│   ├── test_base_scraper.py   # Unit tests (no network)
│   ├── test_craigslist.py     # Integration tests
│   └── test_kijiji.py         # Integration tests
├── demo.py                    # Quick demo: CL + Kijiji
└── demo_complete.py           # Full demo: all 3 sources
```

## Dependencies

- **playwright** - Browser automation for Craigslist/Kijiji, CDP for Facebook
- **anthropic** - Claude API for Facebook post extraction
- **beautifulsoup4/lxml** - HTML parsing fallback
- **httpx** - HTTP client
- **python-dateutil** - Date parsing

## Roadmap

- [ ] Phase 2: Deduplication across sources
- [ ] Phase 3: SQLite storage for historical tracking
- [ ] Phase 4: Analysis pipeline (comparable filtering, price recommendations)
- [ ] Phase 5: Markdown report generation for landlord negotiation
