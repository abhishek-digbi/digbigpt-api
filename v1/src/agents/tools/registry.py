from dataclasses import dataclass
from typing import Any, Callable, Optional, Dict, List
import inspect
from functools import wraps

from agent_core.config.logging_config import logger

@dataclass
class Tool:
    """Simple representation of a function-based tool."""

    name: str
    description: str
    func: Callable[..., Any]
    strict_schema: bool = True


_TOOL_REGISTRY: Dict[str, "Tool"] = {}


def register_tool_global(t: "Tool") -> "Tool":
    """Register a tool in the global registry and return it."""
    _TOOL_REGISTRY[t.name] = t
    return t


def get_registered_tool(name: str) -> Optional["Tool"]:
    """Look up a tool previously registered via :func:`register_tool_global`."""
    return _TOOL_REGISTRY.get(name)


def list_registered_tools() -> List["Tool"]:
    """Return all globally registered tools."""
    return list(_TOOL_REGISTRY.values())


def tool(
    func: Callable[..., Any] | None = None,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    strict_schema: Optional[bool] = True,
) -> Tool | Callable[[Callable[..., Any]], Tool]:
    """Decorator to convert a function into a :class:`Tool`.

    Both synchronous and asynchronous functions are supported without wrapping.
    """

    def _create(f: Callable[..., Any]) -> Tool:
        tool_name = name or f.__name__

        if inspect.iscoroutinefunction(f):
            @wraps(f)
            async def _logged(*args, **kwargs):
                logger.info("Tool %s invoked", tool_name)
                return await f(*args, **kwargs)
        else:
            @wraps(f)
            def _logged(*args, **kwargs):
                logger.info("Tool %s invoked", tool_name)
                return f(*args, **kwargs)

        final_description = description or (f.__doc__ or "").strip()
        if not final_description:
            logger.warning("Creating tool %s without a description", tool_name)

        tool_obj = Tool(
            name=tool_name,
            description=final_description,
            func=_logged,
            strict_schema=strict_schema,
        )
        return register_tool_global(tool_obj)

    if callable(func):
        return _create(func)

    def decorator(real_func: Callable[..., Any]) -> Tool:
        return _create(real_func)

    return decorator


def with_db_client(t: Tool, db_client: Any) -> Tool:
    """Return a new Tool with ``db_client`` bound if the underlying function expects it.
    
    Args:
        t: The original Tool instance
        db_client: The database client instance to inject
        
    Returns:
        A new Tool with the db_client bound if the function expects it,
        otherwise returns the original Tool unchanged.
    """
    import inspect
    from functools import wraps

    sig = inspect.signature(t.func)
    if "db_client" not in sig.parameters:
        return t

    if inspect.iscoroutinefunction(t.func):
        @wraps(t.func)
        async def _wrapped(*args, **kwargs):
            return await t.func(*args, db_client=db_client, **kwargs)
    else:
        @wraps(t.func)
        def _wrapped(*args, **kwargs):
            return t.func(*args, db_client=db_client, **kwargs)

    # Remove db_client from the signature since we're binding it
    params = [p for name, p in sig.parameters.items() if name != "db_client"]
    _wrapped.__signature__ = inspect.Signature(parameters=params)

    return Tool(
        name=t.name,
        description=t.description,
        func=_wrapped,
        strict_schema=t.strict_schema
    )


def with_user_token(t: Tool, user_token: str) -> Tool:
    """Return a new Tool with ``user_token`` bound if the underlying function expects it."""
    import inspect
    from functools import wraps

    sig = inspect.signature(t.func)
    if "user_token" not in sig.parameters:
        return t

    if inspect.iscoroutinefunction(t.func):
        @wraps(t.func)
        async def _wrapped(*args, **kwargs):
            return await t.func(user_token, *args, **kwargs)
    else:
        @wraps(t.func)
        def _wrapped(*args, **kwargs):
            return t.func(user_token, *args, **kwargs)

    params = [p for name, p in sig.parameters.items() if name != "user_token"]
    _wrapped.__signature__ = inspect.Signature(parameters=params)

    return Tool(
        name=t.name,
        description=t.description,
        func=_wrapped,
        strict_schema=t.strict_schema
    )
