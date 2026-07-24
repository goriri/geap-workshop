import asyncio
import os
import re
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
        project = os.environ.get("GOOGLE_CLOUD_PROJECT", "geap-trial-run")
        engine_resource_name = (
            os.getenv("GOOGLE_CLOUD_AGENT_ENGINE_ID")
            or os.getenv("GOOGLE_CLOUD_REASONING_ENGINE_RESOURCE_NAME")
            or os.getenv("REASONING_ENGINE_RESOURCE_NAME")
            or getattr(self, "_resource_name", "")
        )
        if engine_resource_name and "locations/" in engine_resource_name:
            short_resource_id = engine_resource_name[engine_resource_name.find("locations/"):]
        else:
            short_resource_id = f"locations/us-central1/reasoningEngines/{engine_resource_name.split('/')[-1]}" if engine_resource_name else ""

        try:
            import opentelemetry
            import opentelemetry.trace
            from opentelemetry.instrumentation.google_genai import GoogleGenAiSdkInstrumentor
            from agentplatform.agent_engines.templates.adk import _default_instrumentor_builder

            GoogleGenAiSdkInstrumentor().instrument()
            
            _default_instrumentor_builder(
                project_id=project,
                enable_tracing=True,
                enable_logging=False
            )
            
            self.tracer = opentelemetry.trace.get_tracer("warehouse_adk_agent")
            print(f"Successfully initialized OpenTelemetry for resource '{short_resource_id}'.")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Warning: OpenTelemetry tracer initialization skipped: {e}")
            self.tracer = None

        self.client = genai.Client(vertexai=True, project=project, location="global")
        if not hasattr(self, "sessions") or self.sessions is None:
            self.sessions = {}

    def _get_engine_resource_path(self):
        """Returns the GCP ReasoningEngine resource base URL path if available."""
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "geap-trial-run")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        engine_id = (
            os.getenv("GOOGLE_CLOUD_AGENT_ENGINE_ID")
            or os.getenv("GOOGLE_CLOUD_REASONING_ENGINE_RESOURCE_NAME")
            or os.getenv("REASONING_ENGINE_RESOURCE_NAME")
            or getattr(self, "_resource_name", None)
        )
        if engine_id:
            if "/" in str(engine_id):
                return f"https://{location}-aiplatform.googleapis.com/v1beta1/{engine_id}"
            return f"https://{location}-aiplatform.googleapis.com/v1beta1/projects/{project_id}/locations/{location}/reasoningEngines/{engine_id}"
        return None

    def _create_managed_session(self, session_id: str, user_id: str = "workshop-user"):
        """Registers the session with GCP Managed Agent Engine Sessions REST API."""
        def _do_create():
            base_path = self._get_engine_resource_path()
            if not base_path:
                return
            try:
                import google.auth
                from google.auth.transport.requests import Request
                import urllib.request
                import json

                creds, _ = google.auth.default()
                creds.refresh(Request())
                token = creds.token
                
                url = f"{base_path}/sessions"
                payload = {"user_id": user_id}
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    print(f"Successfully registered session '{session_id}' with Managed Sessions API.")
            except Exception as e:
                print(f"Managed Session creation note: {e}")

        try:
            import threading
            threading.Thread(target=_do_create, daemon=True).start()
        except Exception as e:
            print(f"Thread spawn note: {e}")

    def _append_managed_session_event(self, session_id: str, author: str, content_text: str, invocation_id: str):
        """Appends turn events to GCP Managed Agent Engine Sessions REST API for Cloud Console UI visibility."""
        def _do_append():
            base_path = self._get_engine_resource_path()
            if not base_path:
                return
            try:
                import google.auth
                from google.auth.transport.requests import Request
                import urllib.request
                import json

                creds, _ = google.auth.default()
                creds.refresh(Request())
                token = creds.token

                url = f"{base_path}/sessions/{session_id}:appendEvent"
                payload = {
                    "author": author,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "invocationId": invocation_id,
                    "content": {
                        "parts": [{"text": str(content_text)}]
                    }
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    pass
            except Exception as e:
                if "404" in str(e):
                    try:
                        self._create_managed_session(session_id)
                        req = urllib.request.Request(
                            url,
                            data=json.dumps(payload).encode("utf-8"),
                            headers={
                                "Authorization": f"Bearer {token}",
                                "Content-Type": "application/json"
                            },
                            method="POST"
                        )
                        with urllib.request.urlopen(req, timeout=5) as resp:
                            pass
                    except Exception as retry_e:
                        print(f"Managed Session event append retry note: {retry_e}")
                else:
                    print(f"Managed Session event append note: {e}")

        try:
            import threading
            threading.Thread(target=_do_append, daemon=True).start()
        except Exception as e:
            print(f"Thread spawn note: {e}")

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
                self._create_managed_session(session_id)
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
        inv_id = f"turn-{turn_index}"
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
                    self._append_managed_session_event(session_id, "user", user_input, inv_id)
                    self._append_managed_session_event(session_id, "model", final_response_text, inv_id)
            try:
                import opentelemetry.trace
                tracer_provider = opentelemetry.trace.get_tracer_provider()
                if hasattr(tracer_provider, "force_flush"):
                    tracer_provider.force_flush()
            except Exception:
                pass

            return {
                "session_id": session_id,
                "response": final_response_text,
                "trajectory": turn_record["steps"]
            }

        try:
            if self.tracer:
                engine_res_path = self._get_engine_resource_path() or ""
                with self.tracer.start_as_current_span("agent_query_turn") as span:
                    span.set_attribute("cloud.resource_id", engine_res_path)
                    span.set_attribute("gcp.vertex.agent.engine_id", engine_res_path)
                    span.set_attribute("gen_ai.conversation.id", session_id)
                    span.set_attribute("gcp.vertex.agent.session_id", session_id)
                    span.set_attribute("gcp.vertex.agent.invocation_id", inv_id)
                    span.set_attribute("session.id", session_id)
                    span.set_attribute("user.input", user_input)
                    return await run_loop()
            else:
                return await run_loop()

        except Exception as e:
            import traceback
            traceback.print_exc()
            err_msg = f"Error executing agent query: {str(e)}"
            turn_record["steps"].append({"step_type": "error", "content": err_msg})
            sess["turns"].append(turn_record)
            save_session_file(session_id, sess)
            try:
                import opentelemetry.trace
                tracer_provider = opentelemetry.trace.get_tracer_provider()
                if hasattr(tracer_provider, "force_flush"):
                    tracer_provider.force_flush()
            except Exception:
                pass
            return {
                "session_id": session_id,
                "response": err_msg,
                "trajectory": turn_record["steps"]
            }

    def _parse_prompt(self, query=None, input=None, **kwargs) -> str:
        val = query if query is not None else (input if input is not None else (kwargs.get("message") or kwargs.get("prompt")))
        if val is None:
            return ""
        if isinstance(val, dict):
            parts = val.get("parts")
            if parts and isinstance(parts, list):
                text_parts = [p.get("text", "") for p in parts if isinstance(p, dict) and "text" in p]
                if text_parts:
                    return " ".join(text_parts)
            return val.get("query") or val.get("input") or val.get("text") or str(val)
        if isinstance(val, list):
            text_parts = []
            for item in val:
                if isinstance(item, dict):
                    parts = item.get("parts")
                    if parts and isinstance(parts, list):
                        text_parts.extend([p.get("text", "") for p in parts if isinstance(p, dict) and "text" in p])
                    elif "text" in item:
                        text_parts.append(str(item["text"]))
                else:
                    text_parts.append(str(item))
            if text_parts:
                return " ".join(text_parts)
        return str(val)

    async def query(self, query: str = None, input: str = None, session_id: str = None, session: str = None, **kwargs) -> str:
        """Main query endpoint for Reasoning Engine / Cloud Console Playground. Handles query requests or session trajectory retrieval."""
        prompt_text = self._parse_prompt(query=query, input=input, **kwargs)
        sess_id = session_id or session or kwargs.get("session_name")

        if prompt_text and prompt_text.strip().upper() in ["GET_SESSION", "SHOW_TRAJECTORY", "TRAJECTORY", "GET_TRAJECTORY"]:
            sess_data = self.get_session(sess_id)
            return json.dumps(sess_data, indent=2)
        res = await self._async_query(prompt_text, session_id=sess_id)
        if isinstance(res, dict):
            return res.get("response", str(res))
        return str(res)

    async def stream_query(self, query: str = None, input: str = None, session_id: str = None, session: str = None, **kwargs):
        """Streaming query endpoint for Cloud Console Playground compatibility (:streamQuery?alt=sse)."""
        prompt_text = self._parse_prompt(query=query, input=input, **kwargs)
        sess_id = session_id or session or kwargs.get("session_name")

        res_str = await self.query(query=prompt_text, session_id=sess_id, **kwargs)
        yield res_str


def deploy_agent(project_id: str, location: str, mcp_url: str, staging_bucket: str):
    import vertexai
    from google.cloud import aiplatform
    from vertexai import agent_engines
    prefix = os.environ.get("GEAP_PREFIX")
    if not prefix:
        print("Error: GEAP_PREFIX environment variable is not set.")
        sys.exit(1)
    
    try:
        import subprocess
        mcp_service_name = f"{prefix}-warehouse-mcp-server"
        print(f"Granting Reasoning Engine service agent permissions to invoke Cloud Run service '{mcp_service_name}'...")
        proj_num = subprocess.check_output(["gcloud", "projects", "describe", project_id, "--format", "value(projectNumber)"]).decode().strip()
        service_agent = f"serviceAccount:service-{proj_num}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
        subprocess.check_call([
            "gcloud", "run", "services", "add-iam-policy-binding", mcp_service_name,
            "--member", service_agent,
            "--role", "roles/run.invoker",
            "--region", location,
            "--project", project_id,
            "--quiet"
        ])
        print("Successfully granted IAM permissions.")
    except Exception as e:
        print(f"Warning: Failed to grant IAM permissions automatically: {e}")

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
                "opentelemetry-exporter-otlp-proto-http",
                "opentelemetry-instrumentation==0.64b0",
                "opentelemetry-semantic-conventions==0.64b0",
                "opentelemetry-util-genai==0.3b0",
                "opentelemetry-exporter-gcp-logging==1.12.0a0",
                "opentelemetry-exporter-gcp-trace==1.12.0",
                "opentelemetry-resourcedetector-gcp==1.12.0a0",
                "opentelemetry-instrumentation-google-genai==0.7b1"
            ],
            display_name=f"{prefix}-warehouse-assistant-adk",
            gcs_dir_name=f"{prefix}-reasoning-engine",
            extra_packages=[],
            env_vars={
                "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
                "OTEL_SEMCONV_STABILITY_OPT_IN": "gen_ai_latest_experimental",
                "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "EVENT_ONLY",
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
    mcp_url = os.environ.get("MCP_SERVER_URL")
    staging_bucket = os.environ.get("STAGING_BUCKET")
    
    if len(sys.argv) > 1 and sys.argv[1] == "--deploy":
        if not project:
            print("Error: GOOGLE_CLOUD_PROJECT is required for deployment.")
            sys.exit(1)
        if not mcp_url:
            print("Error: MCP_SERVER_URL is required for deployment.")
            sys.exit(1)
        if not staging_bucket:
            staging_bucket = f"gs://{project}-staging"
            print(f"Using default staging bucket: {staging_bucket}")
            
        deploy_agent(project, "us-central1", mcp_url, staging_bucket)
    else:
        print("Running local verification of the Reasoning Engine class...")
        if not project:
            os.environ["GOOGLE_CLOUD_PROJECT"] = "geap-workshop-temp-1"
        if not mcp_url:
            print("Error: MCP_SERVER_URL is required for local verification.")
            sys.exit(1)
            
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
