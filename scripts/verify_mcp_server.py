import asyncio
import os
import sys
import traceback
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def main():
    server_url = os.environ.get("MCP_SERVER_URL")
    if not server_url:
        server_url = "https://warehouse-mcp-server-mjog4mq5za-uc.a.run.app/mcp"
        
    if server_url.endswith("/sse"):
        server_url = server_url[:-4]
    if not server_url.endswith("/mcp"):
        server_url = f"{server_url}/mcp"

    print("====================================================")
    print(f"Connecting to MCP Server via Streamable HTTP: {server_url}")
    print("====================================================")

    try:
        # streamablehttp_client yields (read, write, session_id) or (read, write)
        async with streamablehttp_client(server_url) as streams:
            read_stream = streams[0]
            write_stream = streams[1]
            session_id = streams[2] if len(streams) > 2 else None
            
            print(f"Connection established (Session ID: {session_id})")
            
            async with ClientSession(read_stream, write_stream) as session:
                print("1. Initializing session...", flush=True)
                await session.initialize()
                print("Session initialized successfully.\n")
                
                print("2. Listing registered tools...", flush=True)
                tools_result = await session.list_tools()
                print(f"Found {len(tools_result.tools)} tools:")
                for tool in tools_result.tools:
                    print(f"  - {tool.name}: {tool.description}")
                print()
                
                print("3. Testing 'list_inventory' tool...", flush=True)
                result = await session.call_tool("list_inventory")
                print("Result:")
                for content in result.content:
                    print(content.text)
                print()
                
                print("4. Testing 'get_product_stock' tool (product_id=1)...", flush=True)
                result = await session.call_tool("get_product_stock", arguments={"product_id": 1})
                print("Result:")
                for content in result.content:
                    print(content.text)
                print()

    except Exception as e:
        print("\nVerification Failed with error:")
        traceback.print_exc()
        sys.exit(1)

    print("====================================================")
    print("Verification Completed Successfully!")
    print("====================================================")

if __name__ == "__main__":
    asyncio.run(main())
