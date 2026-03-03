"""Storage backends for rental listings — PostgreSQL (Cloud SQL) and Cloud Storage.

Provides:
    - PostgresStore: Insert/query listings in Cloud SQL PostgreSQL
    - GCSExporter: Export listing snapshots as JSON to a GCS bucket
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Optional

from rental_scraper.models import Listing, ListingSource, ListingType

logger = logging.getLogger(__name__)

# ── SQL schema ────────────────────────────────────────────────────

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS scrape_runs (
    id              SERIAL PRIMARY KEY,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMPTZ,
    source          VARCHAR(20) NOT NULL,
    listings_found  INTEGER DEFAULT 0,
    status          VARCHAR(20) DEFAULT 'running'
);

CREATE TABLE IF NOT EXISTS listings (
    id              VARCHAR(64) PRIMARY KEY,
    source          VARCHAR(20) NOT NULL,
    url             TEXT,
    title           TEXT,
    price           INTEGER,
    location        TEXT,
    description     TEXT,
    posted_date     TIMESTAMPTZ,
    available_date  TIMESTAMPTZ,
    extracted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    listing_type    VARCHAR(30),
    num_bedrooms    INTEGER,
    num_bathrooms   INTEGER,
    num_roommates   INTEGER,
    square_feet     INTEGER,
    utilities_included BOOLEAN,
    furnished       BOOLEAN,
    pets_allowed    BOOLEAN,
    parking_included BOOLEAN,
    laundry_in_unit BOOLEAN,
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    image_urls      JSONB DEFAULT '[]'::jsonb,
    scrape_run_id   INTEGER REFERENCES scrape_runs(id)
);

CREATE TABLE IF NOT EXISTS price_history (
    id              SERIAL PRIMARY KEY,
    listing_id      VARCHAR(64) REFERENCES listings(id),
    price           INTEGER NOT NULL,
    observed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_listings_source ON listings(source);
CREATE INDEX IF NOT EXISTS idx_listings_price ON listings(price);
CREATE INDEX IF NOT EXISTS idx_listings_location ON listings(location);
CREATE INDEX IF NOT EXISTS idx_listings_type ON listings(listing_type);
CREATE INDEX IF NOT EXISTS idx_price_history_listing ON price_history(listing_id);
"""

UPSERT_LISTING_SQL = """
INSERT INTO listings (
    id, source, url, title, price, location, description,
    posted_date, available_date, extracted_at, listing_type,
    num_bedrooms, num_bathrooms, num_roommates, square_feet,
    utilities_included, furnished, pets_allowed, parking_included,
    laundry_in_unit, latitude, longitude, image_urls, scrape_run_id
) VALUES (
    %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s,
    %s, %s, %s, %s,
    %s, %s, %s, %s,
    %s, %s, %s, %s::jsonb, %s
)
ON CONFLICT (id) DO UPDATE SET
    price = EXCLUDED.price,
    description = EXCLUDED.description,
    extracted_at = EXCLUDED.extracted_at,
    image_urls = EXCLUDED.image_urls,
    scrape_run_id = EXCLUDED.scrape_run_id
"""

TRACK_PRICE_SQL = """
INSERT INTO price_history (listing_id, price, observed_at)
SELECT %s, %s, NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM price_history
    WHERE listing_id = %s AND price = %s
    ORDER BY observed_at DESC LIMIT 1
)
"""


