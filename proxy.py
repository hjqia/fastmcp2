"""MCP Proxy for Cloudflare-style Sandboxed Execution.

This script acts as the 'Controller' or 'Proxy'. It:
1. Sends JS code to a remote Sandbox Executor (node sandbox_executor.js).
2. Receives the execution result and logs.
3. Performs MCP tool calls on the server if the sandbox output requests it.
"""

# Usage:
# python proxy.py --script "console.log('Hello'); ({ mcp_call: { tool: 'hello_name', arguments: { name: 'Cloudflare' } } })"

import argparse
import asyncio
import json
import os
import sys
import httpx
from fastmcp import Client
from fastmcp.client import StreamableHttpTransport

DEFAULT_SERVER_URL = os.getenv("SERVER_URL", "http://127.0.0.1:1338/mcp")
SANDBOX_URL = "http://127.0.0.1:8080/execute"

async def run_sandbox(code: str):
    """Send code to the JS Sandbox Executor."""
    async with httpx.AsyncClient() as client:
        print(f"--- Sending code to Sandbox ({SANDBOX_URL}) ---")
        try:
            resp = await client.post(SANDBOX_URL, json={"code": code}, timeout=15.0)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"status": "error", "error": str(e), "logs": [f"Connection Error: {e}"]}

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", help="JS script or path to file to run in sandbox")
    parser.add_argument(
        "--server-url", 
        default=DEFAULT_SERVER_URL,
        help="MCP Server URL"
    )
    parser.add_argument(
        "--bearer-token", 
        default=os.getenv("BLAXEL_BEARER_TOKEN"),
        help="Bearer token for the MCP server"
    )
    
    args = parser.parse_args()
    
    if not args.script:
        parser.print_help()
        return

    # 1. Prepare JS Code
    js_code = args.script
    if os.path.exists(js_code):
        with open(js_code, "r") as f:
            js_code = f.read()
            
    # 2. Execute JS in Sandbox
    sandbox_response = await run_sandbox(js_code)
    
    print("\n--- Sandbox Logs ---")
    for log in sandbox_response.get("logs", []):
        print(f"| {log}")
    
    if sandbox_response.get("status") == "error":
        print(f"\nSandbox failed: {sandbox_response.get('error')}")
        return

    result = sandbox_response.get("result")
    print("\n--- Sandbox Final Result ---")
    print(json.dumps(result, indent=2))
    
    # 3. Proxy Logic: Handle Tool Calls requested by the Sandbox
    # We simulate a contract where the sandbox returns { "mcp_call": { "tool": "...", "arguments": {...} } }
    if isinstance(result, dict) and "mcp_call" in result:
        call_info = result["mcp_call"]
        tool_name = call_info.get("tool")
        tool_args = call_info.get("arguments", {})
        
        print(f"\n--- Proxy: Detected MCP Tool Call: {tool_name} ---")
        
        def httpx_factory(headers=None, timeout=None, auth=None):
            merged_headers = {"User-Agent": "Mozilla/5.0"} | (headers or {})
            if args.bearer_token:
                merged_headers["Authorization"] = f"Bearer {args.bearer_token}"
            return httpx.AsyncClient(headers=merged_headers, timeout=timeout, auth=auth, http2=True)

        transport = StreamableHttpTransport(args.server_url, httpx_client_factory=httpx_factory)
        
        try:
            async with Client(transport) as mcp_client:
                print(f"Calling tool '{tool_name}' on server...")
                # Simple call for demonstration
                mcp_result = await mcp_client.call_tool(tool_name, tool_args)
                print(f"\n--- MCP Server Result ---")
                print(mcp_result)
        except Exception as e:
            print(f"Error calling MCP tool: {e}")

if __name__ == "__main__":
    asyncio.run(main())
