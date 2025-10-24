"""Agent management endpoints using FastAPI."""

import asyncio
import requests
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from agent_core.config.logging_config import logger
from agent_core.config.schema import AgentConfig
from agent_core.services.model_context import BaseModelContext
from tools.utils.digbi_api_util import make_digbi_api_call
from orchestrator.api.services.response_generator import generate_response
from orchestrator.api.schemas import (
    RunAgentRequest,
    RunAgentResponse,
    CreateAgentResponse,
    UpdateAgentResponse,
    AgentListResponse,
    AgentLogsResponse,
    AgentCreateRequest,
    AgentUpdateRequest,
)
from orchestrator.services.agent_config_service import AgentConfigService
from utils.db_ops import insert_agent_config, update_agent_config
from utils.env_loader import get_env_var

router = APIRouter()

@router.post(
    "/run-orchestrator/{id}",
    response_model=RunAgentResponse,
    summary="Run orchestrator",
    description="Execute a configured orchestrator and return the result."
)
async def run_orchestrator(id: str, payload: RunAgentRequest, request: Request):
    """Run the specified orchestrator using the supplied context."""
    logger.info("Received sync request for orchestrator=%s with data: %s", id, payload)

    ctx = BaseModelContext(
        context_id=payload.query_id,
        query=payload.query,
        feature_context=payload.feature_context,
        user_type=payload.user_type,
        conversation_history=payload.conversation_history,
        data=payload.data or {},
        user_token=payload.user_token,
        query_id=payload.query_id,
    )
    # Hint the adapter to start a fresh trace for background execution
    try:
        if isinstance(ctx.data, dict):
            ctx.data["__force_new_trace"] = True
    except Exception:
        pass

    try:
        result = await request.app.state.AGENTS[id].ask(ctx)
        return JSONResponse(generate_response("Success", 200, result), status_code=200)
    except Exception as e:
        logger.error("Error processing agent task: %s", str(e), exc_info=True)
        return JSONResponse(generate_response("Error processing orchestrator task", 500), status_code=500)



@router.post(
    "/run-orchestrator-async/{id}",
    response_model=RunAgentResponse,
    summary="Run orchestrator Async",
    description="Execute a configured orchestrator and return the result."
)
async def run_orchestrator_async(id: str, payload: RunAgentRequest, request: Request):
    """Run the specified orchestrator using the supplied context."""
    logger.info("Received run async request for orchestrator=%s with data: %s", id, payload)

    ctx = BaseModelContext(
        context_id=payload.query_id,
        query=payload.query,
        feature_context=payload.feature_context,
        user_type=payload.user_type,
        conversation_history=payload.conversation_history,
        data=payload.data or {},
        user_token=payload.user_token,
        query_id=payload.query_id,
    )

    async def _process_orchestator_and_callback():
        try:
            result = await request.app.state.AGENTS[id].ask(ctx)
            callback = payload.data.get("callback", {})
            if callback:
                callback_method = callback["method"]
                callback_url = callback["url"]
                callback_body: dict = callback["body"]
                callback_body.update(result)
                await make_digbi_api_call(callback_method, get_env_var("DIGBI_URL") + callback_url, callback_body, {"user-id": ctx.user_token})
        except Exception as e:
            logger.error("Error in process_orchestator_and_callback : %s", str(e), exc_info=True)

    # Start the background task
    asyncio.create_task(_process_orchestator_and_callback())

    # Return immediately
    return JSONResponse(
        content=generate_response("Request accepted and processing in background", 202),
        status_code=202
    )

