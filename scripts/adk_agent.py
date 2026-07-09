import asyncio
import os
import sys
from google import genai
import google.genai.types as genai_types
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

class WarehouseAgentReasoningEngine:
    """Vertex AI Reasoning Engine agent for managing warehouse database via MCP."""
    
    def __init__(self, mcp_url: str):
        self.mcp_url = mcp_url

    def set_up(self):
        """Initializes genai clients. Runs on container startup."""
        # We must initialize the client inside set_up because the client object
        # cannot be pickled/serialized during deployment.
        project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        self.client = genai.Client(vertexai=True, project=project, location="global")

    async def _async_query(self, user_input: str) -> str:
        """Internal helper to execute the agent loop asynchronously."""
        # Standardize route format
        mcp_endpoint = self.mcp_url
        if mcp_endpoint.endswith("/sse"):
            mcp_endpoint = mcp_endpoint[:-4]
        if not mcp_endpoint.endswith("/mcp"):
            mcp_endpoint = f"{mcp_endpoint}/mcp"

        try:
            async with streamablehttp_client(mcp_endpoint) as streams:
                read_stream, write_stream = streams[0], streams[1]
                
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    
                    # 1. Fetch tools dynamically from the MCP server
                    tools_result = await session.list_tools()
                    
                    # 2. Map MCP tools to Gemini function declarations
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

                    # Initialize conversation history
                    history = [
                        genai_types.Content(
                            role="user",
                            parts=[genai_types.Part.from_text(text=user_input)]
                        )
                    ]

                    # 3. Model call and tool execution loop (supports multi-turn reasoning)
                    for _ in range(5):  # Max 5 reasoning steps
                        response = self.client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=history,
                            config=genai_types.GenerateContentConfig(
                                tools=gemini_tools,
                                system_instruction=system_instruction
                            )
                        )

                        if response.text:
                            return response.text

                        if response.function_calls:
                            # Append model's function call turn to history
                            history.append(response.candidates[0].content)
                            
                            response_parts = []
                            for call in response.function_calls:
                                # Call the tool on the MCP server
                                mcp_result = await session.call_tool(call.name, arguments=dict(call.args))
                                
                                # Gather response text
                                content_texts = [item.text for item in mcp_result.content if hasattr(item, "text")]
                                result_text = "\n".join(content_texts)
                                
                                response_parts.append(
                                    genai_types.Part.from_function_response(
                                        name=call.name,
                                        response={"result": result_text}
                                    )
                                )
                            
                            # Append function responses back to history as user turn
                            history.append(
                                genai_types.Content(
                                    role="user",
                                    parts=response_parts
                                )
                            )
                        else:
                            break
                            
                    return "Error: Agent got stuck in a reasoning loop without returning a text response."

        except Exception as e:
            return f"Error executing agent query: {str(e)}"

    async def query(self, query: str) -> str:
        """Main endpoint called by Vertex AI Reasoning Engine query API."""
        return await self._async_query(query)


# Deploy and Local Test Entry Point
def deploy_agent(project_id: str, location: str, mcp_url: str, staging_bucket: str):
    from google.cloud import aiplatform
    from vertexai import agent_engines
    
    print(f"Initializing aiplatform (Project: {project_id}, Location: {location})...")
    aiplatform.init(project=project_id, location=location, staging_bucket=staging_bucket)
    
    # Instantiate class
    agent_instance = WarehouseAgentReasoningEngine(mcp_url=mcp_url)
    
    print("Deploying Reasoning Engine to Vertex AI...")
    try:
        # Deploy using agent_engines.create
        reasoning_engine = agent_engines.create(
            agent_engine=agent_instance,
            requirements=[
                "google-cloud-aiplatform",
                "google-genai",
                "mcp>=0.1.0",
                "httpx>=0.20.0",
                "anyio"
            ],
            display_name="warehouse-assistant-adk",
            extra_packages=[],
            env_vars={
                "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
                "OTEL_SEMCONV_STABILITY_OPT_IN": "gen_ai_latest_experimental",
                "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "EVENT_ONLY",
            }
        )
        print("\n====================================================")
        print("Reasoning Engine Deployed Successfully!")
        print(f"Resource Name: {reasoning_engine.resource_name}")
        print("====================================================")
        return reasoning_engine.resource_name
    except Exception as e:
        print(f"Deployment failed: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    mcp_url = os.environ.get("MCP_SERVER_URL", "https://warehouse-mcp-server-mjog4mq5za-uc.a.run.app")
    staging_bucket = os.environ.get("STAGING_BUCKET") # Reasoning Engine requires a staging Cloud Storage bucket to upload pickled code
    
    if len(sys.argv) > 1 and sys.argv[1] == "--deploy":
        if not project:
            print("Error: GOOGLE_CLOUD_PROJECT is required for deployment.")
            sys.exit(1)
        if not staging_bucket:
            # Check if we can use a default staging bucket name
            staging_bucket = f"gs://{project}-vertex-staging"
            print(f"Using default staging bucket: {staging_bucket}")
            
        deploy_agent(project, "us-central1", mcp_url, staging_bucket)
    else:
        # Run local test
        print("Running local verification of the Reasoning Engine class...")
        if not project:
            # For local mock run, set a fake project ID if not set
            os.environ["GOOGLE_CLOUD_PROJECT"] = "geap-workshop-temp-1"
            
        agent = WarehouseAgentReasoningEngine(mcp_url=mcp_url)
        agent.set_up()
        
        test_query = "What products are currently in stock?"
        print(f"Querying local agent: '{test_query}'...")
        response = asyncio.run(agent.query(test_query))
        print(f"\nAgent Response:\n{response}")

if __name__ == "__main__":
    main()
