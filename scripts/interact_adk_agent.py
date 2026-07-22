import os
import sys
import time
import uuid
import json
from google.cloud import aiplatform
from vertexai.preview import reasoning_engines

def main():
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "geap-workshop-temp-1")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    
    engine_name = os.environ.get("REASONING_ENGINE_NAME")
    if not engine_name:
        print("Error: REASONING_ENGINE_NAME environment variable is not set.")
        print("Set REASONING_ENGINE_NAME to your deployed Reasoning Engine resource name.")
        sys.exit(1)

    session_id = os.environ.get("SESSION_ID") or f"adk-session-{int(time.time())}-{uuid.uuid4().hex[:6]}"
        
    print(f"Initializing Vertex AI SDK (Project: {project}, Location: {location})...")
    aiplatform.init(project=project, location=location)

    print(f"Connecting to Reasoning Engine: {engine_name}...")
    try:
        agent = reasoning_engines.ReasoningEngine(engine_name)
    except Exception as e:
        print(f"Error loading Reasoning Engine: {e}", file=sys.stderr)
        sys.exit(1)

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
                    sess_data = agent.get_session(session_id=session_id)
                    print(json.dumps(sess_data, indent=2))
                except Exception as e:
                    print(f"Could not fetch session data: {e}")
                continue

            print("\nThinking (Remote Agent executing reasoning loop)...")
            response = agent.query(query=user_input, session_id=session_id)
            print(f"\nAgent: {response}")
            
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
