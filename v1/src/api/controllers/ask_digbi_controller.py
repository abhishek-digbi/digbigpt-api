"""Ask Digbi related endpoints using FastAPI."""
import time

import asyncio
import requests
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from agent_core.config.logging_config import logger
from agent_core.services.model_context import BaseModelContext
from app.metrics import track_execution
from tools.services.digbi_service import send_ask_digbi_response
from orchestrator.api.schemas import AskDigbiRequest, AskDigbiResponse
from orchestrator.api.services.response_generator import generate_response

router = APIRouter()


@router.post(
    "/ask-digbi",
    response_model=AskDigbiResponse,
    summary="Ask Digbi asynchronously",
    description="Submit a query to Digbi and receive the response via callback."
)
@track_execution("ask_digbi_async")
async def ask_digbi_async(payload: AskDigbiRequest, request: Request):
    """Enqueue an Ask Digbi request for asynchronous processing."""
    logger.info("Received request at /api/ask-digbi with data: %s", payload)
    if not (payload.context and payload.user_token):
        logger.warning("Invalid input data for ask_digbi")
        return JSONResponse(generate_response("Invalid input data", 400), status_code=400)

    query = payload.query
    query_id = payload.query_id
    context = payload.context.model_dump()
    user_token = payload.user_token
    user_type = payload.user_type

    ask_digbi_agent = request.app.state.AGENTS["ask_digbi_agent"]

    logger.info("Deferring processing of ask-digbi task")
    asyncio.create_task(process_ask_digbi_task(ask_digbi_agent, query, query_id, context, user_token, user_type))
    return JSONResponse(generate_response("Request accepted", 202), status_code=202)


@router.post(
    "/ask-digbi-sync",
    response_model=AskDigbiResponse,
    summary="Ask Digbi synchronously",
    description="Process a Digbi query and return the answer directly."
)
@track_execution("ask_digbi_sync")
async def ask_digbi_sync(payload: AskDigbiRequest, request: Request):
    """Handle an Ask Digbi request and return the result in the response."""
    logger.info("Received request at /api/ask-digbi with data: %s", payload)
    if not (payload.context and payload.user_token):
        logger.warning("Invalid input data for ask_digbi")
        return JSONResponse(generate_response("Invalid input data", 400), status_code=400)

    query = payload.query
    query_id = payload.query_id
    context = payload.context.model_dump()
    user_token = payload.user_token
    user_type = payload.user_type

    ask_digbi_agent = request.app.state.AGENTS["ask_digbi_agent"]

    logger.info("Processing ask-digbi task")
    try:
        result = await process_ask_digbi_task(ask_digbi_agent, query, query_id, context, user_token, user_type)
        return JSONResponse(generate_response("Success", 200, result), status_code=200)
    except Exception as e:
        logger.error("Error processing ask digbi query: %s", str(e), exc_info=True)
        return JSONResponse(generate_response("Error processing ask digbi query", 500), status_code=500)


async def process_ask_digbi_task(agent, query, query_id, context, user_token, user_type):
    response_data = {"query_id": query_id, "response": None, "conversation_summary": ""}
    start_time = time.perf_counter()
    try:
        ctx = BaseModelContext(
            feature_context="ASK_DIGBI",
            context_id=query_id,
            conversation_history=context.get("conversation", {}),
            query=query,
            query_id=query_id,
            user_token=user_token,
            user_type=user_type
        )
        app_ctx = context.get("app") or {}
        screen_info = app_ctx.get("screen_info", "")
        entity_id = app_ctx.get("entity_id", "")
        if screen_info is not None:
            ctx.screen_info = screen_info
            ctx.data["screen_info"] = screen_info
        if entity_id is not None:
            ctx.entity_id = entity_id
            ctx.data["entity_id"] = entity_id

        response = await agent.ask(ctx)
        logger.info(f"response from ask Digbi: {response}")
        response_data["response"] = response
        response_data["response"]["agent_statuses"] = ctx.agent_statuses
        response_data["response"]['total_response_time'] = f"{time.perf_counter() - start_time:.2f}"
        response_data["response"]['query'] = query
        success = await send_ask_digbi_response(response_data)

        if not success:
            logger.warning("Callback failed for query_id: %s", query_id)

    except AttributeError as attr_err:
        logger.error("AttributeError encountered: %s", str(attr_err), exc_info=True)
    except requests.exceptions.RequestException as req_err:
        logger.error("RequestException encountered: %s", str(req_err), exc_info=True)
    except Exception as e:
        logger.error("Unexpected error processing ask-digbi task: %s", str(e), exc_info=True)
    finally:
        return response_data
