import os
import sys
from google.cloud import aiplatform
from vertexai.preview import reasoning_engines

def main():
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "geap-workshop-temp-1")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    
    # Get resource name from env, or default to our successfully deployed engine
    engine_name = os.environ.get("REASONING_ENGINE_NAME")
    if not engine_name:
        engine_name = "projects/181550378089/locations/us-central1/reasoningEngines/2476591117693353984"
        
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
    print("="*60)
    print("This interactive console allows you to chat directly with your remote Python-packaged agent.")
    print("Type 'exit' or 'quit' to end the conversation.")
    print("="*60 + "\n")

    while True:
        try:
            user_input = input("\nYou: ")
            if not user_input.strip():
                continue
            if user_input.strip().lower() in ["exit", "quit"]:
                print("Goodbye!")
                break

            print("\nThinking (Remote Agent executing reasoning loop)...")
            # Query the remote reasoning engine
            response = agent.query(query=user_input)
            
            # Print response
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