class PostgresStore:
    """Store listings in Cloud SQL PostgreSQL.

    Reads connection info from environment variables:
        DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

    For Cloud SQL with Unix sockets (Cloud Run):
        DB_SOCKET_PATH = /cloudsql/PROJECT:REGION:INSTANCE
    """

    def __init__(self):
        self._conn = None

    def _get_connection(self):
        """Lazy-init database connection."""
        if self._conn is None or self._conn.closed:
            import psycopg2

            socket_path = os.environ.get("DB_SOCKET_PATH")
            if socket_path:
                # Cloud Run connects via Unix socket
                self._conn = psycopg2.connect(
                    dbname=os.environ.get("DB_NAME", "rental_scraper"),
                    user=os.environ.get("DB_USER", "scraper"),
                    password=os.environ.get("DB_PASSWORD", ""),
                    host=socket_path,
                )
            else:
                # Direct TCP connection (local dev, Cloud SQL Proxy)
                self._conn = psycopg2.connect(
                    host=os.environ.get("DB_HOST", "localhost"),
                    port=int(os.environ.get("DB_PORT", "5432")),
                    dbname=os.environ.get("DB_NAME", "rental_scraper"),
                    user=os.environ.get("DB_USER", "scraper"),
                    password=os.environ.get("DB_PASSWORD", ""),
                )
            self._conn.autocommit = True
        return self._conn

    def init_schema(self):
        """Create tables if they don't exist."""
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLES_SQL)
        logger.info("Database schema initialized.")

    def start_run(self, source: str) -> int:
        """Record a new scrape run, return run ID."""
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO scrape_runs (source) VALUES (%s) RETURNING id",
                (source,),
            )
            run_id = cur.fetchone()[0]
        return run_id

    def finish_run(self, run_id: int, listings_found: int, status: str = "completed"):
        """Mark a scrape run as finished."""
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE scrape_runs SET finished_at = NOW(), listings_found = %s, status = %s WHERE id = %s",
                (listings_found, status, run_id),
            )

    def store_listings(self, listings: list[Listing], run_id: Optional[int] = None):
        """Insert or update listings, track price changes."""
        conn = self._get_connection()
        with conn.cursor() as cur:
            for listing in listings:
                cur.execute(UPSERT_LISTING_SQL, (
                    listing.id, listing.source.value, listing.url, listing.title,
                    listing.price, listing.location, listing.description,
                    listing.posted_date, listing.available_date, listing.extracted_at,
                    listing.listing_type.value,
                    listing.num_bedrooms, listing.num_bathrooms, listing.num_roommates,
                    listing.square_feet,
                    listing.utilities_included, listing.furnished, listing.pets_allowed,
                    listing.parking_included, listing.laundry_in_unit,
                    listing.latitude, listing.longitude,
                    json.dumps(listing.image_urls), run_id,
                ))

                # Track price history
                if listing.price:
                    cur.execute(TRACK_PRICE_SQL, (
                        listing.id, listing.price,
                        listing.id, listing.price,
                    ))

        logger.info(f"Stored {len(listings)} listings (run_id={run_id})")

    def get_listings(
        self,
        source: Optional[str] = None,
        listing_type: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Query listings with optional filters."""
        conn = self._get_connection()
        conditions = []
        params = []

        if source:
            conditions.append("source = %s")
            params.append(source)
        if listing_type:
            conditions.append("listing_type = %s")
            params.append(listing_type)
        if min_price:
            conditions.append("price >= %s")
            params.append(min_price)
        if max_price:
            conditions.append("price <= %s")
            params.append(max_price)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT * FROM listings {where} ORDER BY extracted_at DESC LIMIT %s"
        params.append(limit)

        with conn.cursor() as cur:
            cur.execute(query, params)
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def close(self):
        if self._conn and not self._conn.closed:
            self._conn.close()


class GCSExporter:
    """Export listing snapshots to Google Cloud Storage.

    Reads bucket name from GCS_BUCKET environment variable.
    """

    def __init__(self, bucket_name: Optional[str] = None):
        self.bucket_name = bucket_name or os.environ.get("GCS_BUCKET", "rental-scraper-exports")

    def export_listings(self, listings: list[Listing], prefix: str = "scrapes"):
        """Export listings as a JSON file to GCS.

        File path: gs://{bucket}/{prefix}/{date}/{timestamp}.json
        """
        from google.cloud import storage

        client = storage.Client()
        bucket = client.bucket(self.bucket_name)

        now = datetime.now()
        blob_path = f"{prefix}/{now.strftime('%Y-%m-%d')}/{now.strftime('%H%M%S')}.json"
        blob = bucket.blob(blob_path)

        data = [l.to_dict() for l in listings]
        blob.upload_from_string(
            json.dumps(data, indent=2, default=str),
            content_type="application/json",
        )

        logger.info(f"Exported {len(listings)} listings to gs://{self.bucket_name}/{blob_path}")
        return f"gs://{self.bucket_name}/{blob_path}"
