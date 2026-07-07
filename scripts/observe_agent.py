import os
import sys
import json
from google import genai

def main():
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    interaction_id = os.environ.get("INTERACTION_ID")

    if not project:
        print("Error: GOOGLE_CLOUD_PROJECT environment variable is not set.")
        sys.exit(1)

    if not interaction_id:
        print("Error: INTERACTION_ID environment variable is not set.")
        sys.exit(1)

    print(f"Initializing Gemini Client (Project: {project}, Location: global)...")
    client = genai.Client(vertexai=True, project=project, location="global")

    print(f"Fetching details for interaction: {interaction_id}...")
    try:
        interaction = client.interactions.get(id=interaction_id)
    except Exception as e:
        print(f"Failed to fetch interaction: {e}")
        sys.exit(1)

    print("\n" + "="*60)
    print(f"INTERACTION DETAILS (ID: {interaction.id})")
    print("="*60)
    print(f"Agent ID:    {interaction.agent}")
    print(f"Environment: {interaction.environment_id}")
    print(f"Status:      {interaction.status}")
    print("="*60)
    
    steps = getattr(interaction, "steps", []) or []
    if not steps:
        print("No steps found in this interaction trace.")
        return

    print(f"Trace execution flow ({len(steps)} steps):")
    print("-" * 60)

    for i, step in enumerate(steps):
        step_type = getattr(step, "type", "unknown")
        print(f"\n[Step {i+1}] Type: {step_type}")
        
        # 1. Thought / Reasoning step
        if step_type == "thought":
            content = getattr(step, "content", None)
            if content:
                print("Reasoning:")
                for part in content:
                    if hasattr(part, "text") and part.text:
                        print(f"  {part.text.strip()}")
            else:
                print("  (Empty thought content)")

        # 2. Model Output / Response step
        elif step_type == "model_output":
            content = getattr(step, "content", None)
            if content:
                print("Output Text:")
                for part in content:
                    if hasattr(part, "text") and part.text:
                        print(f"  {part.text.strip()}")

        # 3. User Input step
        elif step_type == "user_input":
            content = getattr(step, "content", None)
            if content:
                print("Input:")
                for part in content:
                    if hasattr(part, "text") and part.text:
                        print(f"  {part.text.strip()}")

        # 4. MCP Server Tool Call step
        elif step_type == "mcp_server_tool_call":
            tool_name = getattr(step, "name", "unknown")
            server_name = getattr(step, "server_name", "unknown")
            args = getattr(step, "arguments", {})
            print(f"Calling MCP Tool '{tool_name}' on server '{server_name}'...")
            print(f"  Arguments: {json.dumps(args, indent=2)}")

        # 5. MCP Server Tool Result step
        elif step_type == "mcp_server_tool_result":
            tool_name = getattr(step, "name", "unknown")
            server_name = getattr(step, "server_name", "unknown")
            result = getattr(step, "result", None)
            print(f"Received result from MCP Tool '{tool_name}' (Server: '{server_name}'):")
            if result:
                # result can be string or nested object, print as string or json
                if isinstance(result, str):
                    print(f"  Result: {result.strip()}")
                else:
                    print(f"  Result Data: {result}")
            else:
                print("  (No result payload)")

        # 6. Default fallback for other step types
        else:
            # Print serialized dump
            try:
                print(json.dumps(step.model_dump(), indent=2))
            except Exception:
                print(f"  {step}")

    print("\n" + "="*60)

if __name__ == "__main__":
    main()
