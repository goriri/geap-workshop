import asyncio
import os
import sys
import time
import uuid
import json
from google import genai
import google.genai.types as genai_types
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

def save_session_file(session_id: str, session_data: dict):
    try:
        os.makedirs("/tmp/sessions", exist_ok=True)
        filepath = f"/tmp/sessions/{session_id}.json"
        with open(filepath, "w") as f:
            json.dump({
                "session_id": session_data.get("session_id"),
                "created_at": session_data.get("created_at"),
                "turns": session_data.get("turns", [])
            }, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save session to file: {e}")

def load_session_file(session_id: str) -> dict:
    try:
        filepath = f"/tmp/sessions/{session_id}.json"
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return None

class WarehouseAgentReasoningEngine:
    """Vertex AI Reasoning Engine agent with OpenTelemetry Tracing & Session Logging."""
    
    def __init__(self, mcp_url: str):
        self.mcp_url = mcp_url
        self.sessions = {}
        self.tracer = None

    def set_up(self):
        """Initializes genai clients and OpenTelemetry GCP Cloud Trace exporter."""
        project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        self.client = genai.Client(vertexai=True, project=project, location="global")
        if not hasattr(self, "sessions") or self.sessions is None:
            self.sessions = {}

        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter

            provider = trace.get_tracer_provider()
            if not hasattr(provider, "add_span_processor"):
                provider = TracerProvider()
                processor = BatchSpanProcessor(CloudTraceSpanExporter(project_id=project))
                provider.add_span_processor(processor)
                trace.set_tracer_provider(provider)

            self.tracer = trace.get_tracer("warehouse_adk_agent")
            print("Successfully initialized OpenTelemetry GCP Cloud Trace exporter.")
        except Exception as e:
            print(f"Warning: OpenTelemetry tracer initialization skipped: {e}")
            self.tracer = None

    def create_session(self, session_id: str = None) -> str:
        """Creates a new session and returns the session_id."""
        if not session_id:
            session_id = f"adk-session-{int(time.time())}-{uuid.uuid4().hex[:6]}"
        if session_id not in self.sessions:
            disk_sess = load_session_file(session_id)
            if disk_sess:
                self.sessions[session_id] = {
                    "session_id": disk_sess["session_id"],
                    "created_at": disk_sess["created_at"],
                    "history": [],
                    "turns": disk_sess.get("turns", [])
                }
            else:
                self.sessions[session_id] = {
                    "session_id": session_id,
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "history": [],
                    "turns": []
                }
        return session_id

    def get_session(self, session_id: str) -> dict:
        """Retrieves session metadata, conversation history, and trajectory steps."""
        if session_id not in self.sessions:
            disk_sess = load_session_file(session_id)
            if disk_sess:
                return disk_sess
            return {"error": f"Session '{session_id}' not found.", "session_id": session_id, "turns": []}
        sess = self.sessions[session_id]
        return {
            "session_id": sess["session_id"],
            "created_at": sess["created_at"],
            "total_turns": len(sess["turns"]),
            "turns": sess["turns"]
        }

    def list_sessions(self) -> list:
        """Lists all active session summaries."""
        return [
            {
                "session_id": sid,
                "created_at": sdata["created_at"],
                "total_turns": len(sdata["turns"])
            }
            for sid, sdata in self.sessions.items()
        ]

    async def _async_query(self, user_input: str, session_id: str = None) -> dict:
        """Internal helper to execute the agent reasoning loop and record session trajectory."""
        session_id = self.create_session(session_id)
        sess = self.sessions[session_id]

        mcp_endpoint = self.mcp_url
        if mcp_endpoint.endswith("/sse"):
            mcp_endpoint = mcp_endpoint[:-4]
        if not mcp_endpoint.endswith("/mcp"):
            mcp_endpoint = f"{mcp_endpoint}/mcp"

        turn_index = len(sess["turns"]) + 1
        turn_record = {
            "turn_index": turn_index,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "user_input": user_input,
            "steps": [
                {
                    "step_type": "user_input",
                    "content": user_input
                }
            ]
        }

        mcp_headers = {}
        if ".run.app" in mcp_endpoint:
            try:
                import google.oauth2.id_token
                from google.auth.transport.requests import Request

                audience = mcp_endpoint.split("/mcp")[0].split("/sse")[0]
                token = google.oauth2.id_token.fetch_id_token(Request(), audience)
                if token:
                    mcp_headers["Authorization"] = f"Bearer {token}"
                    try:
                        import jwt
                        decoded = jwt.decode(token, options={"verify_signature": False})
                        print(f"OIDC Token Claims: email={decoded.get('email')}, sub={decoded.get('sub')}, aud={decoded.get('aud')}")
                    except Exception:
                        print(f"Token length: {len(token)}")
                    print(f"Successfully fetched OIDC ID token for audience '{audience}'")
            except Exception as e:
                print(f"Warning: Could not fetch OIDC ID token: {e}")

        async def run_loop():
            async with streamablehttp_client(mcp_endpoint, headers=mcp_headers) as streams:
                read_stream, write_stream = streams[0], streams[1]
                
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    
                    tools_result = await session.list_tools()
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
                        "update stock, and create orders. Always summarize your action results clearly for the user. "
                        "You must NEVER update stock level using update_stock to satisfy an order; reject the order instead. "
                        "When asked about product stock or details, refer to previous conversation history or call get_product_stock/list_inventory directly."
                    )

                    sess["history"].append(
                        genai_types.Content(
                            role="user",
                            parts=[genai_types.Part.from_text(text=user_input)]
                        )
                    )

                    final_response_text = ""
                    for step_idx in range(5):
                        response = self.client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=sess["history"],
                            config=genai_types.GenerateContentConfig(
                                tools=gemini_tools,
                                system_instruction=system_instruction
                            )
                        )

                        for candidate in (response.candidates or []):
                            for part in (candidate.content.parts or []):
                                if getattr(part, "thought", False) and part.text:
                                    turn_record["steps"].append({
                                        "step_type": "thought",
                                        "content": part.text
                                    })

                        if response.text:
                            final_response_text = response.text
                            sess["history"].append(response.candidates[0].content)
                            turn_record["steps"].append({
                                "step_type": "model_output",
                                "content": final_response_text
                            })
                            break

                        if response.function_calls:
                            sess["history"].append(response.candidates[0].content)
                            response_parts = []
                            
                            for call in response.function_calls:
                                turn_record["steps"].append({
                                    "step_type": "function_call",
                                    "tool_name": call.name,
                                    "arguments": dict(call.args)
                                })
                                
                                mcp_result = await session.call_tool(call.name, arguments=dict(call.args))
                                content_texts = [item.text for item in mcp_result.content if hasattr(item, "text")]
                                result_text = "\n".join(content_texts)
                                
                                turn_record["steps"].append({
                                    "step_type": "function_response",
                                    "tool_name": call.name,
                                    "result": result_text
                                })

                                response_parts.append(
                                    genai_types.Part.from_function_response(
                                        name=call.name,
                                        response={"result": result_text}
                                    )
                                )
                            
                            sess["history"].append(
                                genai_types.Content(
                                    role="user",
                                    parts=response_parts
                                )
                            )
                        else:
                            break
                            
                    if not final_response_text:
                        final_response_text = "Error: Agent reached maximum steps without text response."

                    sess["turns"].append(turn_record)
                    save_session_file(session_id, sess)
                    return {
                        "session_id": session_id,
                        "response": final_response_text,
                        "trajectory": turn_record["steps"]
                    }

        try:
            if self.tracer:
                with self.tracer.start_as_current_span("agent_query_turn") as span:
                    span.set_attribute("session.id", session_id)
                    span.set_attribute("user.input", user_input)
                    return await run_loop()
            else:
                return await run_loop()

        except Exception as e:
            err_msg = f"Error executing agent query: {str(e)}"
            turn_record["steps"].append({"step_type": "error", "content": err_msg})
            sess["turns"].append(turn_record)
            save_session_file(session_id, sess)
            return {
                "session_id": session_id,
                "response": err_msg,
                "trajectory": turn_record["steps"]
            }

    async def query(self, query: str, session_id: str = None) -> str:
        """Main query endpoint for Reasoning Engine. Handles query requests or session trajectory retrieval."""
        if query and query.strip().upper() in ["GET_SESSION", "SHOW_TRAJECTORY", "TRAJECTORY", "GET_TRAJECTORY"]:
            sess_data = self.get_session(session_id)
            return json.dumps(sess_data, indent=2)
        res = await self._async_query(query, session_id=session_id)
        if isinstance(res, dict):
            return res.get("response", str(res))
        return str(res)


