import asyncio
import os
import sys
from google import genai
import google.genai.types as genai_types
from mcp import ClientSession
from mcp.client.sse import sse_client

async def main():
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        print("Error: GOOGLE_CLOUD_PROJECT environment variable is not set.")
        sys.exit(1)

    mcp_url = os.environ.get("MCP_SERVER_URL", "https://warehouse-mcp-server-r2vgs5vdkq-uc.a.run.app/sse")
    
    print(f"Initializing Gemini Client (Project: {project}, Location: global)...")
    client = genai.Client(vertexai=True, project=project, location="global")

    print(f"Connecting to MCP SSE server at {mcp_url}...")
    try:
        async with sse_client(url=mcp_url) as (read_stream, write_stream):
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
                print("="*60)
                print("This interactive console allows you to chat directly with your agent.")
                print("Type 'exit' or 'quit' to end the conversation.")
                print("="*60 + "\n")

                history = []

                while True:
                    try:
                        user_input = input("\nYou: ")
                        if not user_input.strip():
                            continue
                        if user_input.strip().lower() in ["exit", "quit"]:
                            print("Goodbye!")
                            break

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

                            # If model returns a text response, print it and break the function calling loop
                            if response.text:
                                print(f"\nAgent: {response.text}")
                                history.append(response.candidates[0].content)
                                break

                            # If model requests function calls, execute them
                            if response.function_calls:
                                # Append the model's function call turn to conversation history
                                history.append(response.candidates[0].content)
                                
                                response_parts = []
                                for call in response.function_calls:
                                    print(f"\n[Agent is executing tool '{call.name}' with arguments {call.args} on MCP server...]")
                                    
                                    # Invoke the tool on the MCP server
                                    mcp_result = await session.call_tool(call.name, arguments=dict(call.args))
                                    
                                    # Extract result text
                                    content_texts = [item.text for item in mcp_result.content if hasattr(item, "text")]
                                    result_text = "\n".join(content_texts)
                                    print(f"[Tool Output: {result_text}]")
                                    
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
