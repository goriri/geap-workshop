#!/bin/bash

# Exit on error
set -e

# Ensure project is set
if [ -z "$GOOGLE_CLOUD_PROJECT" ]; then
  echo "Error: GOOGLE_CLOUD_PROJECT environment variable is not set."
  exit 1
fi

PROJECT_NUMBER=$(gcloud projects describe "$GOOGLE_CLOUD_PROJECT" --format="value(projectNumber)")
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "============================================="
1. Granting Cloud SQL Client role to Cloud Run service account...
echo "============================================="
gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/cloudsql.client" \
    --quiet

echo "============================================="
2. Deploying MCP Server to Cloud Run...
echo "============================================="
gcloud run deploy warehouse-mcp-server \
    --source mcp_server \
    --region us-central1 \
    --add-cloudsql-instances "${GOOGLE_CLOUD_PROJECT}:us-central1:warehouse-db" \
    --set-env-vars "DB_USER=postgres,DB_PASS=super-secret-password,DB_NAME=warehouse,INSTANCE_CONNECTION_NAME=${GOOGLE_CLOUD_PROJECT}:us-central1:warehouse-db" \
    --allow-unauthenticated \
    --quiet

# Retrieve and print the URL
SERVICE_URL=$(gcloud run services describe warehouse-mcp-server --region us-central1 --format="value(status.url)")
echo "============================================="
Deployment complete!
Your MCP Server URL: ${SERVICE_URL}
Set this as environment variable for registration:
export MCP_SERVER_URL=\"${SERVICE_URL}/sse\"
echo "============================================="
