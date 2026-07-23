import os
import time
from google import genai

client = genai.Client(vertexai=True, project=os.environ["GOOGLE_CLOUD_PROJECT"], location="global")
agent_id = "1398451796938063872"

try:
    print(f"Interacting with agent {agent_id}...")
    interaction = client.interactions.create(
        agent=f"projects/{os.environ['GOOGLE_CLOUD_PROJECT']}/locations/global/agents/{agent_id}",
        input="List the inventory.",
        background=True
    )
    print("Waiting...")
    while True:
        interaction = client.interactions.get(id=interaction.id)
        if interaction.status in ["SUCCEEDED", "FAILED", "CANCELLED"]:
            break
        time.sleep(1)
        
    print(f"Status: {interaction.status}")
    print(f"Agent responded: {getattr(interaction, 'output_text', 'No output text')}")
except Exception as e:
    print(f"Error: {e}")

