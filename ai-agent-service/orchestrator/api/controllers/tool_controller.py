"""Tool execution endpoints using FastAPI.

Provides a simple API to list and execute registered tools.
"""

import inspect
from typing import Any, Dict
from datetime import date, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from agent_core.config.logging_config import logger
from orchestrator.api.schemas import ApiResponse, ExecuteToolRequest, ExecuteToolResponse, VariablesRequest, VariablesResponse
from orchestrator.api.services.response_generator import generate_response
from tools import get_registered_tool, list_registered_tools, with_user_token, Tool


router = APIRouter()


@router.get(
    "/tools",
    response_model=ApiResponse[list[dict]],
    summary="List available tools",
    description="List names and descriptions of registered tools.",
)
async def list_tools(request: Request):
    """Return available tool names and descriptions from both registries."""
    try:
        # Tools provided by the ToolService instance
        data_core = request.app.state.AI_CORE_SERVICE.data_core
        service_tools = {t.name: {"name": t.name, "description": t.description} for t in getattr(data_core, "tools", [])}

        # Globally registered tools from the registry
        global_tools = {
            t.name: {"name": t.name, "description": t.description}
            for t in list_registered_tools()
        }

        # Merge, preferring service definitions on conflict
        combined: Dict[str, Dict[str, Any]] = {**global_tools, **service_tools}
        tools_list = list(combined.values())
        tools_list.sort(key=lambda x: x["name"])  # stable order

        return JSONResponse(generate_response("Success", 200, tools_list), status_code=200)
    except Exception as e:
        logger.error("Error listing tools: %s", e, exc_info=True)
        return JSONResponse(generate_response("Error listing tools", 500), status_code=500)


@router.post(
    "/tools/execute/{tool_name}",
    response_model=ExecuteToolResponse,
    summary="Execute a tool",
    description="Execute a registered tool by name with optional arguments.",
)
async def execute_tool(tool_name: str, payload: ExecuteToolRequest, request: Request):
    """Execute a tool from either ToolService or global registry.

    The handler attempts to resolve the tool in this order:
    1. ToolService.get_tool(tool_name)
    2. Global registry via get_registered_tool(tool_name)
    """
    logger.info("Execute tool request: %s with payload: %s", tool_name, payload)

    try:
        ai_core_service = request.app.state.AI_CORE_SERVICE
        data_core = ai_core_service.data_core

        t: Tool | None = getattr(data_core, "get_tool", lambda n: None)(tool_name)
        if t is None:
            t = get_registered_tool(tool_name)

        if t is None:
            return JSONResponse(
                generate_response(f"Tool '{tool_name}' not found", 404),
                status_code=404,
            )

        # Optionally bind user_token if tool expects it
        if payload.user_token:
            t = with_user_token(t, payload.user_token)

        args = payload.args or {}

        # Inject use_cache if the tool supports it and caller provided it
        try:
            sig = inspect.signature(t.func)
            if "use_cache" in sig.parameters and payload.use_cache is not None and "use_cache" not in args:
                args["use_cache"] = payload.use_cache
        except Exception:
            pass

        # Call the underlying function correctly for async/sync tools
        if inspect.iscoroutinefunction(t.func):
            result = await t.func(**args)
        else:
            result = t.func(**args)

        # If upstream returned no result (e.g., failed API call), surface as 502
        if result is None:
            err_details = {
                "tool": tool_name,
                "args_keys": sorted(list(args.keys())),
                "has_user_token": bool(payload.user_token),
            }
            return JSONResponse(
                generate_response("Upstream tool returned no result", 502, err_details),
                status_code=502,
            )

        return JSONResponse(generate_response("Success", 200, result), status_code=200)
    except TypeError as te:
        # Likely due to unexpected arguments/signature mismatch
        logger.error("Tool invocation error for %s: %s", tool_name, te, exc_info=True)
        return JSONResponse(
            generate_response("Invalid arguments for tool", 400), status_code=400
        )
    except Exception as e:
        logger.error("Error executing tool %s: %s", tool_name, e, exc_info=True)
        return JSONResponse(generate_response("Error executing tool", 500), status_code=500)


@router.post(
    "/tools/variables",
    response_model=VariablesResponse,
    summary="Resolve variables",
    description="Fetch one or more variables via ToolService processing, to test default processing and caching.",
)
async def resolve_variables(payload: VariablesRequest, request: Request):
    """Resolve variables using the same path used during prompt hydration.

    Supports disabling cache and an optional last_num_days hint for time-range
    variables (if configured in API_DATA_CONFIG).
    """
    try:
        data_core = request.app.state.AI_CORE_SERVICE.data_core
        from_date = to_date = None
        if payload.last_num_days:
            to_date = date.today()
            from_date = to_date - timedelta(days=payload.last_num_days)

        result = data_core.process_variables(
            payload.user_token,
            payload.variables,
            from_date=from_date,
            to_date=to_date,
            use_cache=True if payload.use_cache is None else bool(payload.use_cache),
        )
        return JSONResponse(generate_response("Success", 200, result), status_code=200)
    except Exception as e:
        logger.error("Error resolving variables: %s", e, exc_info=True)
        return JSONResponse(generate_response("Error resolving variables", 500), status_code=500)
