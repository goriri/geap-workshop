import asyncio
import os
import sys
import json
import time
import uuid
from google import genai
import google.genai.types as genai_types
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

def save_session_trajectory(session_id: str, trajectory: dict):
    """Saves structured session trajectory log to sessions/{session_id}.json."""
    sessions_dir = "sessions"
    os.makedirs(sessions_dir, exist_ok=True)
    filepath = os.path.join(sessions_dir, f"{session_id}.json")
    with open(filepath, "w") as f:
        json.dump(trajectory, f, indent=2)
    return filepath

async def main():
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        print("Error: GOOGLE_CLOUD_PROJECT environment variable is not set.")
        sys.exit(1)

    mcp_url = os.environ.get("MCP_SERVER_URL")
    if not mcp_url:
        print("Error: MCP_SERVER_URL environment variable is not set.")
        sys.exit(1)

    # Normalize URL to the Streamable HTTP endpoint (/mcp)
    if mcp_url.endswith("/sse"):
        mcp_url = mcp_url[:-4]
    if not mcp_url.endswith("/mcp"):
        mcp_url = f"{mcp_url}/mcp"

    # Initialize or accept SESSION_ID
    session_id = os.environ.get("SESSION_ID") or f"local-session-{int(time.time())}-{uuid.uuid4().hex[:6]}"

    print(f"Initializing Gemini Client (Project: {project}, Location: global)...")
    client = genai.Client(vertexai=True, project=project, location="global")

    headers = {}
    if mcp_url.startswith("https://") and ".run.app" in mcp_url:
        try:
            print("Fetching OIDC token for Cloud Run authentication...")
            import google.auth
            from google.auth.transport.requests import Request
            import google.oauth2.id_token
            # Use base URL as audience
            audience = mcp_url.rsplit("/mcp", 1)[0]
            token = google.oauth2.id_token.fetch_id_token(Request(), audience)
            headers["Authorization"] = f"Bearer {token}"
            print("Successfully retrieved OIDC authentication token.")
        except Exception as e:
            print(f"Warning: Could not fetch OIDC token: {e}")

    print(f"Connecting to MCP Streamable HTTP server at {mcp_url}...")
    try:
        async with streamablehttp_client(url=mcp_url, headers=headers) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                print("MCP session initialized successfully!")
                
                # 1. Fetch tools from MCP server
                tools_result = await session.list_tools()
                print(f"Loaded {len(tools_result.tools)} tools from MCP database server.")
                
                # Map MCP tools to Gemini Function Declarations
                func_declarations = []
                for tool in tools_result.tools:
                    fd = genai_types.FunctionDeclaration(
                        name=tool.name,
                        description=tool.description,
                        parameters=tool.inputSchema
                    )
                    func_declarations.append(fd)

                gemini_tools = [genai_types.Tool(function_declarations=func_declarations)]
                system_instruction = (
                    "You are a warehouse management assistant. Your task is to help the user manage inventory "
                    "and orders in the warehouse. Use the tools provided by the warehouse-db MCP server to query stock, "
                    "update stock, and create orders. Always summarize your action results clearly for the user."
                )

                print("\n" + "="*60)
                print("Welcome to the Local Warehouse Manager Agent CLI Client!")
                print(f"Active Session ID: {session_id}")
                print("="*60)
                print("This interactive console allows you to chat directly with your agent.")
                print("Type 'exit' or 'quit' to end the conversation.")
                print("="*60 + "\n")

                history = []
                session_trajectory = {
                    "session_id": session_id,
                    "agent_type": "local_emulation",
                    "project_id": project,
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "turns": []
                }

                turn_count = 0
                while True:
                    try:
                        user_input = input("\nYou: ")
                        if not user_input.strip():
                            continue
                        if user_input.strip().lower() in ["exit", "quit"]:
                            print("Goodbye!")
                            break

                        turn_count += 1
                        turn_record = {
                            "turn_index": turn_count,
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "user_input": user_input,
                            "steps": [
                                {
                                    "step_type": "user_input",
                                    "content": user_input
                                }
                            ]
                        }

                        # Append user input to history
                        history.append(
                            genai_types.Content(
                                role="user",
                                parts=[genai_types.Part.from_text(text=user_input)]
                            )
                        )

                        # Loop to handle sequential/parallel function calling turns
                        while True:
                            print("Thinking...")
                            response = client.models.generate_content(
                                model="gemini-3.5-flash",
                                contents=history,
                                config=genai_types.GenerateContentConfig(
                                    tools=gemini_tools,
                                    system_instruction=system_instruction
                                )
                            )

                            # Log thought if returned
                            for candidate in (response.candidates or []):
                                for part in (candidate.content.parts or []):
                                    if getattr(part, "thought", False) and part.text:
                                        turn_record["steps"].append({
                                            "step_type": "thought",
                                            "content": part.text
                                        })

                            # If model returns a text response, print it and break the function calling loop
                            if response.text:
                                print(f"\nAgent: {response.text}")
                                history.append(response.candidates[0].content)
                                turn_record["steps"].append({
                                    "step_type": "model_output",
                                    "content": response.text
                                })
                                break

                            # If model requests function calls, execute them
                            if response.function_calls:
                                # Append the model's function call turn to conversation history
                                history.append(response.candidates[0].content)
                                
                                response_parts = []
                                for call in response.function_calls:
                                    print(f"\n[Agent is executing tool '{call.name}' with arguments {call.args} on MCP server...]")
                                    turn_record["steps"].append({
                                        "step_type": "function_call",
                                        "tool_name": call.name,
                                        "arguments": dict(call.args)
                                    })
                                    
                                    # Invoke the tool on the MCP server
                                    mcp_result = await session.call_tool(call.name, arguments=dict(call.args))
                                    
                                    # Extract result text
                                    content_texts = [item.text for item in mcp_result.content if hasattr(item, "text")]
                                    result_text = "\n".join(content_texts)
                                    print(f"[Tool Output: {result_text}]")
                                    
                                    turn_record["steps"].append({
                                        "step_type": "function_response",
                                        "tool_name": call.name,
                                        "result": result_text
                                    })

                                    # Create the function response part
                                    response_parts.append(
                                        genai_types.Part.from_function_response(
                                            name=call.name,
                                            response={"result": result_text}
                                        )
                                    )
                                
                                # Append the function responses back to history as user role turn
                                history.append(
                                    genai_types.Content(
                                        role="user",
                                        parts=response_parts
                                    )
                                )
                            else:
                                # Fallback if no text and no function calls returned
                                break

                        # Save updated session trajectory after turn
                        session_trajectory["turns"].append(turn_record)
                        log_path = save_session_trajectory(session_id, session_trajectory)
                        print(f"[Trajectory logged to {log_path}]")

                    except KeyboardInterrupt:
                        print("\nGoodbye!")
                        break
                    except Exception as e:
                        print(f"\nError in loop: {e}")

    except Exception as e:
        print(f"Failed to connect to MCP server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
