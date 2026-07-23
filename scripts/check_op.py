import json
import urllib.request
import google.auth
import google.auth.transport.requests

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

print(get_operation_status("projects/181550378089/locations/global/agents/warehouse-assistant-no-mcp/operations/7700369211989688320"))
