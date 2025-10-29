"""API routing using FastAPI routers."""

from fastapi import APIRouter

from orchestrator.api.controllers.agent_controller import router as agent_router
from orchestrator.api.controllers.ask_digbi_controller import (
    router as ask_digbi_router,
)
from orchestrator.api.controllers.meal_rating_controller import (
    router as meal_rating_router,
)
from orchestrator.api.controllers.vector_store_controller import (
    router as vector_store_router,
)
from orchestrator.api.controllers.tool_controller import (
    router as tool_router,
)
from orchestrator.api.controllers.digbigpt_controller import (
    router as digbigpt_router,
)

router = APIRouter()

# Register routers under /api prefix
router.include_router(ask_digbi_router, prefix="/api", tags=["Ask Digbi"])
router.include_router(meal_rating_router, prefix="/api", tags=["Meal Rating"])
router.include_router(agent_router, prefix="/api", tags=["Agents"])
router.include_router(vector_store_router, prefix="/api", tags=["Vector Store"])
router.include_router(tool_router, prefix="/api", tags=["Tools"])
router.include_router(digbigpt_router, prefix="/api", tags=["DigbiGPT"])