@router.post(
    "/run-agent-async/{agent_id}",
    response_model=RunAgentResponse,
    summary="Run agent async",
    description="Execute a configured orchestrator and return the result."
)
async def run_agent_async(agent_id: str, payload: RunAgentRequest, request: Request):
    """Run the specified orchestrator using the supplied context."""
    logger.info("Received async run request for agent=%s with data: %s", agent_id, payload)
    ai_core_service = request.app.state.AI_CORE_SERVICE
    ctx = BaseModelContext(
        context_id=payload.query_id,
        query=payload.query,
        feature_context=payload.feature_context,
        user_type=payload.user_type,
        conversation_history=payload.conversation_history,
        data=payload.data or {},
        user_token=payload.user_token,
        query_id=payload.query_id,
    )

    async def _process_agent_and_callback():
        try:
            agent_response = await ai_core_service.run_agent(agent_id, ctx)
            callback = payload.data.get("callback", {})
            if callback:
                callback_method = callback["method"]
                callback_url = callback["url"]
                callback_body: dict = callback["body"]
                result: dict = {"message" : agent_response}
                callback_body.update(response=result)
                await make_digbi_api_call(callback_method, get_env_var("DIGBI_URL") + callback_url, callback_body, {"user-id": ctx.user_token})
        except Exception as e:
            logger.error("Error in process_agent_run_and_callback : %s", str(e), exc_info=True)

    # Start the background task
    asyncio.create_task(_process_agent_and_callback())

    # Return immediately
    return JSONResponse(
        content=generate_response("Request accepted and processing in background", 202),
        status_code=202
    )


@router.post(
    "/run-agent/{agent_id}",
    response_model=RunAgentResponse,
    summary="Run agent",
    description="Execute a configured agent and return the result."
)
async def run_agent(agent_id: str, payload: RunAgentRequest, request: Request):
    """Run the specified agent using the supplied context."""
    logger.info("Received request for agent_id=%s with data: %s", agent_id, payload)

    ai_core_service = request.app.state.AI_CORE_SERVICE
    ctx = BaseModelContext(
        context_id=payload.query_id,
        query=payload.query,
        feature_context=payload.feature_context,
        user_type=payload.user_type,
        conversation_history=payload.conversation_history,
        data=payload.data or {},
        user_token=payload.user_token,
        query_id=payload.query_id,
    )

    try:
        logger.info("Received request")
        result = await ai_core_service.run_agent(agent_id, ctx)
        return JSONResponse(generate_response("Success", 200, result), status_code=200)
    except Exception as e:
        logger.error("Error processing agent run task: %s", str(e), exc_info=True)
        return JSONResponse(generate_response("Error processing agent run task", 500), status_code=500)


@router.post(
    "/agents",
    response_model=CreateAgentResponse,
    summary="Create agent",
    description="Create a new agent configuration."
)
async def create_agent(payload: AgentCreateRequest, request: Request):
    """Create a new agent definition."""
    logger.info("Received request to create agent: %s", payload)

    if not (payload.id and payload.langfuse_prompt_key):
        logger.warning("Invalid input data for creating agent")
        return JSONResponse(generate_response("Invalid input data", 400), status_code=400)

    cfg = AgentConfig(
        id=payload.id,
        name=payload.name or payload.id,
        provider=payload.provider or "openai",
        model=payload.model or "gpt-4o",
        langfuse_prompt_key=payload.langfuse_prompt_key,
        text_format=payload.text_format,
        assistant_id=payload.assistant_id,
        instructions=payload.instructions,
        vector_store_ids=payload.vector_store_ids,
        tools=payload.tools,
        temperature=payload.temperature,
        top_p=payload.top_p,
    )

    db = request.app.state.DB_CLIENT
    try:
        insert_agent_config(cfg, db)
        return JSONResponse(generate_response("Agent created", 201), status_code=201)
    except Exception as e:
        logger.error("Failed to create agent %s: %s", payload.id, e, exc_info=True)
        return JSONResponse(generate_response("Error creating agent", 500), status_code=500)


