import os
import sys
from google import genai

def main():
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    client = genai.Client(vertexai=True, project=project, location="global")

    db_user = "postgres"
    db_pass = "super-secret-password"
    db_name = "warehouse"
    db_host = "35.255.44.66"

    print("Deleting existing agent if any...")
    try:
        client.agents.delete(name="warehouse-assistant")
        print("Deleted existing agent.")
    except Exception as e:
        print(f"Failed to delete (may not exist): {e}")

    system_instruction = f"""
You are a helpful Warehouse Assistant. 
You can query the warehouse postgres database directly using your code execution tool.
The database connection details are:
Host: {db_host}
User: {db_user}
Password: {db_pass}
Database: {db_name}

To interact with the database, write and execute python code using the psycopg2 library, which you can install via pip.
You should be able to:
1. List all inventory
2. Get stock for a specific product
3. Update stock levels
4. Create customer orders (decrementing stock)
"""

    print("Creating remote agent with code_execution...")
    operation = client.agents.create(
        id="warehouse-assistant",
        base_agent="antigravity-preview-05-2026",
        system_instruction=system_instruction,
        tools=[
            {
                "type": "code_execution"
            }
        ],
        base_environment={
            "type": "remote"
        }
    )
    
    print(f"Agent creation initiated: {operation.name}")
    print("Waiting for creation to complete (this might take a few minutes)...")
    
    result = operation.result()
    print("\nAgent created successfully!")
    print(result)

if __name__ == "__main__":
    main()
