import os
import sys
import json
import glob
import argparse
from google import genai

def observe_local_session(session_id: str = None):
    sessions_dir = "sessions"
    if not os.path.exists(sessions_dir):
        print("No local sessions directory found.")
        return

    if not session_id:
        # Find latest session file
        files = glob.glob(os.path.join(sessions_dir, "*.json"))
        if not files:
            print("No session trajectory files found in 'sessions/'.")
            return
        files.sort(key=os.path.getmtime, reverse=True)
        session_file = files[0]
    else:
        session_file = os.path.join(sessions_dir, f"{session_id}.json")
        if not os.path.exists(session_file):
            print(f"Session trajectory file not found: {session_file}")
            return

    print(f"Loading local session trajectory: {session_file}")
    with open(session_file, "r") as f:
        data = json.load(f)

    print("\n" + "="*60)
    print(f"LOCAL SESSION TRAJECTORY LOG (ID: {data.get('session_id')})")
    print(f"Created At: {data.get('created_at')}")
    print("="*60)

    turns = data.get("turns", [])
    print(f"Total Turns: {len(turns)}")

    for turn in turns:
        print("\n" + "-"*60)
        print(f"Turn #{turn.get('turn_index')} [{turn.get('timestamp')}] User: '{turn.get('user_input')}'")
        print("-" * 60)
        for i, step in enumerate(turn.get("steps", [])):
            stype = step.get("step_type")
            if stype == "user_input":
                print(f"  [Step {i+1}] User Input: {step.get('content')}")
            elif stype == "thought":
                print(f"  [Step {i+1}] Thought: {step.get('content')}")
            elif stype == "function_call":
                print(f"  [Step {i+1}] Function Call: '{step.get('tool_name')}' with args: {json.dumps(step.get('arguments'))}")
            elif stype == "function_response":
                print(f"  [Step {i+1}] Function Result ({step.get('tool_name')}): {step.get('result')}")
            elif stype == "model_output":
                print(f"  [Step {i+1}] Model Output: {step.get('content')}")
            else:
                print(f"  [Step {i+1}] {stype}: {step}")
    print("\n" + "="*60)


def observe_adk_session(project: str, engine_name: str, session_id: str = None):
    from google.cloud import aiplatform
    from vertexai.preview import reasoning_engines

    if not engine_name.startswith("projects/"):
        engine_name = f"projects/{project}/locations/us-central1/reasoningEngines/{engine_name}"

    print(f"Connecting to Reasoning Engine API: {engine_name}...")
    aiplatform.init(project=project)
    agent = reasoning_engines.ReasoningEngine(engine_name)

    if not session_id:
        print("Error: --session_id is required to fetch Reasoning Engine session trajectory.")
        return

    print(f"\nFetching Session Trajectory via API for Session ID: {session_id}...")
    try:
        raw_sess = agent.query(query="GET_SESSION", session_id=session_id)
        sess_data = json.loads(raw_sess) if isinstance(raw_sess, str) else raw_sess
        print("\n" + "="*60)
        print(f"REASONING ENGINE SESSION TRAJECTORY (ID: {sess_data.get('session_id')})")
        print(f"Created At: {sess_data.get('created_at')}")
        print("="*60)

        turns = sess_data.get("turns", [])
        for turn in turns:
            print("\n" + "-"*60)
            print(f"Turn #{turn.get('turn_index')} [{turn.get('timestamp')}] User: '{turn.get('user_input')}'")
            print("-" * 60)
            for i, step in enumerate(turn.get("steps", [])):
                stype = step.get("step_type")
                if stype == "user_input":
                    print(f"  [Step {i+1}] User Input: {step.get('content')}")
                elif stype == "thought":
                    print(f"  [Step {i+1}] Thought: {step.get('content')}")
                elif stype == "function_call":
                    print(f"  [Step {i+1}] Function Call: '{step.get('tool_name')}' with args: {json.dumps(step.get('arguments'))}")
                elif stype == "function_response":
                    print(f"  [Step {i+1}] Function Result ({step.get('tool_name')}): {step.get('result')}")
                elif stype == "model_output":
                    print(f"  [Step {i+1}] Model Output: {step.get('content')}")
                else:
                    print(f"  [Step {i+1}] {stype}: {step}")
        print("\n" + "="*60)

    except Exception as e:
        print(f"Error fetching session trajectory: {e}")


def observe_interaction(project: str, interaction_id: str):
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
    for i, step in enumerate(steps):
        step_type = getattr(step, "type", "unknown")
        print(f"\n[Step {i+1}] Type: {step_type}")
        if step_type == "thought":
            for part in (getattr(step, "content", []) or []):
                if hasattr(part, "text") and part.text:
                    print(f"  Thought: {part.text.strip()}")
        elif step_type == "model_output":
            for part in (getattr(step, "content", []) or []):
                if hasattr(part, "text") and part.text:
                    print(f"  Output: {part.text.strip()}")
        elif step_type == "user_input":
            for part in (getattr(step, "content", []) or []):
                if hasattr(part, "text") and part.text:
                    print(f"  Input: {part.text.strip()}")
        elif step_type == "mcp_server_tool_call":
            print(f"  Tool Call: '{getattr(step, 'name', 'unknown')}' on '{getattr(step, 'server_name', 'unknown')}'")
            print(f"  Args: {json.dumps(getattr(step, 'arguments', {}))}")
        elif step_type == "mcp_server_tool_result":
            print(f"  Tool Result ('{getattr(step, 'name', 'unknown')}'): {getattr(step, 'result', '')}")


def main():
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "geap-workshop-temp-1")
    parser = argparse.ArgumentParser(description="View Agent Session & Trajectory Logs.")
    parser.add_argument("--session_id", type=str, help="Session ID to inspect.")
    parser.add_argument("--adk", type=str, help="Deployed ADK Reasoning Engine name or ID.")
    parser.add_argument("--interaction_id", type=str, help="Managed agent interaction ID.")
    parser.add_argument("--local", action="store_true", help="Force viewing local session trajectory.")
    args = parser.parse_args()

    if args.interaction_id:
        observe_interaction(project, args.interaction_id)
    elif args.adk:
        observe_adk_session(project, args.adk, session_id=args.session_id)
    else:
        observe_local_session(session_id=args.session_id)

if __name__ == "__main__":
    main()