@router.put(
    "/agents/{agent_id}",
    response_model=UpdateAgentResponse,
    summary="Update agent",
    description="Update an existing agent configuration."
)
async def update_agent(agent_id: str, payload: AgentUpdateRequest, request: Request):
    """Update the configuration of an existing agent."""
    logger.info("Received request to update agent %s: %s", agent_id, payload)

    if not payload.langfuse_prompt_key:
        logger.warning("Invalid input data for updating agent")
        return JSONResponse(generate_response("Invalid input data", 400), status_code=400)

    cfg = AgentConfig(
        id=agent_id,
        name=payload.name or agent_id,
        provider=payload.provider or "openai",
        model=payload.model or "gpt-4o",
        langfuse_prompt_key=payload.langfuse_prompt_key,
        text_format=payload.text_format,
        assistant_id=payload.assistant_id,
        instructions=payload.instructions,
        vector_store_ids=payload.vector_store_ids,
        tools=payload.tools,
        temperature=payload.temperature,
        top_p=payload.top_p,
    )

    db = request.app.state.DB_CLIENT
    try:
        update_agent_config(cfg, db)
        return JSONResponse(generate_response("Agent updated", 200), status_code=200)
    except KeyError:
        logger.warning("Agent %s not found", agent_id)
        return JSONResponse(generate_response("Agent not found", 404), status_code=404)
    except Exception as e:
        logger.error("Failed to update agent %s: %s", agent_id, e, exc_info=True)
        return JSONResponse(generate_response("Error updating agent", 500), status_code=500)


@router.get(
    "/agents",
    response_model=AgentListResponse,
    summary="List agents",
    description="Return all configured agents."
)
async def list_agents(request: Request):
    """Return all configured agents."""
    db = request.app.state.DB_CLIENT
    try:
        agents = AgentConfigService.fetch_all_agents(db)
        result = [
            {
                "id": a.id,
                "name": a.name,
                "provider": a.provider,
                "model": a.model,
                "langfuse_prompt_key": a.langfuse_prompt_key,
                "text_format": a.text_format,
                "assistant_id": a.assistant_id,
                "instructions": a.instructions,
                "vector_store_ids": a.vector_store_ids,
                "tools": a.tools,
                "temperature": a.temperature,
                "top_p": a.top_p,
            }
            for a in agents
        ]
        return JSONResponse(generate_response("Success", 200, result), status_code=200)
    except Exception as e:
        logger.error("Failed to fetch agents: %s", e, exc_info=True)
        return JSONResponse(generate_response("Error fetching agents", 500), status_code=500)


@router.get(
    "/agent-logs",
    response_model=AgentLogsResponse,
    summary="Get agent logs",
    description="Retrieve agent execution logs for a context ID."
)
def get_agent_logs(request: Request, context_id: str | None = None):
    """
    Retrieve agent logs for a specific context_id.

    Query Parameters:
        context_id: The unique identifier for the conversation context (required)

    Returns:
        JSON response containing the logs or an error message
    """
    logger.info(f"Fetching logs for context_id: {context_id}")

    if not context_id:
        logger.warning("No context_id provided")
        return JSONResponse(content=generate_response("context_id is required", 400), status_code=400)

    try:
        # Get logs for the specified context_id using the pre-initialized repository
        logs = request.app.state.repositories["agent_logs_repo"].get_logs_by_context(context_id)

        # Format the response
        formatted_logs = []
        for log in logs:
            try:
                # Safely format timestamps
                timestamp = (
                    log.get("timestamp").isoformat()
                    if hasattr(log.get("timestamp"), 'isoformat')
                    else str(log.get("timestamp"))
                )
                created_at = (
                    log.get("created_at").isoformat()
                    if hasattr(log.get("created_at"), 'isoformat')
                    else str(log.get("created_at"))
                )

                formatted_log = {
                    "id": log.get("id"),
                    "agent_id": log.get("agent_id"),
                    "response": log.get("response"),
                    "timestamp": timestamp,
                    "context_id": log.get("context_id"),
                    "user_token": log.get("user_token"),
                    "model_context": log.get("model_context"),
                    "metadata": log.get("metadata"),
                    "created_at": created_at
                }
                formatted_logs.append(formatted_log)
            except Exception as e:
                logger.warning(f"Error formatting log entry: {e}", exc_info=True)
                continue

        return JSONResponse(
            content=generate_response(
                "Logs retrieved successfully",
                200,
                {"logs": formatted_logs}
            ),
            status_code=200
        )

    except Exception as e:
        error_msg = f"Error retrieving logs: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return JSONResponse(content=generate_response(error_msg, 500), status_code=500)
