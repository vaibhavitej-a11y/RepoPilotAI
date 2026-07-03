"""GitHub MCP client adapter."""
import sys
from google.adk.tools.mcp_tool.mcp_session_manager import StdioServerParameters

def configure_github_mcp(pat: str) -> StdioServerParameters:
    """Configure the GitHub MCP server connection parameters.
    
    This connects to the `@modelcontextprotocol/server-github` MCP server
    using the provided GitHub Personal Access Token (PAT).
    """
    command = "npx.cmd" if sys.platform == "win32" else "npx"
    
    return StdioServerParameters(
        command=command,
        args=["-y", "@modelcontextprotocol/server-github"],
        env={"GITHUB_PERSONAL_ACCESS_TOKEN": pat}
    )
