#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# GCP Infrastructure Setup for Vancouver Rental Scraper
#
# Creates: Cloud SQL (PostgreSQL), Cloud Storage bucket,
#          Artifact Registry repo, Cloud Run job, Cloud Scheduler
#
# Prerequisites:
#   - gcloud CLI authenticated (gcloud auth login)
#   - A GCP project with billing enabled
#
# Usage:
#   export GCP_PROJECT="your-project-id"
#   bash infra/setup-gcp.sh
# ──────────────────────────────────────────────────────────────
set -euo pipefail

# ── Configuration ─────────────────────────────────────────────
PROJECT="${GCP_PROJECT:?Set GCP_PROJECT environment variable}"
REGION="${GCP_REGION:-us-west1}"             # Close to Vancouver
INSTANCE_NAME="rental-scraper-db"
DB_NAME="rental_scraper"
DB_USER="scraper"
DB_PASSWORD="${DB_PASSWORD:-$(openssl rand -base64 16)}"
BUCKET_NAME="${GCS_BUCKET:-${PROJECT}-rental-scraper}"
AR_REPO="rental-scraper"
JOB_NAME="rental-scraper-job"
SERVICE_ACCOUNT="rental-scraper-sa"
SCHEDULER_NAME="daily-scrape"

echo "═══════════════════════════════════════════════════"
echo "  Vancouver Rental Scraper — GCP Setup"
echo "═══════════════════════════════════════════════════"
echo "  Project:  ${PROJECT}"
echo "  Region:   ${REGION}"
echo "  DB:       ${INSTANCE_NAME} / ${DB_NAME}"
echo "  Bucket:   ${BUCKET_NAME}"
echo "═══════════════════════════════════════════════════"
echo ""

# ── Enable required APIs ──────────────────────────────────────
echo "→ Enabling GCP APIs..."
gcloud services enable \
    sqladmin.googleapis.com \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com \
    cloudscheduler.googleapis.com \
    secretmanager.googleapis.com \
    servicenetworking.googleapis.com \
    vpcaccess.googleapis.com \
    compute.googleapis.com \
    --project="${PROJECT}" \
    --quiet

# ── Service Account ───────────────────────────────────────────
echo "→ Creating service account..."
gcloud iam service-accounts create "${SERVICE_ACCOUNT}" \
    --display-name="Rental Scraper Service Account" \
    --project="${PROJECT}" 2>/dev/null || echo "  (already exists)"

SA_EMAIL="${SERVICE_ACCOUNT}@${PROJECT}.iam.gserviceaccount.com"

# Grant necessary roles
for ROLE in \
    roles/cloudsql.client \
    roles/storage.objectAdmin \
    roles/run.invoker \
    roles/secretmanager.secretAccessor; do
    gcloud projects add-iam-policy-binding "${PROJECT}" \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="${ROLE}" \
        --quiet > /dev/null
done
echo "  Service account: ${SA_EMAIL}"

# ── VPC Network + Private Services Access ─────────────────────
# Required by org policy: sql.restrictPublicIp
NETWORK_NAME="rental-scraper-vpc"
CONNECTOR_NAME="rental-scraper-conn"

echo "→ Setting up VPC for private Cloud SQL..."
gcloud compute networks create "${NETWORK_NAME}" \
    --subnet-mode=auto \
    --project="${PROJECT}" 2>/dev/null || echo "  VPC already exists"

# Allocate IP range for Private Services Access
echo "→ Allocating private IP range for Cloud SQL..."
gcloud compute addresses create google-managed-services-${NETWORK_NAME} \
    --global \
    --purpose=VPC_PEERING \
    --prefix-length=16 \
    --network="${NETWORK_NAME}" \
    --project="${PROJECT}" 2>/dev/null || echo "  IP range already allocated"

# Create the private connection
echo "→ Creating Private Services Access connection (this may take a minute)..."
gcloud services vpc-peerings connect \
    --service=servicenetworking.googleapis.com \
    --ranges=google-managed-services-${NETWORK_NAME} \
    --network="${NETWORK_NAME}" \
    --project="${PROJECT}" 2>/dev/null || echo "  Peering already exists"

