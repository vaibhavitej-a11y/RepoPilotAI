"""Filesystem MCP client adapter."""
import asyncio
import logging
import os
import shutil
import sys
from pathlib import Path

from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

# ADK wraps bare StdioServerParameters with a fixed 5s timeout. Cold npx startup
# on Windows routinely exceeds that, so we must use StdioConnectionParams.
DEFAULT_STDIO_TIMEOUT_SECONDS = 120.0
FILESYSTEM_MCP_PACKAGE = "@modelcontextprotocol/server-filesystem"


def _resolve_npx_command() -> str:
    """Resolve an npx executable available on the current platform."""
    if sys.platform == "win32":
        return shutil.which("npx.cmd") or shutil.which("npx") or "npx.cmd"
    return shutil.which("npx") or "npx"


def configure_filesystem_mcp(root_path: str) -> StdioConnectionParams:
    """Configure the Filesystem MCP server connection parameters.

    Connects to ``@modelcontextprotocol/server-filesystem`` over stdio, clamped
    to the resolved absolute target directory.
    """
    resolved_root = str(Path(root_path).expanduser().resolve())
    root = Path(resolved_root)
    if not root.is_dir():
        raise ValueError(
            f"Filesystem MCP root path does not exist or is not a directory: "
            f"{resolved_root!r}"
        )

    command = _resolve_npx_command()
    server_params = StdioServerParameters(
        command=command,
        args=["-y", FILESYSTEM_MCP_PACKAGE, resolved_root],
        cwd=resolved_root,
        env=os.environ.copy(),
    )

    logger.info(
        "Filesystem MCP stdio config: command=%r args=%r cwd=%r timeout=%ss "
        "allowed_root=%r",
        server_params.command,
        server_params.args,
        server_params.cwd,
        DEFAULT_STDIO_TIMEOUT_SECONDS,
        resolved_root,
    )

    return StdioConnectionParams(
        server_params=server_params,
        timeout=DEFAULT_STDIO_TIMEOUT_SECONDS,
    )


async def probe_filesystem_mcp_stdio(
    connection_params: StdioConnectionParams,
    *,
    timeout_seconds: float = DEFAULT_STDIO_TIMEOUT_SECONDS,
) -> None:
    """Verify the filesystem MCP server starts and initializes outside ADK.

    Raises:
        Exception: If the subprocess cannot start or MCP initialize fails.
    """
    server_params = connection_params.server_params
    logger.info(
        "Probing filesystem MCP startup: command=%r args=%r cwd=%r",
        server_params.command,
        server_params.args,
        server_params.cwd,
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        from mcp import ClientSession

        async with ClientSession(read_stream, write_stream) as session:
            await asyncio.wait_for(session.initialize(), timeout=timeout_seconds)

    logger.info("Filesystem MCP probe succeeded for root=%r", server_params.args[-1])
