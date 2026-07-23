import os
import httpx
from unittest.mock import patch
from google import genai
import json

client = genai.Client(vertexai=True, project=os.environ["GOOGLE_CLOUD_PROJECT"], location="global")

original_post = httpx.Client.post

def mock_post(self, url, **kwargs):
    print("URL:", url)
    print("PAYLOAD:", json.dumps(json.loads(kwargs.get("content", "{}")), indent=2))
    return httpx.Response(200, json={"name": "dummy/operations/123"})

with patch("httpx.Client.post", mock_post):
    try:
        client.agents.create(
            id="test-agent",
            base_agent="antigravity-preview-05-2026",
            base_environment={"type": "remote"},
            tools=[{
                "type": "mcp_server", 
                "name": "test-mcp",
                "url": "https://example.com"
            }]
        )
    except Exception as e:
        print(e)

