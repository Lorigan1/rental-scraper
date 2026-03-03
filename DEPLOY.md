# Deployment Guide — GCP + GitHub

## Overview

The full pipeline runs as a scheduled Cloud Run job:

```
Cloud Scheduler (daily 8am PT)
  → Cloud Run Job (scrape Craigslist + Kijiji)
    → Cloud SQL PostgreSQL (store listings + price history)
    → Cloud Storage (export JSON snapshots)
```

GitHub pushes to `main` trigger Cloud Build to rebuild and redeploy automatically.

## Step 1: Push to GitHub

```bash
cd rental-scraper
bash infra/setup-github.sh
```

This creates a public repo, commits everything, and pushes. Set `GITHUB_VISIBILITY=private` for a private repo.

## Step 2: Deploy to GCP

```bash
export GCP_PROJECT="your-project-id"
export GCP_REGION="us-west1"         # optional, defaults to us-west1
export DB_PASSWORD="your-db-pass"    # optional, auto-generated if not set

bash infra/setup-gcp.sh
```

This creates all GCP resources in one shot (takes ~10 minutes, mostly Cloud SQL):

| Resource | Details |
|----------|---------|
| Cloud SQL | PostgreSQL 15, db-f1-micro, 10GB |
| Cloud Storage | `{project}-rental-scraper` bucket, 90-day lifecycle |
| Artifact Registry | Docker image repo |
| Cloud Run Job | 2GB RAM, 1 CPU, 15min timeout |
| Cloud Scheduler | Daily at 8:00 AM Pacific |
| Secret Manager | DB password stored securely |
| Service Account | Least-privilege SA for the job |

## Step 3: Verify

```bash
# Trigger a manual run
gcloud run jobs execute rental-scraper-job --region=us-west1 --project=${GCP_PROJECT}

# Watch logs
gcloud run jobs executions list --job=rental-scraper-job --region=us-west1

# Check exported data
gcloud storage ls gs://${GCP_PROJECT}-rental-scraper/scrapes/

# Connect to database (via Cloud SQL Proxy)
cloud-sql-proxy ${GCP_PROJECT}:us-west1:rental-scraper-db &
psql -h localhost -U scraper -d rental_scraper
```

## Step 4: CI/CD (Optional)

Connect Cloud Build to your GitHub repo so pushes to `main` auto-deploy:

```bash
gcloud builds triggers create github \
    --repo-name=rental-scraper \
    --repo-owner=YOUR_GITHUB_USERNAME \
    --branch-pattern="^main$" \
    --build-config=cloudbuild.yaml \
    --project=${GCP_PROJECT}
```

## Cost Estimate

Running daily with default settings:

| Resource | Monthly Cost |
|----------|-------------|
| Cloud SQL (db-f1-micro) | ~$9 |
| Cloud Run Job (daily, ~5min) | ~$0.50 |
| Cloud Storage (small JSONs) | ~$0.01 |
| Cloud Build (on push) | Free tier |
| **Total** | **~$10/month** |

To minimize costs, you can pause the scheduler and run manually:

```bash
# Pause
gcloud scheduler jobs pause daily-scrape --location=us-west1

# Manual run
gcloud run jobs execute rental-scraper-job --region=us-west1
```

## Teardown

To delete all resources:

```bash
export GCP_PROJECT="your-project-id"
bash infra/teardown-gcp.sh
```

## Architecture Diagram

```
┌─────────────────┐     ┌──────────────────┐
│ Cloud Scheduler  │────→│  Cloud Run Job   │
│ (daily 8am PT)  │     │  (rental-scraper) │
└─────────────────┘     └────────┬─────────┘
                                 │
                    ┌────────────┼────────────┐
                    │            │            │
                    ▼            ▼            ▼
            ┌──────────┐  ┌──────────┐  ┌──────────┐
            │Craigslist │  │  Kijiji  │  │Cloud SQL │
            │  Scraper  │  │ Scraper  │  │(Postgres)│
            └─────┬────┘  └────┬─────┘  └──────────┘
                  │             │               ▲
                  └──────┬──────┘               │
                         │                      │
                         ▼                      │
                   ┌──────────┐          ┌──────┘
                   │ Listings │──────────┘
                   │ (unified)│──────────┐
                   └──────────┘          │
                                         ▼
                                   ┌──────────┐
                                   │   GCS    │
                                   │ (export) │
                                   └──────────┘
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_HOST` | PostgreSQL host (TCP mode) | localhost |
| `DB_SOCKET_PATH` | Cloud SQL Unix socket path | — |
| `DB_NAME` | Database name | rental_scraper |
| `DB_USER` | Database user | scraper |
| `DB_PASSWORD` | Database password (or from Secret Manager) | — |
| `GCS_BUCKET` | Cloud Storage bucket name | — |
| `SCRAPE_MAX_LISTINGS` | Max listings per source | 50 |
| `SCRAPE_SOURCES` | Comma-separated sources | craigslist,kijiji |
