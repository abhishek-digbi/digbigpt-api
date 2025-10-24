#!/usr/bin/env python3
"""
DigbiGPT API Service for Custom GPT Integration
Simplified FastAPI service that provides the DigbiGPT endpoint for ChatGPT Enterprise.
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="DigbiGPT API",
    description="Claims database query API for DigbiGPT Custom GPT",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware for Custom GPT
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class DigbiGPTRequest(BaseModel):
    """Request schema for DigbiGPT queries."""
    question: str = Field(..., description="Natural language question about claims data")
    user_id: str = Field(..., description="User identifier for audit logging")

class DigbiGPTResponse(BaseModel):
    """Response schema for DigbiGPT queries."""
    answer: str = Field(..., description="Plain-English summary of the results")
    table: Optional[Dict[str, Any]] = Field(None, description="Structured data with columns and rows")
    sql_executed: Optional[str] = Field(None, description="The SQL query that was executed")
    confidence: float = Field(..., description="Confidence score (0.0-1.0)")
    agent_used: str = Field(..., description="Which agent handled the query")

class ClaimsServerClient:
    """Client for communicating with claims server."""
    
    def __init__(self, url: str = "http://localhost:8811"):
        self.url = url
        
    async def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Call a claims server tool and return result."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.url}/tools/call",
                    json={"name": tool_name, "arguments": args},
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                
                if result.get("is_error"):
                    return {
                        "error": result["content"][0].get("error", "Unknown error"),
                        "columns": [],
                        "rows": []
                    }
                
                return result["content"][0]
        except Exception as e:
            logger.error(f"Claims server tool call failed for {tool_name}: {e}")
            return {
                "error": f"Failed to call {tool_name}",
                "details": str(e),
                "columns": [],
                "rows": []
            }

# Initialize claims server client
claims_client = ClaimsServerClient()

class DigbiGPTOrchestrator:
    """Simplified orchestrator for DigbiGPT queries."""
    
    # Agent routing keywords
    DRUG_SPEND_KEYWORDS = [
        "drug", "medication", "spend", "cost", "price", "expensive",
        "pharmacy", "prescription", "duplicate", "statin", "benzo"
    ]
    
    CLINICAL_KEYWORDS = [
        "diagnosis", "disease", "condition", "history", "timeline",
        "patient", "member", "icd", "gi", "gastrointestinal"
    ]
    
    COHORT_KEYWORDS = [
        "cohort", "population", "group", "hypertension", "diabetes",
        "summary", "metrics", "aggregate", "total"
    ]
    
    def _route_query(self, question: str) -> str:
        """Route question to the appropriate specialist agent based on keywords."""
        question_lower = question.lower()
        
        # Check for drug/spend keywords
        if any(keyword in question_lower for keyword in self.DRUG_SPEND_KEYWORDS):
            return "DRUG_SPEND_AGENT"
        
        # Check for clinical keywords
        if any(keyword in question_lower for keyword in self.CLINICAL_KEYWORDS):
            return "CLINICAL_HISTORY_AGENT"
        
        # Check for cohort keywords
        if any(keyword in question_lower for keyword in self.COHORT_KEYWORDS):
            return "COHORT_INSIGHTS_AGENT"
        
        # Default to drug spend agent (most common use case)
        return "DRUG_SPEND_AGENT"
    
    def _apply_privacy_guardrails(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Apply PHI redaction to the response."""
        # Redact patterns in answer text
        answer = response.get("answer", "")
        
        # Redact dates of birth (MM/DD/YYYY, YYYY-MM-DD, etc.)
        answer = re.sub(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', '[DATE REDACTED]', answer)
        answer = re.sub(r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b', '[DATE REDACTED]', answer)
        
        # Redact SSN patterns (XXX-XX-XXXX)
        answer = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN REDACTED]', answer)
        
        # Redact phone numbers
        answer = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE REDACTED]', answer)
        
        # Redact member ID hashes (long hex strings)
        answer = re.sub(r'\b[a-f0-9]{64}\b', '[MEMBER_ID REDACTED]', answer)
        
        response["answer"] = answer
        
        # Also redact from table data
        if response.get("table"):
            redacted_table = []
            for row in response["table"]:
                if isinstance(row, dict):
                    redacted_row = {}
                    for key, value in row.items():
                        # Redact member_id_hash
                        if key in ("member_id_hash", "member_id"):
                            redacted_row[key] = "[REDACTED]"
                        # Redact names in table
                        elif "name" in key.lower():
                            redacted_row[key] = "[NAME REDACTED]"
                        # Keep other fields
                        else:
                            redacted_row[key] = value
                    redacted_table.append(redacted_row)
                else:
                    redacted_table.append(row)
            response["table"] = redacted_table
        
        return response
    
    async def process_query(self, question: str, user_id: str) -> Dict[str, Any]:
        """Process a user question end-to-end."""
        start_time = datetime.utcnow()
        
        try:
            # Step 1: Route question to appropriate agent
            agent_name = self._route_query(question)
            logger.info(f"Routed query to agent: {agent_name}")
            
            # Step 2: Execute appropriate tool based on routing
            result = await self._execute_tool(question, agent_name)
            
            # Step 3: Format response
            formatted_response = self._format_response(result, question, agent_name)
            
            # Step 4: Apply privacy guardrails
            safe_response = self._apply_privacy_guardrails(formatted_response)
            
            # Step 5: Log query for audit
            self._log_query(question, user_id, agent_name, safe_response, start_time)
            
            return safe_response
            
        except Exception as e:
            logger.error(f"Error processing DigbiGPT query: {e}", exc_info=True)
            return {
                "answer": f"I encountered an error processing your question: {str(e)}",
                "table": [],
                "sql_executed": None,
                "confidence": 0.0,
                "agent_used": None,
                "error": str(e)
            }
    
    async def _execute_tool(self, question: str, agent_name: str) -> Dict[str, Any]:
        """Execute the appropriate tool based on agent routing."""
        question_lower = question.lower()
        
        # Drug spend queries
        if agent_name == "DRUG_SPEND_AGENT":
            # Extract drug name and year from question
            drug_name = self._extract_drug_name(question)
            year = self._extract_year(question, default=2023)
            
            return await claims_client.call_tool("get_top_drug_spend", {
                "drug_name": drug_name,
                "year": year,
                "limit": 10
            })
        
        # Clinical history queries
        elif agent_name == "CLINICAL_HISTORY_AGENT":
            if "gi" in question_lower or "gastro" in question_lower:
                # GI new starts query
                start_date = self._extract_start_date(question, default="2023-01-01")
                end_date = self._extract_end_date(question, default="2023-12-31")
                
                return await claims_client.call_tool("get_gi_new_starts", {
                    "start_date": start_date,
                    "end_date": end_date,
                    "limit": 50
                })
            else:
                # Member disease history (would need member ID)
                return {"error": "Member ID required for disease history query"}
        
        # Cohort insights queries
        elif agent_name == "COHORT_INSIGHTS_AGENT":
            disease_category = self._extract_disease_category(question, default="hypertention")
            year = self._extract_year(question, default=2023)
            
            return await claims_client.call_tool("get_disease_cohort_summary", {
                "disease_category": disease_category,
                "year": year
            })
        
        else:
            return {"error": f"Unknown agent: {agent_name}"}
    
    def _extract_drug_name(self, question: str) -> str:
        """Extract drug name from question."""
        # Common drug patterns
        drug_patterns = [
            "omeprazole", "sertraline", "metformin", "lisinopril", "atorvastatin",
            "rosuvastatin", "simvastatin", "pantoprazole", "esomeprazole"
        ]
        
        question_lower = question.lower()
        for drug in drug_patterns:
            if drug in question_lower:
                return drug.upper()
        
        # Default to common drug
        return "OMEPRAZOLE"
    
    def _extract_year(self, question: str, default: int = 2023) -> int:
        """Extract year from question."""
        # Look for 4-digit year
        import re
        year_match = re.search(r'\b(20\d{2})\b', question)
        if year_match:
            return int(year_match.group(1))
        return default
    
    def _extract_start_date(self, question: str, default: str = "2023-01-01") -> str:
        """Extract start date from question."""
        # Simple date extraction - could be enhanced
        return default
    
    def _extract_end_date(self, question: str, default: str = "2023-12-31") -> str:
        """Extract end date from question."""
        # Simple date extraction - could be enhanced
        return default
    
    def _extract_disease_category(self, question: str, default: str = "hypertention") -> str:
        """Extract disease category from question."""
        question_lower = question.lower()
        if "hypertension" in question_lower or "hypertention" in question_lower:
            return "hypertention"
        elif "diabetes" in question_lower:
            return "diabetes"
        return default
    
    def _format_response(self, result: Any, question: str, agent_name: str) -> Dict[str, Any]:
        """Format the result into a standardized response."""
        # Extract table data from tool results if available
        table_data = []
        sql_executed = None
        
        # Handle different result formats
        if isinstance(result, dict):
            if "rows" in result:
                table_data = result.get("rows", [])
            if "sql_executed" in result:
                sql_executed = result.get("sql_executed")
            answer = result.get("response", result.get("answer", str(result)))
        else:
            answer = str(result)
        
        # Ensure answer is a string
        if not isinstance(answer, str):
            answer = str(answer)
        
        # Calculate confidence based on whether we got data
        confidence = 0.9 if table_data else 0.5
        
        return {
            "answer": answer,
            "table": table_data,
            "sql_executed": sql_executed,
            "confidence": confidence,
            "agent_used": agent_name
        }
    
    def _log_query(self, question: str, user_id: str, agent: str, response: Dict[str, Any], start_time: datetime) -> None:
        """Log the query for audit trail."""
        end_time = datetime.utcnow()
        duration_ms = (end_time - start_time).total_seconds() * 1000
        
        log_entry = {
            "timestamp": start_time.isoformat(),
            "user_id": user_id,
            "question": question,
            "agent": agent,
            "sql_executed": response.get("sql_executed"),
            "row_count": len(response.get("table", [])),
            "confidence": response.get("confidence"),
            "duration_ms": duration_ms,
            "error": response.get("error")
        }
        
        logger.info(f"DigbiGPT Query: {json.dumps(log_entry)}")

