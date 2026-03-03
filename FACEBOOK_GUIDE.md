# Facebook Groups Scraper - Setup Guide

## Why Browser Attachment?

Instead of creating fake accounts or using unofficial APIs, this scraper connects to your existing Chrome session where you're already logged into Facebook. This is the "browser attachment" pattern:

- Uses your real Facebook account (no bot detection issues)
- No fake accounts or ToS violations
- You control what pages the scraper sees
- Falls back to manual copy/paste if automation isn't feasible

## Method 1: Automated (Browser Attachment via CDP)

### Step 1: Launch Chrome with Remote Debugging

```bash
# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=9222 \
    --user-data-dir="/tmp/chrome-debug"

# Linux
google-chrome --remote-debugging-port=9222 --user-data-dir="/tmp/chrome-debug"

# Windows
"C:\Program Files\Google\Chrome\Application\chrome.exe" ^
    --remote-debugging-port=9222 ^
    --user-data-dir="%TEMP%\chrome-debug"
```

**Important:** This launches a separate Chrome profile. Your regular Chrome stays untouched.

### Step 2: Log into Facebook

In the debug Chrome window:
1. Go to facebook.com
2. Log in with your account
3. Navigate to a Vancouver housing group, e.g.:
   - "Vancouver Rooms & Rentals"
   - "Vancouver Housing - Rooms for Rent"
   - "Vancouver Affordable Housing"

### Step 3: Run the Scraper

```python
import asyncio
from rental_scraper.scrapers.facebook import FacebookGroupsScraper
from rental_scraper.facebook_extractor import FacebookExtractor

async def main():
    # Connect to your Chrome session
    async with FacebookGroupsScraper(cdp_url="http://localhost:9222") as scraper:
        # Get info about current page
        info = await scraper.get_group_info()
        print(f"Connected to: {info['title']}")

        # Scroll and extract posts
        posts = await scraper.scrape_current_page(max_posts=20, max_scrolls=10)
        print(f"Found {len(posts)} posts")

        # Process with Claude API
        extractor = FacebookExtractor()
        listings = extractor.extract_from_posts(posts)

        for listing in listings:
            print(listing.summary())

asyncio.run(main())
```

### Troubleshooting

**"Failed to connect to Chrome"**
- Make sure Chrome is running with `--remote-debugging-port=9222`
- Check that port 9222 isn't blocked by firewall
- Verify with: `curl http://localhost:9222/json/version`

**"No pages found"**
- Open a tab in the debug Chrome window
- Navigate to a Facebook group page

**Posts not loading / empty text**
- Facebook's DOM changes frequently; selectors may need updating
- Try the manual dump method as fallback

## Method 2: Manual Dump (No Automation)

If browser attachment doesn't work, you can manually copy posts:

### Step 1: Collect Posts

1. Open a Facebook housing group in your browser
2. Scroll through recent posts
3. For each rental post, select all text and copy it
4. Paste into a text file, separating posts with `---`

Example file (`posts.txt`):
```
Room available in Kitsilano! $850/month, utilities included.
Private room in a 3-bedroom house, 2 other roommates.
Available March 1st. Furnished. Near bus routes.
Contact me for viewing.
---
Basement suite in East Van - $1100/mo
1 bedroom, own bathroom, laundry in unit.
Pets negotiable. Available immediately.
Street parking available.
---
LOOKING FOR: room near downtown, budget $900
Moving Feb 15th, clean and quiet.
```

### Step 2: Process with LLM

```python
from rental_scraper.facebook_extractor import FacebookExtractor

extractor = FacebookExtractor()

# From file
with open("posts.txt") as f:
    listings = extractor.extract_from_dump(f.read())

# The extractor automatically:
# - Classifies offering vs seeking posts
# - Skips "seeking" posts (like the 3rd example above)
# - Extracts structured data from "offering" posts

for listing in listings:
    print(listing.summary())
```

### Step 3: Interactive Mode

Run `python demo_complete.py` and choose option 6 (Manual dump) to paste posts directly into the terminal.

## API Key Setup

The Facebook extractor uses the Anthropic API (Claude). Set your API key:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

Or pass it directly:
```python
extractor = FacebookExtractor(api_key="sk-ant-...")
```

## Cost Estimates

Each post extraction uses approximately 500-800 tokens. At Claude Sonnet pricing:
- 20 posts ≈ $0.01-0.02
- 100 posts ≈ $0.05-0.10

The extractor processes posts one at a time for reliability.
