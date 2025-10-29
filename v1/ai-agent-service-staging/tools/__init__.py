"""Unified tools package combining tool registry and data tools."""

from .registry import (
    Tool,
    tool,
    register_tool_global,
    get_registered_tool,
    list_registered_tools,
    with_db_client,
    with_user_token,
)
from .services.tool_service import ToolService

# Import built-in tool definitions to ensure they're registered
import pkgutil
import importlib
from . import definitions as _definitions

for _module in pkgutil.iter_modules(_definitions.__path__):
    importlib.import_module(f"{_definitions.__name__}.{_module.name}")

__all__ = [
    "Tool",
    "tool",
    "register_tool_global",
    "get_registered_tool",
    "list_registered_tools",
    "with_db_client",
    "with_user_token",
    "ToolService",
]
