#!/bin/bash

# Ensure project is set
if [ -z "$GOOGLE_CLOUD_PROJECT" ]; then
  echo "Error: GOOGLE_CLOUD_PROJECT environment variable is not set."
  exit 1
fi

echo "============================================="
echo "Cleaning up GEAP Workshop resources..."
echo "============================================="

# 1. Delete the Managed Agent via Python Client
echo "Deleting managed agent 'warehouse-manager'..."
python3 -c "
from google import genai
import os
try:
    client = genai.Client(vertexai=True, project=os.environ['GOOGLE_CLOUD_PROJECT'], location='global')
    client.agents.delete(id='warehouse-manager')
    print('Successfully deleted agent.')
except Exception as e:
    print('Agent deletion skipped or failed:', e)
"

# 2. Delete Cloud Run Service
echo "Deleting Cloud Run service 'warehouse-mcp-server'..."
gcloud run services delete warehouse-mcp-server \
    --region=us-central1 \
    --quiet \
    --project=$GOOGLE_CLOUD_PROJECT

# 3. Delete Cloud SQL Instance
echo "Deleting Cloud SQL instance 'warehouse-db' (this can take a few minutes)..."
gcloud sql instances delete warehouse-db \
    --quiet \
    --project=$GOOGLE_CLOUD_PROJECT

echo "============================================="
echo "Cleanup complete!"
echo "============================================="
