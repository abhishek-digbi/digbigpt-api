"""DigbiGPT controller for claims analysis."""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class DigbiGPTRequest(BaseModel):
    """Request model for DigbiGPT questions."""
    question: str
    user_id: str
    context: Optional[Dict[str, Any]] = None


@router.post("/digbigpt/ask")
async def ask_digbigpt(request_data: DigbiGPTRequest, req: Request):
    """Process a claims analysis question via DigbiGPT.
    
    Args:
        request_data: Question and user information
        req: FastAPI request object
        
    Returns:
        Dict with answer, table data, agent used, and confidence
    """
    try:
        # Get the orchestrator from app state
        digbigpt = req.app.state.AGENTS.get("digbigpt_orchestrator")
        if not digbigpt:
            raise HTTPException(status_code=500, detail="DigbiGPT orchestrator not initialized")
        
        # Process the query
        result = await digbigpt.process_query(
            question=request_data.question,
            user_id=request_data.user_id,
            context=request_data.context
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error in DigbiGPT endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

