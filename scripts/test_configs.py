import os
import time
import json
import urllib.request
import google.auth
import google.auth.transport.requests
from google import genai
import threading

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
        try:
            return {"error": {"code": e.code, "message": e.read().decode()}}
        except:
            return {"error": {"code": e.code, "message": str(e)}}
    except Exception as e:
        return {"error": {"code": 500, "message": str(e)}}

def wait_for_op(operation_name):
    print(f"Waiting for {operation_name}...")
    while True:
        status = get_operation_status(operation_name)
        if not status:
            time.sleep(5)
            continue
        if "error" in status and "message" in status["error"]:
            pass
        if status.get("done"):
            return status
        time.sleep(5)

def test_config(name, kwargs):
    print(f"Testing config: {name}")
    client = genai.Client(vertexai=True, project=os.environ["GOOGLE_CLOUD_PROJECT"], location="global")
    agent_id = f"test-{name}"
    
    try:
        op = client.agents.delete(id=agent_id)
        if op and hasattr(op, 'name'):
            wait_for_op(op.name)
    except:
        pass
        
    try:
        print(f"Creating {agent_id}...")
        operation = client.agents.create(
            id=agent_id,
            base_agent="antigravity-preview-05-2026",
            description="Test agent",
            system_instruction="You are a test agent.",
            **kwargs
        )
        res = wait_for_op(operation.name)
        if "error" in res:
            print(f"Result for {name}: FAILED - {res['error']}")
        else:
            print(f"Result for {name}: SUCCESS")
            client.agents.delete(id=agent_id)
    except Exception as e:
        print(f"Result for {name}: FAILED - Exception: {e}")

configs = [
    ("no-mcp-no-net", {}),
    ("no-mcp-with-net", {"base_environment": {"network": {"allowlist": [{"domain": "*"}]}}}),
    ("with-mcp-no-net", {"tools": [{"type": "mcp_server", "name": "test-mcp", "url": "https://example.com"}]}),
    ("with-mcp-with-net", {"tools": [{"type": "mcp_server", "name": "test-mcp", "url": "https://example.com"}], "base_environment": {"network": {"allowlist": [{"domain": "*"}]}}}),
]

threads = []
for name, kw in configs:
    t = threading.Thread(target=test_config, args=(name, kw))
    t.start()
    threads.append(t)

for t in threads:
    t.join()
