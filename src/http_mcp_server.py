"""FastMCP HTTP server exposing both a background task and an elicitation tool.

Run with:
    python http_mcp_server.py
"""

import asyncio
import logging
import os
from typing import Annotated

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


def main() -> None:
    host = os.getenv("HOST", "0.0.0.0")
    port = os.getenv("PORT", 1338)
    mcp.run(transport="http", host=host, port=port)


if __name__ == "__main__":
    main()
