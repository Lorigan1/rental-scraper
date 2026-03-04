#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Teardown all GCP resources created by setup-gcp.sh
#
# Usage:
#   export GCP_PROJECT="your-project-id"
#   bash infra/teardown-gcp.sh
# ──────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT="${GCP_PROJECT:?Set GCP_PROJECT environment variable}"
REGION="${GCP_REGION:-us-west1}"
INSTANCE_NAME="rental-scraper-db"
BUCKET_NAME="${GCS_BUCKET:-${PROJECT}-rental-scraper}"
AR_REPO="rental-scraper"
JOB_NAME="rental-scraper-job"
SERVICE_ACCOUNT="rental-scraper-sa"
SCHEDULER_NAME="daily-scrape"

echo "⚠️  This will DELETE all rental-scraper GCP resources in project: ${PROJECT}"
read -p "Are you sure? (yes/no): " CONFIRM
if [ "${CONFIRM}" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

echo "→ Deleting Cloud Scheduler job..."
gcloud scheduler jobs delete "${SCHEDULER_NAME}" \
    --location="${REGION}" --project="${PROJECT}" --quiet 2>/dev/null || true

echo "→ Deleting Cloud Run job..."
gcloud run jobs delete "${JOB_NAME}" \
    --region="${REGION}" --project="${PROJECT}" --quiet 2>/dev/null || true

echo "→ Deleting Artifact Registry images..."
gcloud artifacts docker images delete \
    "${REGION}-docker.pkg.dev/${PROJECT}/${AR_REPO}/rental-scraper" \
    --project="${PROJECT}" --quiet --delete-tags 2>/dev/null || true

gcloud artifacts repositories delete "${AR_REPO}" \
    --location="${REGION}" --project="${PROJECT}" --quiet 2>/dev/null || true

echo "→ Deleting Cloud Storage bucket..."
gcloud storage rm -r "gs://${BUCKET_NAME}" --project="${PROJECT}" 2>/dev/null || true

echo "→ Deleting Cloud SQL instance (this takes a few minutes)..."
gcloud sql instances delete "${INSTANCE_NAME}" \
    --project="${PROJECT}" --quiet 2>/dev/null || true

echo "→ Deleting VPC connector..."
gcloud compute networks vpc-access connectors delete rental-scraper-conn \
    --region="${REGION}" --project="${PROJECT}" --quiet 2>/dev/null || true

echo "→ Deleting VPC peering and network..."
gcloud compute addresses delete google-managed-services-rental-scraper-vpc \
    --global --project="${PROJECT}" --quiet 2>/dev/null || true
gcloud compute networks delete rental-scraper-vpc \
    --project="${PROJECT}" --quiet 2>/dev/null || true

echo "→ Deleting Secret Manager secret..."
gcloud secrets delete db-password --project="${PROJECT}" --quiet 2>/dev/null || true

echo "→ Deleting service account..."
gcloud iam service-accounts delete \
    "${SERVICE_ACCOUNT}@${PROJECT}.iam.gserviceaccount.com" \
    --project="${PROJECT}" --quiet 2>/dev/null || true

echo ""
echo "Teardown complete. All rental-scraper resources deleted."
