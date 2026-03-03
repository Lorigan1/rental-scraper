# Quick Reference - Command Cheat Sheet

## Installation

```bash
pip install -e ".[dev]"
playwright install chromium
```

## Running Scrapers

```bash
# Quick demo (Craigslist + Kijiji)
python demo.py

# Full interactive demo (all sources)
python demo_complete.py
```

## Testing

```bash
# Unit tests only (fast, no network)
pytest tests/test_base_scraper.py -v

# Integration tests (hits live sites)
pytest -m slow -v

# All tests
pytest -v

# Specific test
pytest tests/test_base_scraper.py::TestExtractPrice -v
```

## Python API

```python
import asyncio
from rental_scraper.scrapers.craigslist import CraigslistScraper
from rental_scraper.scrapers.kijiji import KijijiScraper

# Craigslist
async with CraigslistScraper() as s:
    listings = await s.scrape(max_listings=20, min_price=500, max_price=1500)

# Kijiji
async with KijijiScraper() as s:
    listings = await s.scrape(max_listings=20)

# Facebook (manual dump)
from rental_scraper.facebook_extractor import FacebookExtractor
extractor = FacebookExtractor()
listings = extractor.extract_from_dump(open("posts.txt").read())
```

## Facebook Browser Setup

```bash
# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=9222 --user-data-dir="/tmp/chrome-debug"

# Linux
google-chrome --remote-debugging-port=9222 --user-data-dir="/tmp/chrome-debug"
```

## Export

```python
import json
data = [l.to_dict() for l in listings]
with open("listings.json", "w") as f:
    json.dump(data, f, indent=2, default=str)
```

## Environment Variables

```bash
export ANTHROPIC_API_KEY="sk-ant-..."  # Required for Facebook extraction only
```
