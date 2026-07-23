import os
import sys
from google import genai
import google.auth

def main():
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    client = genai.Client(vertexai=True, project=project, location="global")

    print("Creating agent without base_environment...")
    operation = client.agents.create(
        id="warehouse-assistant-no-env",
        base_agent="antigravity-preview-05-2026",
        system_instruction="You are a helpful assistant.",
        tools=[
            {
                "type": "code_execution"
            }
        ]
    )
    
    print(f"Agent creation initiated: {operation.name}")
    
if __name__ == "__main__":
    main()
