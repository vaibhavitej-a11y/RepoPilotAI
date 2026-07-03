"""MCP tool registry and allowlist enforcement."""
import logging
import os
from pathlib import PurePosixPath, PureWindowsPath
from typing import Literal

from app.mcp._session_logging import LoggingMcpToolset

logger = logging.getLogger(__name__)


class PathTraversalError(ValueError):
    """Raised when a path traversal attempt is detected in an MCP tool call."""


def validate_path(file_path: str) -> str:
    """Validate that a file path does not contain path traversal sequences.
    
    Raises:
        PathTraversalError: If the path contains '..' components or other traversal patterns.
    
    Returns:
        The original path string if it is safe.
    """
    # Normalize and check for traversal sequences
    normalized = os.path.normpath(file_path)
    
    # Check for .. in original path (before or after normalization)
    if ".." in file_path or ".." in normalized:
        raise PathTraversalError(
            f"Path traversal attempt detected in: {file_path!r}. "
            "Paths containing '..' are not permitted."
        )
    
    # Additional check: if path starts with / after normalization, ensure it's not escaping
    # a relative sandbox (e.g., ../../../../etc/passwd normalizes to /etc/passwd)
    if file_path.startswith("..") or "\\.." in file_path or "/.." in file_path:
        raise PathTraversalError(
            f"Path traversal attempt detected: {file_path!r}"
        )
    
    return file_path

# The only permitted MCP tools. Enforced at config time.
ALLOWED_MCP_TOOLS = frozenset({
    "read_file",
    "list_directory",
    "search_files",
    "get_file_metadata",
})

class MCPConfig:
    """Configuration for an MCP connection."""
    def __init__(self, target_path: str, auth_token: str | None = None):
        self.target_path = target_path
        self.auth_token = auth_token

def build_mcp_toolset(data_source: Literal["github", "filesystem"], config: MCPConfig):
    """Build an McpToolset restricted to ALLOWED_MCP_TOOLS."""
    from app.mcp.filesystem_mcp import configure_filesystem_mcp

    if data_source == "filesystem":
        connection_params = configure_filesystem_mcp(config.target_path)
        logger.info(
            "Building filesystem MCP toolset for target=%r with stdio transport",
            config.target_path,
        )
    elif data_source == "github":
        import os
        pat = config.auth_token or os.environ.get("GITHUB_PAT") or os.environ.get("GITHUB_TOKEN")
        if not pat:
            raise ValueError(
                "GitHub Personal Access Token (PAT) is required for GitHub analysis. "
                "Please set GITHUB_PAT or GITHUB_TOKEN environment variable."
            )
        from app.mcp.github_mcp import configure_github_mcp
        connection_params = configure_github_mcp(pat)
        logger.info("Building GitHub MCP toolset for target=%r", config.target_path)
    else:
        raise ValueError(f"Unknown data source: {data_source}")

    # Initialize the toolset with our connection params and filter
    # by our strict ALLOWED_MCP_TOOLS whitelist.
    return LoggingMcpToolset(
        connection_params=connection_params,
        tool_filter=list(ALLOWED_MCP_TOOLS)
    )

