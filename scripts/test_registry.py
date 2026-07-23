import os
import time
from google import genai

client = genai.Client(vertexai=True, project=os.environ["GOOGLE_CLOUD_PROJECT"], location="global")

def test_registry():
    agent_id = "test-agent-registry"
    try:
        client.agents.delete(id=agent_id)
        time.sleep(5)
    except:
        pass

    project_num = "181550378089" # Project number for geap-workshop-temp-1
    registry_name = f"projects/{project_num}/locations/global/services/warehouse-db"
    
    print("Testing with type: agentregistry.googleapis.com/McpServer")
    try:
        operation = client.agents.create(
            id=agent_id,
            base_agent="antigravity-preview-05-2026",
            base_environment={"type": "remote"},
            tools=[{
                "type": "agentregistry.googleapis.com/McpServer", 
                "name": registry_name
            }]
        )
        print("Success:", operation.name)
    except Exception as e:
        print("Failed:", e)

test_registry()
