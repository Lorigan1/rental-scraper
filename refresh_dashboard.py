#!/usr/bin/env python3
"""Download latest scrape data from GCS and open the dashboard.

Usage:
    python refresh_dashboard.py                  # latest scrape
    python refresh_dashboard.py --all            # merge all scrapes
    python refresh_dashboard.py --date 2026-03-03  # specific date
"""

import argparse
import json
import os
import subprocess
import sys
import webbrowser
from pathlib import Path

BUCKET = "rental-tool-489118-rental-scraper"
PROJECT = "rental-tool-489118"
PREFIX = "scrapes"
DASHBOARD = Path(__file__).parent / "dashboard.html"
DATA_FILE = Path(__file__).parent / "data.json"


def gcloud(*args) -> str:
    """Run a gcloud command and return stdout."""
    cmd = ["gcloud"] + list(args) + [f"--project={PROJECT}"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def list_scrapes(date_filter: str = None) -> list[str]:
    """List available scrape JSON files in GCS."""
    path = f"gs://{BUCKET}/{PREFIX}/"
    if date_filter:
        path += f"{date_filter}/"
    output = gcloud("storage", "ls", path, "--recursive")
    return [line for line in output.splitlines() if line.endswith(".json")]


def download_json(gcs_path: str) -> list[dict]:
    """Download and parse a JSON file from GCS."""
    output = gcloud("storage", "cat", gcs_path)
    return json.loads(output)


def main():
    parser = argparse.ArgumentParser(description="Refresh dashboard with latest scrape data")
    parser.add_argument("--all", action="store_true", help="Merge all available scrapes")
    parser.add_argument("--date", type=str, help="Filter to specific date (YYYY-MM-DD)")
    parser.add_argument("--no-open", action="store_true", help="Don't open browser")
    args = parser.parse_args()

    print(f"Listing scrapes in gs://{BUCKET}/{PREFIX}/...")
    files = list_scrapes(args.date)

    if not files:
        print("No scrape files found.")
        sys.exit(1)

    print(f"Found {len(files)} scrape file(s)")

    if args.all:
        # Merge all scrapes, deduplicate by id
        all_listings = {}
        for f in files:
            print(f"  Downloading {f}...")
            data = download_json(f)
            for listing in data:
                lid = listing.get("id", listing.get("url", ""))
                all_listings[lid] = listing
        merged = list(all_listings.values())
        print(f"Merged: {len(merged)} unique listings from {len(files)} files")
    else:
        # Just the latest file
        latest = files[-1]
        print(f"Downloading {latest}...")
        merged = download_json(latest)
        print(f"Loaded: {len(merged)} listings")

    # Write data.json next to dashboard
    DATA_FILE.write_text(json.dumps(merged, indent=2, default=str))
    print(f"Saved to {DATA_FILE}")

    if not args.no_open:
        url = DASHBOARD.as_uri()
        print(f"Opening dashboard: {url}")
        webbrowser.open(url)
    else:
        print(f"Dashboard: {DASHBOARD}")


if __name__ == "__main__":
    main()
