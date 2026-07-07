#!/bin/bash

# Exit on error
set -e

# Ensure project is set
if [ -z "$GOOGLE_CLOUD_PROJECT" ]; then
  echo "Error: GOOGLE_CLOUD_PROJECT environment variable is not set."
  exit 1
fi

DB_INSTANCE="warehouse-db"
DB_NAME="warehouse"
DB_REGION="us-central1"
DB_PASS="super-secret-password"

echo "============================================="
echo "1. Creating Cloud SQL PostgreSQL instance '${DB_INSTANCE}'..."
echo "============================================="
if gcloud sql instances describe "${DB_INSTANCE}" &>/dev/null; then
  echo "Cloud SQL instance '${DB_INSTANCE}' already exists. Skipping creation."
else
  gcloud sql instances create "${DB_INSTANCE}" \
      --database-version=POSTGRES_15 \
      --tier=db-f1-micro \
      --region="${DB_REGION}" \
      --root-password="${DB_PASS}" \
      --quiet
fi

echo "============================================="
echo "2. Creating Database '${DB_NAME}'..."
echo "============================================="
if gcloud sql databases describe "${DB_NAME}" --instance="${DB_INSTANCE}" &>/dev/null; then
  echo "Database '${DB_NAME}' already exists. Skipping creation."
else
  gcloud sql databases create "${DB_NAME}" --instance="${DB_INSTANCE}" \
      --quiet
fi

echo "============================================="
echo "3. Running Table Creation and Seeding..."
echo "============================================="
python3 scripts/setup_db.py
