import os
import sys
from google import genai
import google.auth
import urllib.request
import json
import google.auth.transport.requests

def main():
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    client = genai.Client(vertexai=True, project=project, location="global")

    print("Interacting with warehouse-assistant-no-mcp...")
    
    response = client.interactions.create(
        agent=f"projects/{project}/locations/global/agents/warehouse-assistant-no-mcp",
        messages=[
            {"role": "user", "content": "Can you list all the inventory in the warehouse database?"}
        ]
    )
    
    print("\nResponse:")
    if hasattr(response, "candidates") and response.candidates:
        print(response.candidates[0].content)
    else:
        print(response)

if __name__ == "__main__":
    main()
