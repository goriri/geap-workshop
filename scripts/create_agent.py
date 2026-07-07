import os
import sys
import time
import json
import urllib.request
import google.auth
import google.auth.transport.requests
from google import genai

def get_operation_status(operation_name: str):
    credentials, _ = google.auth.default()
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    
    url = f"https://aiplatform.googleapis.com/v1beta1/{operation_name}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {credentials.token}")
    
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        # Read the error body if available
        try:
            err_body = e.read().decode()
            return {"error": {"code": e.code, "message": err_body}}
        except:
            return {"error": {"code": e.code, "message": str(e)}}
    except Exception as e:
        return {"error": {"code": 500, "message": str(e)}}

def main():
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    mcp_url = os.environ.get("MCP_SERVER_URL")

    if not project:
        print("Error: GOOGLE_CLOUD_PROJECT environment variable is not set.")
        sys.exit(1)

    if not mcp_url:
        print("Error: MCP_SERVER_URL environment variable is not set.")
        sys.exit(1)

    agent_id = "warehouse-manager"

    print(f"Initializing Gemini Client for Vertex AI (Project: {project}, Location: global)...")
    client = genai.Client(vertexai=True, project=project, location="global", http_options={"timeout": 600000})

    # 1. Clean up existing agent if it exists
    print(f"Attempting to delete any existing agent '{agent_id}' to start fresh...")
    try:
        # Note: If the agent is in CREATING state, delete will fail. We'll try anyway.
        delete_op = client.agents.delete(id=agent_id)
        print(f"Agent deletion operation started: {delete_op.name}")
        while True:
            status = get_operation_status(delete_op.name)
            if not status or "error" in status:
                print(f"Error checking deletion status: {status}")
                break
            if status.get("done"):
                print("Agent deletion completed.")
                break
            print("Waiting for deletion to complete...")
            time.sleep(10)
    except Exception as e:
        print(f"Agent deletion skipped or not found: {e}")

    # 2. Register/Create the Agent
    print(f"Creating managed agent '{agent_id}'...")
    try:
        operation = client.agents.create(
            id=agent_id,
            base_agent="antigravity-preview-05-2026",
            description="A managed agent for checking warehouse inventory and processing orders.",
            system_instruction=(
                "You are a warehouse management assistant. Your task is to help the user manage inventory "
                "and orders in the warehouse. Use the tools provided by the warehouse_db MCP server to query stock, "
                "update stock, and create orders. Always summarize your action results clearly for the user."
            ),
            tools=[
                {
                    "type": "mcp_server",
                    "name": "warehouse-db",
                    "url": mcp_url
                }
            ],
            timeout=600
        )
        print(f"Agent creation operation started: {operation.name}")
        operation_name = operation.name
    except Exception as e:
        print(f"Failed to start agent creation: {e}")
        sys.exit(1)

    # 3. Poll for operation completion using direct REST requests
    print("Waiting for creation operation to complete...")
    start_time = time.time()
    while True:
        status = get_operation_status(operation_name)
        if not status:
            print("Failed to fetch operation status, retrying in 10 seconds...")
            time.sleep(10)
            continue
            
        if "error" in status:
            print("\n--- Operation Failed ---")
            print(f"Status response: {status}")
            print("------------------------")
            sys.exit(1)
            
        if status.get("done"):
            # Check if there is an error in the response metadata/result
            op_error = status.get("error")
            if op_error:
                print("\n--- Operation Completed with Error ---")
                print(f"Code: {op_error.get('code')}")
                print(f"Message: {op_error.get('message')}")
                print("--------------------------------------")
                sys.exit(1)
            else:
                print("Agent creation operation completed successfully!")
                break
        
        elapsed = int(time.time() - start_time)
        print(f"Operation still running (elapsed: {elapsed}s), waiting 10 seconds...")
        time.sleep(10)

    # Verify agent exists and get its details
    try:
        retrieved_agent = client.agents.get(id=agent_id)
        print(f"\nSuccessfully verified agent: {retrieved_agent.name}")
    except Exception as e:
        print(f"Error verifying agent after creation: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()


