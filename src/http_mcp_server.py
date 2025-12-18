"""FastMCP HTTP server exposing both a background task and an elicitation tool.

Run with:
    python http_mcp_server.py
"""

import asyncio
import base64
import logging
import os
import sys
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

import mcp.types as mcp_types
from fastmcp import Context, FastMCP
from fastmcp.dependencies import Depends, Progress
from fastmcp.server.tasks import TaskConfig

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.DEBUG)
logging.getLogger("docket").setLevel(logging.INFO)
logging.getLogger("docket.worker").setLevel(logging.INFO)


mcp = FastMCP(
    "http-mcp-server",
    instructions="HTTP MCP server with background task + elicitation",
    tasks=True,
    # host=os.getenv("HOST", "0.0.0.0"),
    # port=os.getenv("PORT", "8000"),
)


@mcp.tool(task=TaskConfig(mode="required"))
async def slow_task(
    duration: Annotated[int, "How many seconds to run"],
    progress: Progress = Depends(Progress),
) -> str:
    """Sleep for `duration` seconds while reporting progress."""

    await progress.set_total(duration)

    for i in range(duration):
        await progress.set_message(f"Working... step {i + 1}/{duration}")
        await progress.increment()
        await asyncio.sleep(1)

    return f"Finished a {duration}-second task over HTTP"


@mcp.tool
async def choose_action(ctx: Context) -> str:
    """Ask the client to pick an action via elicitation."""
    result = await ctx.elicit("Choose an action", ["accept", "decline", "cancel"])

    if result.action == "accept":
        selection = getattr(result, "data", None)
        return f"Accepted: {selection or 'no selection provided'}"
    if result.action == "decline":
        return "Declined!"
    return "Cancelled!"


@mcp.tool
async def receive_file(
    uploaded_file: Annotated[
        mcp_types.EmbeddedResource | mcp_types.ResourceLink,
        "File uploaded by the client",
    ],
    ctx: Context,
) -> str:
    """Store an uploaded file and report where it was saved."""

    if isinstance(uploaded_file, mcp_types.ResourceLink):
        contents = await ctx.read_resource(str(uploaded_file.uri))
        if not contents:
            raise ValueError("No content returned for the provided resource link")
        resource = contents[0]
        source_uri = uploaded_file.uri
    else:
        resource = uploaded_file.resource
        source_uri = uploaded_file.resource.uri

    if isinstance(resource, mcp_types.TextResourceContents):
        data = resource.text.encode()
        mime_type = resource.mimeType
    elif isinstance(resource, mcp_types.BlobResourceContents):
        data = base64.b64decode(resource.blob)
        mime_type = resource.mimeType
    else:
        raise ValueError(f"Unsupported resource type: {type(resource)!r}")

    # Use only the filename component to avoid path traversal
    name_hint = Path(urlparse(str(source_uri)).path).name or "uploaded.bin"
    upload_dir = Path(os.getenv("UPLOAD_DIR", "/tmp/mcp_uploads"))
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination = upload_dir / name_hint
    destination.write_bytes(data)

    return f"Saved {destination} ({mime_type}, {destination.stat().st_size} bytes)"


@mcp.tool
async def run_python(script: Annotated[str, "Python script to execute"]) -> str:
    """Run a Python script and return the output."""
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-c", script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    output = stdout.decode()
    print(f'script output: {output}')
    if stderr:
        output += f"\nStderr: {stderr.decode()}"
    return output


def main() -> None:
    host = os.getenv("HOST", "0.0.0.0")
    port = os.getenv("PORT", 1338)
    if isinstance(port, str):
        port = int(port)
    mcp.run(transport="http", host=host, port=port)


if __name__ == "__main__":
    main()
