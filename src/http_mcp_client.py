"""Unified FastMCP HTTP client for tasks + elicitation.

Usage examples:
  source .venv/bin/activate
  python http_mcp_client.py --tool slow_task --duration 5 --bearer-token $BLAXEL_BEARER_TOKEN
  python http_mcp_client.py --tool choose_action --bearer-token $BLAXEL_BEARER_TOKEN
  python http_mcp_client.py --probe
"""

import argparse
import asyncio
import inspect
import logging
import os
import shutil
import sys
from pathlib import Path

import httpx
from fastmcp import Client
from fastmcp.client import StreamableHttpTransport
from fastmcp.client.elicitation import ElicitResult
from fastmcp.exceptions import ToolError
from fastmcp.utilities.types import File as MCPFile

logging.basicConfig(level=logging.INFO)

DEFAULT_SERVER_URL = os.getenv("SERVER_URL", "http://127.0.0.1:1338/mcp")


async def generate_proxies(client: Client, server_url: str, bearer_token: str | None) -> None:
    """Generate local Python wrappers for all tools on the server."""
    tools = await client.list_tools()
    server_name = "mcp_server"  # In a real scenario, this would come from the server metadata
    proxy_dir = Path("mcp_proxies") / server_name
    proxy_dir.mkdir(parents=True, exist_ok=True)

    # Create __init__.py for the package
    init_content = [
        "import asyncio",
        "import os",
        "import httpx",
        "from fastmcp import Client",
        "from fastmcp.client import StreamableHttpTransport",
        "from fastmcp.client.elicitation import ElicitResult",
        "",
        f"SERVER_URL = {server_url!r}",
        f"BEARER_TOKEN = {bearer_token!r}",
        "",
        "async def basic_elicitation_handler(message: str, response_type: type, params, context):",
        "    print(f'Server asks: {message}')",
        "    user_response = input('Your response: ').strip()",
        "",
        "    if response_type is None:",
        "        lowered = user_response.lower()",
        "        if lowered in ('decline', 'reject', 'no'):",
        "            return ElicitResult(action='decline')",
        "        if lowered in ('cancel', 'exit'):",
        "            return ElicitResult(action='cancel')",
        "        # For generic accept, we can assume the user input is the data if it's not a control word",
        "        # But adhering to the simple handler in the main client:",
        "        return ElicitResult(action='accept', data=user_response)",
        "",
        "    if not user_response:",
        "        return ElicitResult(action='decline')",
        "",
        "    try:",
        "        return response_type(value=user_response)",
        "    except TypeError:",
        "        return response_type(user_response)",
        "",
        "async def _call_tool_async(tool_name, is_task=False, **kwargs):",
        "    def httpx_factory(headers=None, timeout=None, auth=None):",
        "        merged_headers = {'User-Agent': 'Mozilla/5.0'} | (headers or {})",
        "        if BEARER_TOKEN:",
        "            merged_headers['Authorization'] = f'Bearer {BEARER_TOKEN}'",
        "        return httpx.AsyncClient(headers=merged_headers, timeout=timeout, auth=auth, http2=True)",
        "    ",
        "    transport = StreamableHttpTransport(SERVER_URL, httpx_client_factory=httpx_factory)",
        "    async with Client(transport, elicitation_handler=basic_elicitation_handler) as client:",
        "        if not is_task:",
        "            result = await client.call_tool(tool_name, kwargs)",
        "            return result.content[0].text if result.content else ''",
        "        ",
        "        # Handle Task execution",
        "        task = await client.call_tool(tool_name, kwargs, task=True)",
        "        if task.returned_immediately:",
        "            return task.data",
        "        ",
        "        await task.wait(state='completed')",
        "        result = await task.result()",
        "        return result.data or result.structured_content or result.content",
        "",
        "def _run_sync(coro):",
        "    try:",
        "        loop = asyncio.get_event_loop()",
        "    except RuntimeError:",
        "        loop = asyncio.new_event_loop()",
        "        asyncio.set_event_loop(loop)",
        "    return loop.run_until_complete(coro)",
        "",
    ]

    for tool in tools:
        # We need to know if this tool requires task execution.
        # FastMCP tools don't expose 'task' config in the standard ListTools result directly 
        # in a way that is easily guaranteed without inspecting the schema or naming convention.
        # However, for this generated proxy, we can try to infer or just support a generic 'task' arg.
        # But specifically for 'slow_task' which we know is a task:
        
        # In a robust implementation, we would check tool.description or specific metadata if available.
        # For this prototype, we will check if the tool name implies a task or hardcode known tasks.
        is_task = tool.name == "slow_task" # Simple heuristic for this demo
        
        init_content.append(f"def {tool.name}(**kwargs):")
        init_content.append(f"    \"\"\"{tool.description}\"\"\"")
        init_content.append(f"    return _run_sync(_call_tool_async({tool.name!r}, is_task={is_task}, **kwargs))")
        init_content.append("")

    (proxy_dir / "__init__.py").write_text("\n".join(init_content))
    (Path("mcp_proxies") / "__init__.py").touch()
    
    print(f"Proxies generated in {proxy_dir}")
    print("You can now use them in your local scripts, e.g.:")
    print(f"  from mcp_proxies.{server_name} import {tools[0].name if tools else 'tool'}")


def execute_local_script(script_path_or_code: str) -> None:
    """Execute a Python script locally with mcp_proxies in the path."""
    sys.path.append(os.getcwd())
    
    code = script_path_or_code
    if os.path.exists(script_path_or_code):
        with open(script_path_or_code, "r") as f:
            code = f.read()
    
    print("--- Executing Local Script ---")
    # We use exec in a clean global scope but including current globals might be easier for some
    exec_globals = {"__name__": "__main__"}
    try:
        exec(code, exec_globals)
    except Exception as e:
        print(f"Error executing script: {e}")
    print("--- Execution Finished ---")


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
    generate: bool,
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
        if generate:
            await generate_proxies(client, server_url, bearer_token)
            return

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
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate local proxy wrappers for server tools",
    )
    parser.add_argument(
        "--execute-local",
        action="store_true",
        help="Execute the script locally using the generated proxies",
    )

    args = parser.parse_args()

    if args.execute_local:
        if not args.script:
            print("Error: --execute-local requires --script")
            sys.exit(1)
        execute_local_script(args.script)
    else:
        asyncio.run(
            main(
                tool=args.tool,
                duration=args.duration,
                probe=args.probe,
                bearer_token=args.bearer_token,
                server_url=args.server_url,
                upload_file=args.upload_file,
                script=args.script,
                generate=args.generate,
            )
        )
