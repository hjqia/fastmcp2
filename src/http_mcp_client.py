"""Unified FastMCP HTTP client for tasks + elicitation.

Usage examples:
  source .venv/bin/activate
  python http_mcp_client.py --tool slow_task --duration 5 --bearer-token $BLAXEL_BEARER_TOKEN
  python http_mcp_client.py --tool choose_action --bearer-token $BLAXEL_BEARER_TOKEN
  python http_mcp_client.py --probe
"""

import argparse
import asyncio
import logging
import os

import httpx
from fastmcp import Client
from fastmcp.client import StreamableHttpTransport
from fastmcp.client.elicitation import ElicitResult
from fastmcp.exceptions import ToolError
from fastmcp.utilities.types import File as MCPFile

logging.basicConfig(level=logging.INFO)

DEFAULT_SERVER_URL = os.getenv("SERVER_URL", "http://127.0.0.1:1338/mcp")


async def probe_endpoint(httpx_factory, server_url: str) -> None:
    """Send a single POST to inspect status/body when debugging Cloudflare 400s."""
    async with httpx_factory() as client:
        resp = await client.post(server_url, json={"probe": True})
        text = resp.text
        print(f"Probe status: {resp.status_code}")
        print("Probe headers:")
        for k, v in resp.headers.items():
            print(f"  {k}: {v}")
        print("Probe body (first 500 chars):")
        print(text[:500])


async def basic_elicitation_handler(message: str, response_type: type, params, context):
    print(f"Server asks: {message}")
    user_response = input("Your response: ").strip()

    if response_type is None:
        lowered = user_response.lower()
        if lowered in ("decline", "reject", "no"):
            return ElicitResult(action="decline")
        if lowered in ("cancel", "exit"):
            return ElicitResult(action="cancel")
        return ElicitResult(action="accept")

    if not user_response:
        return ElicitResult(action="decline")

    try:
        return response_type(value=user_response)
    except TypeError:
        return response_type(user_response)


async def run_slow_task(client: Client, duration: int) -> None:
    task = await client.call_tool("slow_task", {"duration": duration}, task=True)
    print(f"Submitted slow_task({duration}) as task_id={task.task_id}")
    print(f"Returned immediately: {task.returned_immediately}")

    if task.returned_immediately:
        result = await task
        print("Server chose synchronous execution; result:", result.data)
        return

    status = await task.status()
    print(f"Initial status: {status.status}")

    final_status = await task.wait(state="completed")
    print(f"Final status: {final_status.status}")

    result = await task.result()
    print("Task result:", result.data or result.structured_content or result.content)


async def run_choose_action(client: Client) -> None:
    result = await client.call_tool("choose_action")
    print("Tool result:", result)


async def run_generic_tool(client: Client, name: str) -> None:
    """Call any tool with no arguments and print the result."""
    result = await client.call_tool(name)
    print(f"Tool '{name}' result:", result)


async def run_receive_file(client: Client, path: str) -> None:
    """Send a local file to the receive_file tool."""
    if not path:
        raise ValueError("A file path is required for receive_file")

    resource = MCPFile(path=path).to_resource_content()
    result = await client.call_tool("receive_file", {"uploaded_file": resource})
    print("receive_file result:", result)


async def run_run_python(client: Client, script: str) -> None:
    """Call the run_python tool."""
    if not script:
        raise ValueError("Script content is required for run_python")
    
    # Check if script is a file path
    if os.path.exists(script):
        try:
            with open(script, "r") as f:
                script_content = f.read()
            print(f"Reading script from file: {script}")
            script = script_content
        except Exception as e:
            print(f"Warning: Could not read file '{script}', treating as raw code. Error: {e}")

    result = await client.call_tool("run_python", {"script": script})
    print("run_python result:\n", result)


async def main(
    tool: str,
    duration: int,
    probe: bool,
    bearer_token: str | None,
    server_url: str,
    upload_file: str | None,
    script: str | None,
) -> None:
    def httpx_factory(headers=None, timeout=None, auth=None):
        merged_headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/event-stream",
        } | (headers or {})
        if bearer_token:
            merged_headers["Authorization"] = f"Bearer {bearer_token}"
        return httpx.AsyncClient(
            headers=merged_headers,
            timeout=timeout,
            auth=auth,
            follow_redirects=False,
            http2=True,
            verify=True,
        )

    transport = StreamableHttpTransport(
        server_url,
        httpx_client_factory=httpx_factory,
    )

    if probe:
        await probe_endpoint(httpx_factory, server_url)
        return

    client = Client(
        transport,
        elicitation_handler=basic_elicitation_handler,
    )

    async with client:
        tools = await client.list_tools()
        available = {t.name: t for t in tools}
        print("Available tools:", ", ".join(sorted(available.keys())) or "(none)")

        if tool == "list":
            return

        if tool not in available:
            print(f"Tool '{tool}' is not offered by the server. Nothing to do.")
            return

        try:
            if tool == "slow_task":
                await run_slow_task(client, duration)
            elif tool == "choose_action":
                await run_choose_action(client)
            elif tool == "receive_file":
                if not upload_file:
                    print("receive_file requires --upload-file PATH")
                    return
                await run_receive_file(client, upload_file)
            elif tool == "run_python":
                if not script:
                    print("run_python requires --script 'code' or --script path/to/file.py")
                    return
                await run_run_python(client, script)
            else:
                await run_generic_tool(client, tool)
        except ToolError as exc:
            print(f"Server rejected tool '{tool}': {exc}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tool",
        default="slow_task",
        help="Tool to call (use 'list' to only show available tools)",
    )
    parser.add_argument("--duration", type=int, default=5, help="Seconds for slow_task")
    parser.add_argument("--probe", action="store_true", help="Make a single POST and print status/body")
    parser.add_argument(
        "--bearer-token",
        default=os.getenv("BLAXEL_BEARER_TOKEN"),
        help="Bearer token for Authorization header (or set BLAXEL_BEARER_TOKEN)",
    )
    parser.add_argument(
        "--server-url",
        default=DEFAULT_SERVER_URL,
        help="Override MCP server URL (default SERVER_URL env or http://127.0.0.1:8000/mcp)",
    )
    parser.add_argument(
        "--upload-file",
        help="Local file path to send to the receive_file tool",
    )
    parser.add_argument(
        "--script",
        help="Python script content or file path for the run_python tool",
    )

    args = parser.parse_args()
    asyncio.run(
        main(
            tool=args.tool,
            duration=args.duration,
            probe=args.probe,
            bearer_token=args.bearer_token,
            server_url=args.server_url,
            upload_file=args.upload_file,
            script=args.script,
        )
    )
