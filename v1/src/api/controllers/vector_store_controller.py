"""Endpoints for managing vector store files."""

import json
from typing import Any

from fastapi import APIRouter, File, Form, Request, UploadFile, Query
from fastapi.responses import JSONResponse

from agent_core.config.logging_config import logger
from orchestrator.api.schemas import ApiResponse, VectorStoreFileResponse
from orchestrator.api.services.response_generator import generate_response
from orchestrator.services.vector_store_service import VectorStoreService

router = APIRouter()


@router.post(
    "/vector-stores/{vector_store_id}/files",
    response_model=VectorStoreFileResponse,
    summary="Upload file to vector store",
    description="Upload a file to an OpenAI vector store with optional metadata.",
)
async def upload_vector_file(
    vector_store_id: str,
    request: Request,
    file: UploadFile = File(...),
    attributes: str | None = Form(None),
):
    """Upload a file to a vector store."""
    metadata = None
    if attributes:
        try:
            metadata = json.loads(attributes)
        except json.JSONDecodeError:
            return JSONResponse(
                generate_response("Invalid attributes format", 400), status_code=400
            )
    service: VectorStoreService = request.app.state.VECTOR_STORE_SERVICE
    try:
        result = await service.upload_file(vector_store_id, file, metadata)
        return JSONResponse(generate_response("File uploaded", 200, result), status_code=200)
    except Exception as e:
        logger.error("Error uploading vector store file: %s", e, exc_info=True)
        return JSONResponse(generate_response("Error uploading file", 500), status_code=500)


@router.put(
    "/vector-stores/{vector_store_id}/files/{file_id}",
    response_model=VectorStoreFileResponse,
    summary="Update file metadata",
    description="Update attributes on a vector store file.",
)
async def update_vector_file(
    vector_store_id: str,
    file_id: str,
    payload: dict,
    request: Request,
):
    """Update metadata for a vector store file."""
    attributes = payload.get("attributes")
    if not isinstance(attributes, dict):
        return JSONResponse(
            generate_response("Invalid attributes", 400), status_code=400
        )
    service: VectorStoreService = request.app.state.VECTOR_STORE_SERVICE
    try:
        result = await service.update_file_attributes(vector_store_id, file_id, attributes)
        return JSONResponse(generate_response("File updated", 200, result), status_code=200)
    except Exception as e:
        logger.error("Error updating vector store file: %s", e, exc_info=True)
        return JSONResponse(generate_response("Error updating file", 500), status_code=500)


@router.get(
    "/vector-stores/{vector_store_id}/files/{file_id}",
    response_model=VectorStoreFileResponse,
    summary="Get vector store file",
    description="Retrieve a vector store file (including attributes) by id.",
)
async def get_vector_file(
    vector_store_id: str,
    file_id: str,
    request: Request,
) -> JSONResponse:
    service: VectorStoreService = request.app.state.VECTOR_STORE_SERVICE
    try:
        result = await service.get_vector_store_file(vector_store_id, file_id)
        return JSONResponse(generate_response("File retrieved", 200, result), status_code=200)
    except Exception as e:
        logger.error("Error retrieving vector store file: %s", e, exc_info=True)
        return JSONResponse(generate_response("Error retrieving file", 500), status_code=500)


@router.get(
    "/vector-stores/{vector_store_id}/files/{file_id}/attributes",
    response_model=VectorStoreFileResponse,
    summary="Get file attributes",
    description="Retrieve only the attributes (metadata) for a vector store file.",
)
async def get_vector_file_attributes(
    vector_store_id: str,
    file_id: str,
    request: Request,
) -> JSONResponse:
    service: VectorStoreService = request.app.state.VECTOR_STORE_SERVICE
    try:
        result = await service.get_vector_store_file_attributes(vector_store_id, file_id)
        return JSONResponse(
            generate_response("Attributes retrieved", 200, result), status_code=200
        )
    except Exception as e:
        logger.error("Error retrieving vector store file attributes: %s", e, exc_info=True)
        return JSONResponse(
            generate_response("Error retrieving attributes", 500), status_code=500
        )


@router.delete(
    "/vector-stores/{vector_store_id}/files/{file_id}/attributes",
    response_model=VectorStoreFileResponse,
    summary="Clear file attributes",
    description="Remove all attributes from a vector store file (reset).",
)
async def clear_vector_file_attributes(
    vector_store_id: str,
    file_id: str,
    request: Request,
    force_recreate: bool = Query(False, description="If true, detach and reattach file if clearing fails"),
) -> JSONResponse:
    service: VectorStoreService = request.app.state.VECTOR_STORE_SERVICE
    try:
        result = await service.clear_file_attributes(vector_store_id, file_id, force_recreate=force_recreate)
        return JSONResponse(
            generate_response("Attributes cleared", 200, result), status_code=200
        )
    except Exception as e:
        logger.error("Error clearing vector store file attributes: %s", e, exc_info=True)
        return JSONResponse(
            generate_response("Error clearing attributes", 500), status_code=500
        )
