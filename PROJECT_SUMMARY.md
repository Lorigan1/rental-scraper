# Project Summary - Vancouver Rental Scraper

## Purpose

Data-driven rental market analysis tool for Vancouver. Scrapes listings from multiple sources into a unified model, enabling price comparison and negotiation support.

**Primary use case:** Gather comparable room rental prices to negotiate rent reduction with landlord, backed by current market data.

**Secondary use case:** Portfolio piece demonstrating agent ops patterns (browser automation, LLM extraction, multi-source data pipelines).

## What's Built (Phase 1 - MVP)

### Three Scrapers

1. **Craigslist** (`craigslist.py`) - Automated Playwright scraping of vancouver.craigslist.org/search/roo. Supports price filtering, pagination, and optional detail fetching (visits individual listing pages for description, images, coordinates, amenities).

2. **Kijiji** (`kijiji.py`) - Automated Playwright scraping of Kijiji Vancouver room rentals. Uses data-testid attributes for selector stability. Same feature set as Craigslist scraper.

3. **Facebook** (`facebook.py` + `facebook_extractor.py`) - Browser attachment pattern via Chrome DevTools Protocol. Connects to user's existing Chrome session (no fake accounts). Extracts raw post text, then processes through Claude API for structured data extraction. Includes manual fallback (copy/paste posts).

### Unified Data Model

All sources produce the same `Listing` dataclass with 20+ fields covering price, location, amenities, dates, classification, and media. Enables direct cross-source comparison.

### Testing

- Unit tests for utility functions (price parsing, date parsing, text cleaning)
- Integration tests for live site scraping (marked `@pytest.mark.slow`)

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Browser attachment for Facebook | Uses real account, avoids bot detection, no ToS issues with fake accounts |
| Unified Listing model | Enables cross-source comparison without source-specific code |
| Separate capture from extraction | Raw data capture is independent of LLM processing; can re-process without re-scraping |
| Manual fallback for Facebook | If automation fails, manual copy/paste + LLM extraction still works |
| Playwright over requests | Handles JavaScript-rendered pages (Kijiji React app), cookie banners, dynamic content |
| CSS selectors + data-testid | data-testid attributes are more stable than class names across site redesigns |
| Random delays | Human-like browsing behavior reduces bot detection risk |

## Roadmap

### Phase 2: Deduplication
- Fuzzy matching on title + price + location to identify duplicate listings across sources
- Canonical listing merging (take best data from each source)

### Phase 3: SQLite Storage
- Historical listing tracking (when posted, when removed, price changes)
- Schema: listings table, scrape_runs table, price_history table

### Phase 4: Analysis Pipeline
- Filter comparables (same listing type, similar location, similar size)
- Statistical analysis: median, percentiles, trends
- Neighborhood-level pricing
- "Your rent vs market" comparison

### Phase 5: Report Generation
- Markdown report with charts (price distribution, comparable analysis)
- Formatted for sharing with landlord
- Data tables with sources for credibility

## Portfolio Value

This project demonstrates:
- **Multi-source data pipeline** design with unified schema
- **Browser automation** patterns (headless scraping + CDP attachment)
- **LLM integration** for unstructured data extraction
- **Production patterns**: error handling, logging, rate limiting, testing
- **Ethical scraping**: real accounts for Facebook, human-like delays, respecting robots.txt
