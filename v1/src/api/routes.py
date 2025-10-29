"""API routing using FastAPI routers."""

from fastapi import APIRouter

from src.api.controllers.digbigpt_controller import (
    router as digbigpt_router,
)

router = APIRouter()

# Register routers under /api prefix
router.include_router(digbigpt_router, prefix="/api", tags=["DigbiGPT"])
