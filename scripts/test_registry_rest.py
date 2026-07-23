import os
import subprocess
import urllib.request
import json
import time

def test_rest():
    project_num = "181550378089"
    token = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
    
    agent_id = "test-agent-rest-1"
    url = f"https://aiplatform.googleapis.com/v1beta1/projects/{project_num}/locations/global/agents?agentId={agent_id}"
    
    payload = {
        "model": "projects/181550378089/locations/global/baseAgents/antigravity-preview-05-2026",
        "baseEnvironment": {"type": "remote"},
        "tools": [
            {
                "type": "agentregistry.googleapis.com/McpServer",
                "name": f"projects/{project_num}/locations/global/services/warehouse-db"
            }
        ]
    }
    
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    
    try:
        res = urllib.request.urlopen(req)
        print("Success:", res.read().decode())
    except Exception as e:
        if hasattr(e, 'read'):
            print("Failed:", e.read().decode())
        else:
            print("Failed:", str(e))

test_rest()
