import os
import sys
import json
import urllib.request
from google import genai
from google.genai import types
import google.auth
import google.auth.transport.requests

client = genai.Client(vertexai=True, project=os.environ["GOOGLE_CLOUD_PROJECT"], location="global")

print(f"Creating remote agent with Client-Side function declarations...")

operation = client.agents.create(
    id="warehouse-assistant-no-mcp-v2",
    base_agent="antigravity-preview-05-2026",
    description="An AI assistant that can manage a warehouse inventory and create customer orders.",
    system_instruction="You are a helpful warehouse assistant. You can look up inventory and create orders. When asked to create an order, always check the stock first. If the stock is available, create the order and tell the user the new stock level.",
    tools=[]
)

print(f"Agent creation initiated: {operation.name}")

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
    except Exception as e:
        print(f"Error fetching operation status: {e}")
        return None

import time
print("Waiting for creation to complete (this might take a few minutes)...")
while True:
    status = get_operation_status(operation.name)
    if not status:
        time.sleep(5)
        continue
    
    if status.get("done"):
        if "error" in status:
            print(f"Agent creation failed: {json.dumps(status['error'], indent=2)}")
        else:
            print("Agent created successfully!")
            print(json.dumps(status.get("response", {}), indent=2))
        break
        
    print(".", end="", flush=True)
    time.sleep(5)
