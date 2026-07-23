import os
import json
import urllib.request
import google.auth
import google.auth.transport.requests

credentials, _ = google.auth.default()
auth_req = google.auth.transport.requests.Request()
credentials.refresh(auth_req)

url = f"https://aiplatform.googleapis.com/v1beta1/projects/{os.environ['GOOGLE_CLOUD_PROJECT']}/locations/global/agents"
req = urllib.request.Request(url, method="POST")
req.add_header("Authorization", f"Bearer {credentials.token}")
req.add_header("Content-Type", "application/json")

payload = {
    "base_agent": "antigravity-preview-05-2026",
    "tools": [
        {
            "type": "mcp_server",
            "name": "projects/181550378089/locations/global/services/warehouse-db"
        }
    ],
    "base_environment": {
        "type": "remote"
    }
}

try:
    with urllib.request.urlopen(req, data=json.dumps(payload).encode("utf-8")) as response:
        print("Success!")
        print(response.read().decode())
except urllib.error.HTTPError as e:
    print(f"Error {e.code}: {e.read().decode()}")

