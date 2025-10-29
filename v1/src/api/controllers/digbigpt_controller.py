"""DigbiGPT API Controller - REST endpoints using AI Agent Service staging."""

import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging
from datetime import datetime
import os

logger = logging.getLogger(__name__)

# Add ai-agent-service-staging to Python path
staging_path = Path(__file__).parent.parent.parent.parent / "ai-agent-service-staging"
if str(staging_path) not in sys.path:
    sys.path.insert(0, str(staging_path))

router = APIRouter(prefix="/digbigpt", tags=["DigbiGPT"])


class DigbiGPTRequest(BaseModel):
    """Request schema for DigbiGPT queries."""
    question: str = Field(..., description="Natural language question about claims data")
    user_id: str = Field(..., description="User identifier for audit logging")
    context: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional context (conversation history, user preferences)"
    )


class DigbiGPTResponse(BaseModel):
    """Response schema for DigbiGPT queries."""
    answer: str = Field(..., description="Plain-English summary of the results")
    table: Optional[Dict[str, Any]] = Field(
        None,
        description="Structured data with 'columns' and 'rows' keys"
    )
    agent_used: str = Field(..., description="Which agent handled the query")
    confidence: float = Field(..., description="Router confidence score (0.0-1.0)")
    query_time_ms: int = Field(..., description="Query execution time in milliseconds")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


# Initialize staging services lazily
_orchestrator: Optional[Any] = None


def get_orchestrator(request: Request):
    """Get or initialize the DigbiGPT orchestrator with staging services.
    
    Args:
        request: FastAPI request object with app state
        
    Returns:
        Initialized DigbiGPTOrchestrator instance
    """
    global _orchestrator
    
    if _orchestrator is not None:
        return _orchestrator
    
    try:
        # Lazy import to avoid circular imports
        from agent_core.services.ai_core_service import AiCoreService
        from agent_core.services.prompt_management.langfuse_service import LangFuseService
        from agent_core.services.adapters.adapter_registry import AdapterRegistry
        from agent_core.services.adapters.openai_service import OpenAIService
        from tools import ToolService
        from orchestrator.services.database_agent_logger import DatabaseAgentLogger
        from orchestrator.repositories.agent_logs_repository import AgentLogsRepository
        from orchestrator.orchestrators.digbigpt_orchestrator import DigbiGPTOrchestrator
        
        # Check if staging services are already initialized in app state
        if hasattr(request.app.state, 'AI_CORE_SERVICE'):
            ai_core_service = request.app.state.AI_CORE_SERVICE
            logger.info("Using existing AI_CORE_SERVICE from app state")
        else:
            # Initialize staging services
            logger.info("Initializing AI Agent Service staging components")
            
            # Get DB client from app state or create new one
            db_client = getattr(request.app.state, 'DB_CLIENT', None)
            if db_client is None:
                from utils.db import DBClient
                db_client = DBClient()
                logger.info("Created new DBClient for staging services")
            
            # Initialize LangFuse (optional, can work without it)
            env = os.getenv("ENV", "development")
            langfuse = LangFuseService(
                env=env,
                secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
                public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
                host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
            )
            
            # Initialize OpenAI service
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if not openai_api_key:
                logger.warning("OPENAI_API_KEY not set - agents will not function")
            openai_service = OpenAIService(api_key=openai_api_key or "")
            
            # Initialize adapter registry and tool service
            adapter_registry = AdapterRegistry(openai_service)
            data_core = ToolService(db_client)
            
            # Initialize agent logger
            agent_logs_repo = AgentLogsRepository(db_client)
            agent_logger = DatabaseAgentLogger(agent_logs_repo)
            
            # Initialize AI Core Service
            ai_core_service = AiCoreService(
                langfuse=langfuse,
                registry=adapter_registry,
                data_core=data_core,
                agent_logger=agent_logger
            )
            
            # Store in app state for reuse
            request.app.state.AI_CORE_SERVICE = ai_core_service
            logger.info("AI_CORE_SERVICE initialized and stored in app state")
        
        # Create orchestrator
        _orchestrator = DigbiGPTOrchestrator(ai_core_service)
        logger.info("DigbiGPTOrchestrator initialized successfully")
        
        return _orchestrator
        
    except Exception as e:
        logger.error(f"Failed to initialize DigbiGPT orchestrator: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize DigbiGPT service: {str(e)}"
        )


