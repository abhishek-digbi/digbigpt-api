"""DigbiGPT API Controller - REST endpoints for claims database queries."""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging

from orchestrator.orchestrators.digbigpt_orchestrator import DigbiGPTOrchestrator
from agent_core.services.ai_core_service import AiCoreService
from orchestrator.services.agent_config_service import AgentConfigService

logger = logging.getLogger(__name__)

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


def get_orchestrator() -> DigbiGPTOrchestrator:
    """Dependency injection for DigbiGPT orchestrator."""
    # TODO: Get ai_service from app context in production
    # For now, create a new instance
    ai_service = AiCoreService(AgentConfigService())
    return DigbiGPTOrchestrator(ai_service)


@router.post("/ask", response_model=DigbiGPTResponse)
async def ask_digbigpt(
    request: DigbiGPTRequest,
    orchestrator: DigbiGPTOrchestrator = Depends(get_orchestrator)
):
    """
    Process a natural language query about claims data.
    
    This endpoint accepts natural language questions about healthcare claims data
    and returns structured results with both tabular data and plain-English summaries.
    
    Example:
        POST /api/digbigpt/ask
        {
            "query": "Which customers spent most on rosuvastatin in 2024?",
            "user_token": "dr_smith_123"
        }
    
    The system will:
    1. Route the question to the appropriate specialist agent
    2. Execute pre-vetted SQL queries via MCP server
    3. Apply privacy guardrails to redact PHI
    4. Return structured data with summary
    5. Log everything for audit compliance
    """
    try:
        logger.info(f"DigbiGPT query received from {request.user_id}: {request.question}")
        
        # Validate request
        if not request.question.strip():
            raise HTTPException(
                status_code=400,
                detail="Question cannot be empty"
            )
        
        if not request.user_id.strip():
            raise HTTPException(
                status_code=400,
                detail="User ID is required for audit logging"
            )
        
        # Process the query
        response = await orchestrator.process_query(
            question=request.question,
            user_id=request.user_id,
            ctx=None
        )
        
        # Add missing fields to match response schema
        response["query_time_ms"] = int(response.get("confidence", 0) * 1000)  # Mock for now
        response["timestamp"] = __import__("datetime").datetime.utcnow().isoformat()
        response["table"] = {"columns": [], "rows": response.get("table", [])}
        
        # Convert to response model
        return DigbiGPTResponse(**response)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DigbiGPT query failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process query: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """Health check endpoint for DigbiGPT service."""
    return {
        "status": "healthy",
        "service": "DigbiGPT",
        "version": "1.0.0",
        "timestamp": "2025-01-15T10:30:00Z"
    }


@router.get("/agents")
async def list_agents():
    """List available DigbiGPT specialist agents."""
    return {
        "agents": [
            {
                "id": "DRUG_SPEND_AGENT",
                "name": "Drug Spend Agent",
                "description": "Answers questions about medication costs and utilization",
                "tools": ["get_top_drug_spend", "get_duplicate_medications"]
            },
            {
                "id": "CLINICAL_HISTORY_AGENT",
                "name": "Clinical History Agent", 
                "description": "Answers questions about member diagnoses and clinical timelines",
                "tools": ["get_member_disease_history", "get_gi_new_starts"]
            },
            {
                "id": "COHORT_INSIGHTS_AGENT",
                "name": "Cohort Insights Agent",
                "description": "Answers questions about disease cohort metrics and population health",
                "tools": ["get_disease_cohort_summary", "get_top_drug_spend"]
            }
        ]
    }


@router.get("/tools")
async def list_tools():
    """List available database tools."""
    return {
        "tools": [
            {
                "name": "get_top_drug_spend",
                "description": "Returns members with highest spend on a specific drug",
                "parameters": ["drug_name", "year", "limit"]
            },
            {
                "name": "get_member_disease_history",
                "description": "Returns diagnosis history for a specific member",
                "parameters": ["member_id_hash"]
            },
            {
                "name": "get_gi_new_starts",
                "description": "Returns members who started GI medications in date range",
                "parameters": ["start_date", "end_date", "limit"]
            },
            {
                "name": "get_duplicate_medications",
                "description": "Identifies members on multiple similar medications",
                "parameters": ["drug_pattern", "days_lookback", "limit"]
            },
            {
                "name": "get_disease_cohort_summary",
                "description": "Returns summary statistics for members in a disease cohort",
                "parameters": ["disease_category", "year"]
            }
        ]
    }

