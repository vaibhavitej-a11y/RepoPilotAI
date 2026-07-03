"""Logging helpers for MCP session creation failures."""
from __future__ import annotations

import logging
from typing import Any

from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

logger = logging.getLogger(__name__)


def format_root_exception(exc: BaseException, *, _depth: int = 0) -> str:
    """Format an exception, unwrapping ExceptionGroup/TaskGroup chains."""
    indent = "  " * _depth
    lines = [f"{indent}{type(exc).__name__}: {exc}"]

    if isinstance(exc, BaseExceptionGroup):
        for index, sub_exc in enumerate(exc.exceptions):
            lines.append(f"{indent}  [{index}]")
            lines.append(format_root_exception(sub_exc, _depth=_depth + 2))

    if exc.__cause__ is not None and exc.__cause__ is not exc:
        lines.append(f"{indent}  caused by:")
        lines.append(format_root_exception(exc.__cause__, _depth=_depth + 1))

    return "\n".join(lines)


class LoggingMcpToolset(McpToolset):
    """McpToolset that logs the root cause when session creation fails."""

    async def get_tools(self, *args: Any, **kwargs: Any):
        try:
            return await super().get_tools(*args, **kwargs)
        except Exception as exc:
            logger.error(
                "MCP session creation failed for %r:\n%s",
                self._connection_params,
                format_root_exception(exc),
            )
            raise