@router.post("/ask", response_model=DigbiGPTResponse)
async def ask_digbigpt(
    request: Request,
    req: DigbiGPTRequest
):
    """Process a natural language query about healthcare claims data.
    
    This endpoint routes questions to specialized AI agents that analyze
    claims data and provide insights with PHI redaction for HIPAA compliance.
    
    Args:
        request: FastAPI request object
        req: DigbiGPT request with question and user_id
        
    Returns:
        DigbiGPTResponse with answer, table data, and metadata
    """
    try:
        logger.info(f"DigbiGPT query received from {req.user_id}: {req.question}")
        
        # Validate inputs
        if not req.question.strip():
            raise HTTPException(
                status_code=400,
                detail="Question cannot be empty"
            )
        
        if not req.user_id.strip():
            raise HTTPException(
                status_code=400,
                detail="User ID is required for audit logging"
            )
        
        # Get orchestrator and process query
        orchestrator = get_orchestrator(request)
        response = await orchestrator.process_query(
            question=req.question,
            user_id=req.user_id,
            context=req.context
        )
        
        return DigbiGPTResponse(**response)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DigbiGPT query failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process query: {str(e)}"
        )


@router.get("/agents")
async def list_agents():
    """List available DigbiGPT agents and their capabilities.
    
    Returns:
        Dictionary with agent information
    """
    return {
        "agents": [
            {
                "id": "DRUG_SPEND_AGENT",
                "name": "Drug Spend Agent",
                "description": "Analyzes medication costs and utilization patterns",
                "tools": ["get_top_drug_spend", "get_duplicate_medications"],
                "capabilities": [
                    "Top drug spenders analysis",
                    "Duplicate therapy detection",
                    "Cost trend analysis"
                ]
            },
            {
                "id": "CLINICAL_HISTORY_AGENT",
                "name": "Clinical History Agent",
                "description": "Analyzes member diagnoses and clinical timelines",
                "tools": ["get_member_disease_history", "get_gi_new_starts"],
                "capabilities": [
                    "Member diagnosis history",
                    "GI medication tracking",
                    "Clinical timeline analysis"
                ]
            },
            {
                "id": "COHORT_INSIGHTS_AGENT",
                "name": "Cohort Insights Agent",
                "description": "Analyzes disease cohort metrics and population health",
                "tools": ["get_disease_cohort_summary", "get_top_drug_spend"],
                "capabilities": [
                    "Population health metrics",
                    "Cohort-level analysis",
                    "Disease burden assessment"
                ]
            }
        ]
    }


@router.get("/tools")
async def list_tools():
    """List available database tools for claims analysis.
    
    Returns:
        Dictionary with tool information
    """
    return {
        "tools": [
            {
                "name": "get_top_drug_spend",
                "description": "Returns members with highest spend on a specific drug",
                "parameters": {
                    "drug_name": "Name of the drug (required)",
                    "year": "Year to filter (default: 2023)",
                    "limit": "Max results (default: 10)"
                }
            },
            {
                "name": "get_member_disease_history",
                "description": "Returns diagnosis history for a specific member",
                "parameters": {
                    "member_id_hash": "Hashed member identifier (required)"
                }
            },
            {
                "name": "get_gi_new_starts",
                "description": "Returns members who started GI medications in date range",
                "parameters": {
                    "start_date": "Start date YYYY-MM-DD (required)",
                    "end_date": "End date YYYY-MM-DD (required)",
                    "limit": "Max results (default: 50)"
                }
            },
            {
                "name": "get_duplicate_medications",
                "description": "Identifies members on multiple similar medications",
                "parameters": {
                    "drug_pattern": "Drug pattern to search (required)",
                    "days_lookback": "Days to look back (default: 90)",
                    "limit": "Max results (default: 50)"
                }
            },
            {
                "name": "get_disease_cohort_summary",
                "description": "Returns summary statistics for a disease cohort",
                "parameters": {
                    "disease_category": "Disease category (required)",
                    "year": "Year to filter (default: 2023)"
                }
            }
        ]
    }
