import os
import sys
import time
from google import genai

def main():
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        print("Error: GOOGLE_CLOUD_PROJECT environment variable is not set.")
        sys.exit(1)

    agent_id = "warehouse-manager"
    print(f"Initializing Gemini Client (Project: {project}, Location: global)...")
    client = genai.Client(vertexai=True, project=project, location="global", http_options={"timeout": 1200000})

    print("\n" + "="*60)
    print("Welcome to the GEAP Warehouse Manager Agent CLI Client!")
    print("="*60)
    print("This interactive console allows you to chat directly with your managed agent.")
    print("Type 'exit' or 'quit' to end the conversation.")
    print("All conversation history is maintained statefully using GEAP Sessions.")
    print("="*60 + "\n")

    environment = "remote"

    while True:
        try:
            user_input = input("\nYou: ")
            if not user_input.strip():
                continue
            if user_input.strip().lower() in ["exit", "quit"]:
                print("Goodbye!")
                break

            print("\nThinking...")
            
            # Send message to agent
            interaction = client.interactions.create(
                agent=f"projects/{project}/locations/global/agents/{agent_id}",
                input=user_input,
                environment=environment,
                background=True
            )
            
            # Poll for completion
            while True:
                interaction = client.interactions.get(id=interaction.id)
                if interaction.status in ["SUCCEEDED", "FAILED", "CANCELLED"]:
                    break
                time.sleep(1)
            
            # Print response
            print(f"\nAgent: {interaction.output_text}")
            
            # Update environment to use the session ID for the next turn
            environment = interaction.environment_id
            
            # Print interaction ID for debugging/observability
            print(f"[Interaction ID: {interaction.id}]")
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")
            print("Please ensure your Agent is created and your MCP server is reachable.")

if __name__ == "__main__":
    main()