def deploy_agent(project_id: str, location: str, mcp_url: str, staging_bucket: str):
    import vertexai
    from google.cloud import aiplatform
    from vertexai import agent_engines
    import getpass
    username = getpass.getuser()
    
    print(f"Initializing vertexai & aiplatform (Project: {project_id}, Location: {location}, Staging Bucket: {staging_bucket})...")
    vertexai.init(project=project_id, location=location, staging_bucket=staging_bucket)
    aiplatform.init(project=project_id, location=location, staging_bucket=staging_bucket)
    
    agent_instance = WarehouseAgentReasoningEngine(mcp_url=mcp_url)
    
    print("Deploying Agent Engine with OpenTelemetry GCP Trace Exporter enabled...")
    try:
        reasoning_engine = agent_engines.create(
            agent_engine=agent_instance,
            requirements=[
                "google-cloud-aiplatform",
                "google-genai",
                "mcp>=0.1.0",
                "httpx>=0.20.0",
                "anyio",
                "pyjwt",
                "opentelemetry-api",
                "opentelemetry-sdk",
                "opentelemetry-exporter-gcp-trace",
                "opentelemetry-resourcedetector-gcp",
                "opentelemetry-instrumentation-google-genai"
            ],
            display_name=f"{username}-warehouse-assistant-adk",
            gcs_dir_name=f"{username}-reasoning-engine",
            extra_packages=[],
            env_vars={
                "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
                "OTEL_SEMCONV_STABILITY_OPT_IN": "gen_ai_latest_experimental",
                "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "EVENT_ONLY",
                "OTEL_TRACES_EXPORTER": "google_cloud",
            }
        )
        print("\n====================================================")
        print("Agent Engine Deployed Successfully!")
        print(f"Resource Name: {reasoning_engine.resource_name}")
        print("====================================================")
        return reasoning_engine.resource_name
    except Exception as e:
        print(f"Deployment failed: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    mcp_url = os.environ.get("MCP_SERVER_URL", "https://warehouse-mcp-server-mjog4mq5za-uc.a.run.app")
    staging_bucket = os.environ.get("STAGING_BUCKET")
    
    if len(sys.argv) > 1 and sys.argv[1] == "--deploy":
        if not project:
            print("Error: GOOGLE_CLOUD_PROJECT is required for deployment.")
            sys.exit(1)
        if not staging_bucket:
            staging_bucket = f"gs://{project}-staging"
            print(f"Using default staging bucket: {staging_bucket}")
            
        deploy_agent(project, "us-central1", mcp_url, staging_bucket)
    else:
        print("Running local verification of the Reasoning Engine class...")
        if not project:
            os.environ["GOOGLE_CLOUD_PROJECT"] = "geap-workshop-temp-1"
            
        agent = WarehouseAgentReasoningEngine(mcp_url=mcp_url)
        agent.set_up()
        
        session_id = agent.create_session()
        print(f"Testing session creation: {session_id}")
        test_query = "What products are currently in stock?"
        print(f"Querying local ADK agent: '{test_query}'...")
        res = asyncio.run(agent._async_query(test_query, session_id=session_id))
        print(f"\nAgent Response:\n{res['response']}")
        print(f"\nSession Trajectory Steps ({len(res['trajectory'])} steps):")
        print(json.dumps(res["trajectory"], indent=2))

if __name__ == "__main__":
    main()
