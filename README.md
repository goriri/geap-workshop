# Gemini Enterprise Agent Platform (GEAP) Warehouse Workshop

This workshop demonstrates the capabilities of the **Gemini Enterprise Agent Platform (GEAP)**. It builds a stateful **Warehouse Management Agent** that queries a Cloud SQL database through an MCP (Model Context Protocol) server running on Cloud Run, reasons over customer requests, and performs transactions.

---

## Architecture Overview

```mermaid
graph TD
    User([User CLI / Console]) <--> |1. Prompt / Interaction| GEAP[Gemini Enterprise Agent Platform]
    GEAP <--> |2. Tool Call| MCPServer[MCP Server on Cloud Run]
    MCPServer <--> |3. SQL Query / Write| CloudSQL[(Cloud SQL PostgreSQL)]
```

---

## Prerequisites

If you are running this workshop locally, ensure you have the Google Cloud CLI (`gcloud`) installed and authenticated:
```bash
gcloud auth login
gcloud auth application-default login
```

Set the project you will use for this workshop:
```bash
export GOOGLE_CLOUD_PROJECT="YOUR_PROJECT_ID"
gcloud config set project $GOOGLE_CLOUD_PROJECT
```

> [!TIP]
> **Cloud Shell Users**: If you are using **Google Cloud Shell**, you can skip running `gcloud auth login` or `gcloud auth application-default login` as you are already authenticated. You can also skip setting the project if Cloud Shell is already configured to your target project (verify by running `gcloud config get project`).

---

## GCP Project & IAM Setup

If you are using a new GCP project, you must enable the required Google Cloud APIs and ensure your user account has the appropriate permissions.

### 1. Required IAM Roles
The user account running this workshop requires the following IAM roles on the project:
* **Project IAM Admin** (`roles/resourcemanager.projectIamAdmin`) - to configure Service Account permissions.
* **Cloud Run Admin** (`roles/run.admin`) - to deploy the MCP server.
* **Cloud SQL Admin** (`roles/cloudsql.admin`) - to create and manage the PostgreSQL database.
* **Vertex AI Administrator** (`roles/aiplatform.admin`) - to create and run agents.
* **Service Usage Admin** (`roles/serviceusage.serviceUsageAdmin`) - to enable Google Cloud APIs.
* **Storage Admin** (`roles/storage.admin`) - to create storage buckets for container builds.
* **Artifact Registry Administrator** (`roles/artifactregistry.admin`) - to store the built container images.

> [!NOTE]
> If you have the **Owner** (`roles/owner`) role on the project, you already have all the necessary permissions.

### 2. Enable Required APIs
Run the following command to enable all the necessary APIs:
```bash
gcloud services enable \
    sqladmin.googleapis.com \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    aiplatform.googleapis.com \
    agentregistry.googleapis.com \
    cloudbuild.googleapis.com \
    serviceusage.googleapis.com
```

---

## 1. Setup Virtual Environment & Install Dependencies

Create and activate a python virtual environment, then install dependencies:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 2. Step 1: Create Cloud SQL DB & Seed Data

1. Run the database creation script. This script will provision a new Cloud SQL PostgreSQL instance named `warehouse-db`, create a database named `warehouse`, create tables, and seed the initial inventory data:
   ```bash
   bash scripts/create_db.sh
   ```
2. (Optional) If you want to connect to the database locally for manual queries, download and start the Cloud SQL Auth Proxy:
   ```bash
   # Download the proxy
   curl -o cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/v2.11.0/linux/amd64/cloud-sql-proxy
   chmod +x cloud-sql-proxy
   
   # Start the proxy in the background
   ./cloud-sql-proxy $GOOGLE_CLOUD_PROJECT:us-central1:warehouse-db --port 5433 &
   ```

---

## 3. Step 2: Deploy & Expose the MCP Server on Cloud Run

1. Build and deploy the FastMCP server code to Cloud Run, and set up database connection permissions:
   ```bash
   bash scripts/deploy_mcp_server.sh
   ```
   This will output the URL of your deployed service. Save and set this URL in your environment:
   ```bash
   export MCP_SERVER_URL="https://warehouse-mcp-server-xxxx-uc.a.run.app/sse"
   ```

2. Register the deployed service in the Agent Registry:
   ```bash
   python3 scripts/register_mcp_server.py
   ```

---

## 4. Step 3: Run the Warehouse Agent

Depending on your GCP organization permissions, choose **Option A (Local Emulation - Recommended)** or **Option B (Cloud Managed Agent)**:

### Option A: Local Agent Emulation (Works out-of-the-box)
Certain preview/sandbox projects contain controls that block the remote provisioning of permanent Dialogflow CX agent containers (causing `agents.create` LROs to return `ABORTED`). 

If your project is subject to these restrictions, you can run the **Local Agent Client** which uses the standard Gemini API (`gemini-3.5-flash` in location `global`) with standard tool-use definitions, calling your deployed Cloud Run MCP server directly from your workstation:
```bash
export MCP_SERVER_URL="YOUR_CLOUD_RUN_SSE_URL"
python3 scripts/local_agent.py
```

### Option B: Cloud-Managed Agent
If your project has full GEAP provisioning enablement:
1. Register the managed agent in the Agent Registry:
   ```bash
   export MCP_SERVER_URL="YOUR_CLOUD_RUN_SSE_URL"
   python3 scripts/create_agent.py
   ```
2. Interact with the registered agent statefully through the Interactions API:
   ```bash
   python3 scripts/interact_agent.py
   ```

---

## 5. Verify the Workshop Scenarios

Run the automated verification script to run the five warehouse scenarios sequentially:
1. **List inventory**: Queries and lists initial warehouse items.
2. **Query product stock**: Checks inventory details for product ID 3 (Antigravity Boots).
3. **Invalid order**: Rejects customer order exceeding stock.
4. **Valid order**: Places a valid customer order, reducing database stock to 0.
5. **Re-check stock**: Confirms the database inventory was decremented correctly.

To run verification in **Local Emulation** mode:
```bash
export MCP_SERVER_URL="YOUR_CLOUD_RUN_SSE_URL"
python3 scripts/verify_workshop.py
```

To run verification using the **Cloud Managed Agent** (Option B):
```bash
python3 scripts/verify_workshop.py --remote
```

---

## 6. Step 4: Observability & Agent Management

- **Observability**: When running the Cloud Managed Agent (Option B), call the observability script to retrieve and view the step-by-step reasoning steps and raw database tool logs of the last order transaction:
  ```bash
  python3 scripts/observe_agent.py
  ```
- **Console Monitoring**: You can also monitor your agent's live health, tool executions, and billing details directly within the Google Cloud Console under the **Gemini Enterprise -> Agent Platform** menu.

---

## 7. Step 5: Connect the Agent to Gemini Enterprise

To expose your custom warehouse manager agent to corporate users in the Gemini Enterprise workspace:
1. Open the Google Cloud Console and navigate to **Gemini Enterprise**.
2. Click on the target **App** you want to attach the agent to.
3. Select **Agents** in the left navigation sidebar.
4. Click **Add agent** and choose the **A2A (Agent-to-Agent)** card.
5. Paste the Agent Card JSON, replacing the `LOCATION` and `RESOURCE_NAME` parameters with your agent's deployment details.
6. Provide OAUTH authorization credentials in the form, and click **Finish**.
7. Users can now query your warehouse DB by writing natural language queries in Gemini!

---

## 8. Cleanup

To delete all Cloud SQL instances, Cloud Run services, and Agent registry entries created during the workshop:
```bash
bash scripts/cleanup.sh
```
