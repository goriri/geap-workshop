import argparse
import json
import os
import sys
import time
import uuid
import vertexai
from vertexai import agent_engines
from vertexai.preview import reasoning_engines

def main():
    parser = argparse.ArgumentParser(description="Interactive CLI Client for Deployed ADK Agent")
    parser.add_argument("--resource_name", help="Reasoning Engine resource name")
    parser.add_argument("--query", help="Single query to run non-interactively")
    args = parser.parse_args()

    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "geap-workshop-temp-1")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    
    engine_name = args.resource_name or os.environ.get("REASONING_ENGINE_NAME")
    if not engine_name:
        print("Error: REASONING_ENGINE_NAME environment variable or --resource_name is required.")
        sys.exit(1)

    session_id = os.environ.get("SESSION_ID") or f"adk-session-{int(time.time())}-{uuid.uuid4().hex[:6]}"
        
    print(f"Initializing Vertex AI SDK (Project: {project}, Location: {location})...")
    vertexai.init(project=project, location=location)

    print(f"Connecting to Reasoning Engine: {engine_name}...")
    agent = None
    try:
        agent = agent_engines.get(engine_name)
    except Exception as e:
        try:
            agent = reasoning_engines.ReasoningEngine(engine_name)
        except Exception as e2:
            print(f"Error loading Reasoning Engine: {e2}", file=sys.stderr)
            sys.exit(1)

    def execute_query(user_input: str):
        if hasattr(agent, "stream_query"):
            events = list(agent.stream_query(user_id=session_id, message=user_input))
            final_text = ""
            for ev in events:
                if isinstance(ev, dict) and "content" in ev:
                    parts = ev["content"].get("parts", [])
                    for p in parts:
                        if "text" in p:
                            final_text += p["text"]
                        elif "function_call" in p:
                            fc = p["function_call"]
                            print(f"  [Tool Call] {fc.get('name')}({fc.get('args')})")
                        elif "function_response" in p:
                            fr = p["function_response"]
                            print(f"  [Tool Response] {fr.get('name')}")
            return final_text or str(events)
        elif hasattr(agent, "query"):
            return agent.query(query=user_input, session_id=session_id)
        else:
            raise AttributeError("Agent has neither stream_query nor query method.")

    if args.query:
        print(f"\nQuerying Agent: '{args.query}'...")
        res = execute_query(args.query)
        print(f"\nAgent Response:\n{res}")
        return

    print("\n" + "="*60)
    print("Welcome to the Vertex AI Reasoning Engine ADK Agent CLI Client!")
    print(f"Active Session ID: {session_id}")
    print("="*60)
    print("This interactive console allows you to chat directly with your remote Python-packaged agent.")
    print("Type 'exit' or 'quit' to end the conversation.")
    print("Type 'session' or 'trajectory' to view the full session trajectory via API.")
    print("="*60 + "\n")

    while True:
        try:
            user_input = input("\nYou: ")
            if not user_input.strip():
                continue
            if user_input.strip().lower() in ["exit", "quit"]:
                print("Goodbye!")
                break

            if user_input.strip().lower() in ["session", "trajectory"]:
                print(f"\nFetching Session Trajectory via API for Session: {session_id}...")
                try:
                    if hasattr(agent, "get_session"):
                        sess_data = agent.get_session(session_id=session_id)
                        print(json.dumps(sess_data, indent=2))
                    else:
                        print("get_session is not supported on this agent engine.")
                except Exception as e:
                    print(f"Could not fetch session data: {e}")
                continue

            print("\nThinking (Remote Agent executing reasoning loop)...")
            response = execute_query(user_input)
            print(f"\nAgent:\n{response}")
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except EOFError:
            break
        except Exception as e:
            print(f"\nError: {e}")
            break

if __name__ == "__main__":
    main()