# Create Serverless VPC Connector (for Cloud Run → private Cloud SQL)
echo "→ Creating Serverless VPC Access connector..."
gcloud compute networks vpc-access connectors create "${CONNECTOR_NAME}" \
    --region="${REGION}" \
    --network="${NETWORK_NAME}" \
    --range="10.8.0.0/28" \
    --project="${PROJECT}" 2>/dev/null || echo "  VPC connector already exists"

# ── Cloud SQL (PostgreSQL — private IP only) ──────────────────
echo "→ Creating Cloud SQL instance (this takes 5-10 minutes)..."
if ! gcloud sql instances describe "${INSTANCE_NAME}" --project="${PROJECT}" &>/dev/null; then
    gcloud sql instances create "${INSTANCE_NAME}" \
        --database-version=POSTGRES_15 \
        --tier=db-f1-micro \
        --region="${REGION}" \
        --storage-size=10GB \
        --storage-auto-increase \
        --no-assign-ip \
        --network="projects/${PROJECT}/global/networks/${NETWORK_NAME}" \
        --project="${PROJECT}" \
        --quiet
    echo "  Instance created: ${INSTANCE_NAME} (private IP only)"
else
    echo "  Instance already exists: ${INSTANCE_NAME}"
fi

# Create database and user
echo "→ Creating database and user..."
gcloud sql databases create "${DB_NAME}" \
    --instance="${INSTANCE_NAME}" \
    --project="${PROJECT}" 2>/dev/null || echo "  Database already exists"

gcloud sql users create "${DB_USER}" \
    --instance="${INSTANCE_NAME}" \
    --password="${DB_PASSWORD}" \
    --project="${PROJECT}" 2>/dev/null || echo "  User already exists"

# Store password in Secret Manager
echo "→ Storing DB password in Secret Manager..."
echo -n "${DB_PASSWORD}" | gcloud secrets create db-password \
    --data-file=- \
    --project="${PROJECT}" 2>/dev/null || \
    echo -n "${DB_PASSWORD}" | gcloud secrets versions add db-password \
    --data-file=- \
    --project="${PROJECT}" 2>/dev/null || echo "  Secret already up to date"

# ── Cloud Storage ─────────────────────────────────────────────
echo "→ Creating Cloud Storage bucket..."
gcloud storage buckets create "gs://${BUCKET_NAME}" \
    --location="${REGION}" \
    --project="${PROJECT}" 2>/dev/null || echo "  Bucket already exists"

# Set lifecycle: delete exports older than 90 days
cat > /tmp/lifecycle.json << 'LIFECYCLE'
{
  "rule": [{
    "action": {"type": "Delete"},
    "condition": {"age": 90}
  }]
}
LIFECYCLE
gcloud storage buckets update "gs://${BUCKET_NAME}" \
    --lifecycle-file=/tmp/lifecycle.json \
    --project="${PROJECT}" --quiet

echo "  Bucket: gs://${BUCKET_NAME}"

# ── Artifact Registry ─────────────────────────────────────────
echo "→ Creating Artifact Registry repository..."
gcloud artifacts repositories create "${AR_REPO}" \
    --repository-format=docker \
    --location="${REGION}" \
    --project="${PROJECT}" 2>/dev/null || echo "  Repository already exists"

echo "  Registry: ${REGION}-docker.pkg.dev/${PROJECT}/${AR_REPO}"

# ── Build and push container ──────────────────────────────────
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${AR_REPO}/rental-scraper:latest"

echo "→ Building container image with Cloud Build..."
gcloud builds submit . \
    --tag="${IMAGE}" \
    --project="${PROJECT}" \
    --quiet

echo "  Image: ${IMAGE}"

# ── Cloud Run Job ─────────────────────────────────────────────
CONNECTION_NAME=$(gcloud sql instances describe "${INSTANCE_NAME}" \
    --project="${PROJECT}" --format='value(connectionName)')

