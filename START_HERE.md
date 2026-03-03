# Start Here - Quick Setup Guide

## Prerequisites

- Python 3.11+
- Chrome browser (for Facebook scraper)
- Anthropic API key (for Facebook extraction only)

## Setup Checklist

```bash
# 1. Clone/extract the project
cd rental-scraper

# 2. Install in development mode
pip install -e ".[dev]"

# 3. Install Playwright browsers
playwright install chromium

# 4. Verify installation
pytest tests/test_base_scraper.py -v
# All tests should pass

# 5. Run the demo
python demo.py
# Should scrape ~10 listings each from Craigslist + Kijiji

# 6. (Optional) Set up Facebook extraction
export ANTHROPIC_API_KEY="sk-ant-..."
# See FACEBOOK_GUIDE.md for full setup
```

## What to Run First

1. **`python demo.py`** - Quick test of Craigslist + Kijiji scrapers
2. **`python demo_complete.py`** - Interactive menu with all sources
3. **`pytest -v`** - Run all unit tests
4. **`pytest -m slow -v`** - Run integration tests (hits live sites)

## File Guide

| File | What It Does |
|------|-------------|
| `demo.py` | Quick demo: CL + Kijiji, 10 listings each |
| `demo_complete.py` | Full interactive demo with all 3 sources |
| `README.md` | Project overview and code examples |
| `FACEBOOK_GUIDE.md` | Detailed Facebook scraper setup |
| `PROJECT_SUMMARY.md` | Design decisions and roadmap |
| `QUICK_REFERENCE.md` | Command cheat sheet |

## Troubleshooting

**"ModuleNotFoundError: rental_scraper"**
→ Run `pip install -e .` from the project root

**"playwright._impl._errors.Error: Executable doesn't exist"**
→ Run `playwright install chromium`

**Craigslist/Kijiji returning 0 listings**
→ Sites may be blocking automated access. Try with `headless=False` to see the browser.
→ Sites change their DOM structure periodically; selectors may need updating.

**Facebook "Failed to connect"**
→ Launch Chrome with `--remote-debugging-port=9222` flag
→ See FACEBOOK_GUIDE.md for platform-specific commands
