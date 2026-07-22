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
    if not mcp_url.endswith("/mcp"):
        mcp_url = f"{mcp_url}/mcp"
        
    audience = mcp_url
    sse_url = mcp_url

    import getpass
    username = getpass.getuser()
    agent_id = f"{username}-warehouse-manager"
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
    previous_interaction_id = None

    while True:
        try:
            user_input = input("\nYou: ")
            if not user_input.strip():
                continue
            if user_input.strip().lower() in ["exit", "quit"]:
                print("Goodbye!")
                break

            print("\nThinking...")
            
            # Send message to agent, relying on agent's static tools configuration
            interaction = client.interactions.create(
                agent=agent_name,
                input=user_input,
                environment=environment,
                previous_interaction_id=previous_interaction_id,
                background=True,
                timeout=600.0,
            )
            print(f"[Interaction ID: {interaction.id}]")

            # Poll for completion (API returns lowercase statuses, e.g. "completed")
            while True:
                interaction = client.interactions.get(id=interaction.id)
                status = (interaction.status or "").lower()
                print(f"[Status: {status}]   ", end="\r", flush=True)
                if status in ["succeeded", "failed", "cancelled", "completed", "requires_action"]:
                    break
                time.sleep(1)

            # Print response
            print(f"\nAgent: {interaction.output_text or '(no output)'}")

            # Reuse the sandbox environment and thread conversation history into the next turn
            if getattr(interaction, "environment_id", None):
                environment = interaction.environment_id
            previous_interaction_id = interaction.id
            
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