# Get the private IP of the Cloud SQL instance
DB_PRIVATE_IP=$(gcloud sql instances describe "${INSTANCE_NAME}" \
    --project="${PROJECT}" --format='value(ipAddresses[0].ipAddress)')
echo "  DB private IP: ${DB_PRIVATE_IP}"

echo "→ Creating Cloud Run job..."
gcloud run jobs create "${JOB_NAME}" \
    --image="${IMAGE}" \
    --region="${REGION}" \
    --project="${PROJECT}" \
    --service-account="${SA_EMAIL}" \
    --set-cloudsql-instances="${CONNECTION_NAME}" \
    --vpc-connector="projects/${PROJECT}/locations/${REGION}/connectors/${CONNECTOR_NAME}" \
    --vpc-egress=private-ranges-only \
    --memory=2Gi \
    --cpu=1 \
    --task-timeout=15m \
    --max-retries=1 \
    --set-env-vars="^::^DB_HOST=${DB_PRIVATE_IP}::DB_NAME=${DB_NAME}::DB_USER=${DB_USER}::GCS_BUCKET=${BUCKET_NAME}::SCRAPE_MAX_LISTINGS=50::SCRAPE_SOURCES=craigslist,kijiji" \
    --set-secrets="DB_PASSWORD=db-password:latest" \
    --quiet 2>/dev/null || \
gcloud run jobs update "${JOB_NAME}" \
    --image="${IMAGE}" \
    --region="${REGION}" \
    --project="${PROJECT}" \
    --service-account="${SA_EMAIL}" \
    --set-cloudsql-instances="${CONNECTION_NAME}" \
    --vpc-connector="projects/${PROJECT}/locations/${REGION}/connectors/${CONNECTOR_NAME}" \
    --vpc-egress=private-ranges-only \
    --memory=2Gi \
    --cpu=1 \
    --task-timeout=15m \
    --max-retries=1 \
    --set-env-vars="^::^DB_HOST=${DB_PRIVATE_IP}::DB_NAME=${DB_NAME}::DB_USER=${DB_USER}::GCS_BUCKET=${BUCKET_NAME}::SCRAPE_MAX_LISTINGS=50::SCRAPE_SOURCES=craigslist,kijiji" \
    --set-secrets="DB_PASSWORD=db-password:latest" \
    --quiet

echo "  Job: ${JOB_NAME}"

# ── Cloud Scheduler (daily at 8am Pacific) ────────────────────
echo "→ Creating Cloud Scheduler job..."
gcloud scheduler jobs create http "${SCHEDULER_NAME}" \
    --location="${REGION}" \
    --schedule="0 8 * * *" \
    --time-zone="America/Vancouver" \
    --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT}/jobs/${JOB_NAME}:run" \
    --http-method=POST \
    --oauth-service-account-email="${SA_EMAIL}" \
    --project="${PROJECT}" \
    --quiet 2>/dev/null || echo "  Scheduler already exists"

echo "  Schedule: Daily at 8:00 AM Pacific"

# ── Done ──────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
echo "  Setup complete!"
echo "═══════════════════════════════════════════════════"
echo ""
echo "  Cloud SQL:     ${CONNECTION_NAME}"
echo "  Cloud Storage: gs://${BUCKET_NAME}"
echo "  Cloud Run Job: ${JOB_NAME}"
echo "  Schedule:      Daily at 8:00 AM Pacific"
echo "  DB Password:   Stored in Secret Manager (db-password)"
echo ""
echo "  Manual trigger:"
echo "    gcloud run jobs execute ${JOB_NAME} --region=${REGION} --project=${PROJECT}"
echo ""
echo "  View results:"
echo "    gcloud storage ls gs://${BUCKET_NAME}/scrapes/"
echo ""
if [ -n "${DB_PASSWORD}" ]; then
    echo "  DB Password (save this): ${DB_PASSWORD}"
fi
