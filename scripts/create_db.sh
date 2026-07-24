#!/bin/bash

# Exit on error
set -e

if [ -z "$GEAP_PREFIX" ]; then
  echo "Error: GEAP_PREFIX environment variable is not set."
  exit 1
fi
PREFIX="${GEAP_PREFIX%%[!a-zA-Z0-9]*}" 

# Ensure project is set
if [ -z "$GOOGLE_CLOUD_PROJECT" ]; then
  echo "Error: GOOGLE_CLOUD_PROJECT environment variable is not set."
  exit 1
fi

DB_INSTANCE="${PREFIX}-warehouse-db"
export DB_INSTANCE
DB_NAME="warehouse"
export DB_NAME
DB_REGION="us-central1"
DB_PASS="super-secret-password"

echo "============================================="
echo "1. Creating Cloud SQL PostgreSQL instance '${DB_INSTANCE}'..."
echo "============================================="
if gcloud sql instances describe "${DB_INSTANCE}" --project="${GOOGLE_CLOUD_PROJECT}" &>/dev/null; then
  echo "Cloud SQL instance '${DB_INSTANCE}' already exists. Skipping creation."
else
  gcloud sql instances create "${DB_INSTANCE}" \
      --project="${GOOGLE_CLOUD_PROJECT}" \
      --database-version=POSTGRES_15 \
      --tier=db-f1-micro \
      --region="${DB_REGION}" \
      --root-password="${DB_PASS}" \
      --quiet
fi

echo "============================================="
echo "2. Creating Database '${DB_NAME}'..."
echo "============================================="
if gcloud sql databases describe "${DB_NAME}" --instance="${DB_INSTANCE}" --project="${GOOGLE_CLOUD_PROJECT}" &>/dev/null; then
  echo "Database '${DB_NAME}' already exists. Skipping creation."
else
  gcloud sql databases create "${DB_NAME}" --instance="${DB_INSTANCE}" \
      --project="${GOOGLE_CLOUD_PROJECT}" \
      --quiet
fi

echo "============================================="
echo "3. Running Table Creation and Seeding..."
echo "============================================="
venv/bin/python3 scripts/setup_db.py