# Initialize orchestrator
orchestrator = DigbiGPTOrchestrator()

# API Endpoints
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "DigbiGPT API Service",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Test claims server connection
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8811/health", timeout=5.0)
            claims_server_status = "connected" if response.status_code == 200 else "disconnected"
    except Exception:
        claims_server_status = "disconnected"
    
    return {
        "status": "healthy",
        "service": "DigbiGPT API",
        "claims_server": claims_server_status,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/digbigpt/ask", response_model=DigbiGPTResponse)
async def ask_digbigpt(request: DigbiGPTRequest):
    """
    Process a natural language query about claims data.
    
    This endpoint accepts natural language questions about healthcare claims data
    and returns structured results with both tabular data and plain-English summaries.
    
    Example:
        POST /digbigpt/ask
        {
            "question": "Which customers spent most on rosuvastatin in 2024?",
            "user_id": "dr_smith_123"
        }
    
    The system will:
    1. Route the question to the appropriate specialist agent
    2. Execute pre-vetted SQL queries via claims server
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
            user_id=request.user_id
        )
        
        # Add missing fields to match response schema
        response["query_time_ms"] = int(response.get("confidence", 0) * 1000)  # Mock for now
        response["timestamp"] = datetime.utcnow().isoformat()
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

@app.get("/digbigpt/agents")
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

@app.get("/digbigpt/tools")
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

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting DigbiGPT API Service on http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
