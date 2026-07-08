import os
import sys
import time
from google import genai
import google.oauth2.id_token
from google.auth.transport.requests import Request

def main():
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        print("Error: GOOGLE_CLOUD_PROJECT environment variable is not set.")
        sys.exit(1)

    mcp_url = os.environ.get("MCP_SERVER_URL")
    if not mcp_url:
        print("Error: MCP_SERVER_URL environment variable is not set.")
        sys.exit(1)
        
    if mcp_url.endswith("/sse"):
        mcp_url = mcp_url[:-4]
        
    audience = mcp_url
    sse_url = f"{mcp_url}/sse"

    agent_id = "warehouse-manager-net-only"
    print(f"Initializing Gemini Client (Project: {project}, Location: global)...")
    client = genai.Client(vertexai=True, project=project, location="global", http_options={"timeout": 1200000})

    try:
        agent = client.agents.get(id=agent_id)
        agent_name = agent.name
    except Exception as e:
        print(f"Error fetching agent '{agent_id}': {e}")
        sys.exit(1)

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
            
            # Dynamically fetch a fresh OIDC token for the Cloud Run MCP Server
            print("[Fetching fresh OIDC token for MCP Server...]")
            token = google.oauth2.id_token.fetch_id_token(Request(), audience)
            
            # Send message to agent, injecting the tools with the fresh token
            interaction = client.interactions.create(
                agent=agent_name,
                input=user_input,
                environment=environment,
                background=True,
                timeout=600.0,
                tools=[{
                    "type": "mcp_server",
                    "name": "warehouse-db",
                    "url": sse_url,
                    "headers": {"Authorization": f"Bearer {token}"}
                }]
            )
            print(f"[Interaction ID: {interaction.id}]")
            
            # Poll for completion
            while True:
                interaction = client.interactions.get(id=interaction.id)
                print(f"[Status: {interaction.status}]", end="\r", flush=True)
                if interaction.status in ["SUCCEEDED", "FAILED", "CANCELLED", "COMPLETED", "REQUIRES_ACTION"]:
                    break
                time.sleep(1)
            
            # Print response
            print(f"\nAgent: {interaction.output_text if hasattr(interaction, 'output_text') else getattr(interaction, 'outputs', 'No output')}")
            
            # Update environment to use the session ID for the next turn
            if hasattr(interaction, 'environment_id') and interaction.environment_id:
                environment = interaction.environment_id
            
            # Print interaction ID for debugging/observability
            print(f"[Interaction ID: {interaction.id}]")
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except EOFError:
            break
        except Exception as e:
            print(f"\nError: {e}")
            print("Please ensure your Agent is created and your MCP server is reachable.")
            break

if __name__ == "__main__":
    main()
