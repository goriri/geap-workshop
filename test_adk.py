from google import genai
from google.cloud import aiplatform

aiplatform.init(project="geap-workshop-temp-1", location="us-central1")
try:
    print(aiplatform.ReasoningEngine.create(
        reasoning_engine="test",
        display_name="test"
    ))
except Exception as e:
    print("Failed", e)
