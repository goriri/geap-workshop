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
echo "Deleting managed agent..."
python3 -c "
from google import genai
import os
import getpass
try:
    username = getpass.getuser()
    client = genai.Client(vertexai=True, project=os.environ['GOOGLE_CLOUD_PROJECT'], location='global')
    client.agents.delete(id=f'{username}-warehouse-manager')
    print('Successfully deleted agent.')
except Exception as e:
    print('Agent deletion skipped or failed:', e)
"

# 2. Delete Deployed Reasoning Engines (ADK & LangChain Agents)
echo "Deleting user's deployed Reasoning Engines in us-central1..."
venv/bin/python3 -c "
import os
import getpass
import google.auth
from google.cloud import aiplatform
from vertexai.preview import reasoning_engines
try:
    project = os.environ.get('GOOGLE_CLOUD_PROJECT')
    if not project:
        raise ValueError('GOOGLE_CLOUD_PROJECT env var is not set.')
    username = getpass.getuser()
    aiplatform.init(project=project, location='us-central1')
    engines = reasoning_engines.ReasoningEngine.list()
    for e in engines:
        if e.display_name.startswith(f'{username}-'):
            print(f'Deleting Reasoning Engine: {e.resource_name} ({e.display_name})')
            e.delete()
except Exception as e:
    print('Reasoning Engine deletion skipped or failed:', e)
"

# 3. Delete Cloud Run Service
echo "Deleting Cloud Run service '${USER}-warehouse-mcp-server'..."
gcloud run services delete "${USER}-warehouse-mcp-server" \
    --region=us-central1 \
    --quiet \
    --project=$GOOGLE_CLOUD_PROJECT

# 4. Delete Cloud SQL Instance
echo "Deleting Cloud SQL instance '${USER}-warehouse-db' (this can take a few minutes)..."
gcloud sql instances delete "${USER}-warehouse-db" \
    --quiet \
    --project=$GOOGLE_CLOUD_PROJECT

echo "============================================="
echo "Cleanup complete!"
echo "============================================="
