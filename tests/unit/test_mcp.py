"""Unit tests for the MCP Tool Registry and Adapters."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams

from app.mcp.filesystem_mcp import (
    DEFAULT_STDIO_TIMEOUT_SECONDS,
    configure_filesystem_mcp,
)
from app.mcp.tool_registry import build_mcp_toolset, MCPConfig, ALLOWED_MCP_TOOLS


def test_allowed_mcp_tools_list():
    """Verify the list of permitted read-only tools."""
    assert len(ALLOWED_MCP_TOOLS) == 4
    assert "read_file" in ALLOWED_MCP_TOOLS
    assert "list_directory" in ALLOWED_MCP_TOOLS
    assert "search_files" in ALLOWED_MCP_TOOLS
    assert "get_file_metadata" in ALLOWED_MCP_TOOLS


def test_configure_filesystem_mcp_uses_stdio_connection_params(tmp_path):
    """Filesystem MCP must use StdioConnectionParams with a generous timeout."""
    repo = tmp_path / "repo"
    repo.mkdir()

    params = configure_filesystem_mcp(str(repo))

    assert isinstance(params, StdioConnectionParams)
    assert params.timeout == DEFAULT_STDIO_TIMEOUT_SECONDS
    assert params.server_params.args[-1] == str(repo.resolve())
    assert Path(params.server_params.cwd).resolve() == repo.resolve()


def test_build_mcp_toolset_invalid_source():
    """Verify that build_mcp_toolset raises ValueError on unknown source."""
    config = MCPConfig(target_path="/path/to/repo")
    with pytest.raises(ValueError, match="Unknown data source"):
        build_mcp_toolset("invalid_source", config)  # type: ignore


@patch("app.mcp.tool_registry.LoggingMcpToolset")
@patch("app.mcp.filesystem_mcp.configure_filesystem_mcp")
def test_build_mcp_toolset_filesystem(mock_configure_fs, mock_mcp_toolset):
    """Verify that filesystem toolset is built correctly."""
    mock_params = MagicMock()
    mock_configure_fs.return_value = mock_params
    
    config = MCPConfig(target_path="/path/to/repo")
    
    build_mcp_toolset("filesystem", config)
    
    mock_configure_fs.assert_called_once_with("/path/to/repo")
    mock_mcp_toolset.assert_called_once_with(
        connection_params=mock_params,
        tool_filter=list(ALLOWED_MCP_TOOLS)
    )


@patch("app.mcp.tool_registry.LoggingMcpToolset")
@patch("app.mcp.github_mcp.configure_github_mcp")
def test_build_mcp_toolset_github(mock_configure_gh, mock_mcp_toolset, monkeypatch):
    """Verify that github toolset is built correctly with auth token."""
    mock_params = MagicMock()
    mock_configure_gh.return_value = mock_params
    
    # 1. Test passing PAT in config
    config = MCPConfig(target_path="owner/repo", auth_token="my-secret-pat")
    build_mcp_toolset("github", config)
    
    mock_configure_gh.assert_called_once_with("my-secret-pat")
    mock_mcp_toolset.assert_called_once_with(
        connection_params=mock_params,
        tool_filter=list(ALLOWED_MCP_TOOLS)
    )

    # 2. Test fetching PAT from environment variables
    mock_configure_gh.reset_mock()
    monkeypatch.setenv("GITHUB_PAT", "env-secret-pat")
    config_no_pat = MCPConfig(target_path="owner/repo")
    
    build_mcp_toolset("github", config_no_pat)
    mock_configure_gh.assert_called_once_with("env-secret-pat")


def test_build_mcp_toolset_github_missing_token(monkeypatch):
    """Verify that ValueError is raised if GITHUB_PAT/GITHUB_TOKEN is missing."""
    monkeypatch.delenv("GITHUB_PAT", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    
    config = MCPConfig(target_path="owner/repo")
    with pytest.raises(ValueError, match="GitHub Personal Access Token"):
        build_mcp_toolset("github", config)
