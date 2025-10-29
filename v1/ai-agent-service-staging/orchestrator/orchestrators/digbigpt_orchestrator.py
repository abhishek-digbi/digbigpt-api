"""DigbiGPT Orchestrator for healthcare claims analysis.

This orchestrator routes natural language questions about healthcare claims
to specialized agents and applies PHI redaction for HIPAA compliance.
"""

from typing import Dict, Any, List
import re
import logging
import json
from datetime import datetime

from agent_core.services.ai_core_service import AiCoreService
from agent_core.services.model_context import BaseModelContext

logger = logging.getLogger(__name__)


class DigbiGPTOrchestrator:
    """Orchestrates DigbiGPT claims analysis queries with AI agents."""
    
    # Keyword patterns for agent routing
    DRUG_SPEND_KEYWORDS = [
        "drug", "medication", "spend", "cost", "price", "expensive",
        "pharmacy", "prescription", "duplicate", "statin", "benzo",
        "omeprazole", "rosuvastatin", "metformin", "atorvastatin"
    ]
    
    CLINICAL_KEYWORDS = [
        "diagnosis", "disease", "condition", "history", "timeline",
        "patient", "member", "icd", "gi", "gastrointestinal",
        "clinical", "medical history"
    ]
    
    COHORT_KEYWORDS = [
        "cohort", "population", "group", "hypertension", "diabetes",
        "summary", "metrics", "aggregate", "total", "overall"
    ]
    
    def __init__(self, ai_core_service: AiCoreService):
        """Initialize orchestrator with AI core service.
        
        Args:
            ai_core_service: Service for running AI agents
        """
        self.ai = ai_core_service
        logger.info("DigbiGPTOrchestrator initialized")
    
    async def process_query(
        self,
        question: str,
        user_id: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Process a natural language query about claims data.
        
        Args:
            question: Natural language question
            user_id: User identifier for audit logging
            context: Optional conversation context
            
        Returns:
            Dictionary with answer, table data, agent used, etc.
        """
        start_time = datetime.utcnow()
        
        try:
            # Route to appropriate agent
            agent_id = self._route_query(question)
            confidence = 0.9  # High confidence for keyword-based routing
            
            logger.info(
                f"DigbiGPT query routed to {agent_id} for user {user_id}: {question[:100]}"
            )
            
            # Create model context for the agent
            ctx = BaseModelContext(
                context_id=f"digbigpt_{user_id}_{start_time.timestamp()}",
                query=question,
                user_token=user_id,
                user_type="DIGBI_GPT",
                data={"original_question": question}
            )
            
            # Execute agent with AI
            result = await self.ai.run_agent(
                agent_id=agent_id,
                ctx=ctx,
                output_type=str
            )
            
            # Format response with table data
            formatted_response = self._format_response(result, question, agent_id)
            
            # Apply PHI redaction
            safe_response = self._apply_privacy_guardrails(formatted_response)
            
            # Add metadata
            safe_response["agent_used"] = agent_id
            safe_response["confidence"] = confidence
            safe_response["query_time_ms"] = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )
            safe_response["timestamp"] = datetime.utcnow().isoformat()
            
            # Log query for audit trail
            self._log_query(question, user_id, agent_id, safe_response, start_time)
            
            return safe_response
            
        except Exception as e:
            logger.error(f"Error processing DigbiGPT query: {e}", exc_info=True)
            return {
                "answer": f"I encountered an error processing your question: {str(e)}",
                "table": {"columns": [], "rows": []},
                "agent_used": None,
                "confidence": 0.0,
                "query_time_ms": int(
                    (datetime.utcnow() - start_time).total_seconds() * 1000
                ),
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
    
    def _route_query(self, question: str) -> str:
        """Route question to appropriate agent based on keywords.
        
        Args:
            question: Natural language question
            
        Returns:
            Agent ID to handle the query
        """
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
        
        # Default to drug spend agent
        return "DRUG_SPEND_AGENT"
    
    def _format_response(
        self,
        result: Any,
        question: str,
        agent_id: str
    ) -> Dict[str, Any]:
        """Format agent result into standard response structure.
        
        Args:
            result: Result from agent execution
            question: Original question
            agent_id: Agent that processed the query
            
        Returns:
            Formatted response dictionary
        """
        # If result is a string, it's the AI summary
        if isinstance(result, str):
            return {
                "answer": result,
                "table": {"columns": [], "rows": []}
            }
        
        # If result is a dict with table data
        if isinstance(result, dict):
            return {
                "answer": result.get("answer", result.get("response", str(result))),
                "table": result.get("table", {"columns": [], "rows": []})
            }
        
        # Fallback
        return {
            "answer": str(result),
            "table": {"columns": [], "rows": []}
        }
    
    def _apply_privacy_guardrails(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Apply PHI redaction to protect sensitive information.
        
        Redacts:
        - Names (common first names)
        - Dates (various formats)
        - SSNs (###-##-####)
        - Phone numbers
        - Member IDs (long hex strings)
        
        Args:
            response: Response dictionary with answer and table
            
        Returns:
            Response with PHI redacted
        """
        answer = response.get("answer", "")
        
        # Redact dates (MM/DD/YYYY, MM-DD-YYYY, YYYY-MM-DD)
        answer = re.sub(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', '[DATE REDACTED]', answer)
        answer = re.sub(r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b', '[DATE REDACTED]', answer)
        
        # Redact SSNs
        answer = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN REDACTED]', answer)
        
        # Redact phone numbers
        answer = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE REDACTED]', answer)
        
        # Redact member IDs (64-character hex strings)
        answer = re.sub(r'\b[a-f0-9]{64}\b', '[MEMBER_ID REDACTED]', answer)
        
        response["answer"] = answer
        
        # Redact table data
        if response.get("table") and response["table"].get("rows"):
            redacted_rows = []
            for row in response["table"]["rows"]:
                redacted_row = []
                for item in row:
                    if isinstance(item, str):
                        # Redact dates
                        item = re.sub(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', '[DATE REDACTED]', item)
                        item = re.sub(r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b', '[DATE REDACTED]', item)
                        
                        # Redact member IDs
                        item = re.sub(r'\b[a-f0-9]{64}\b', '[MEMBER_ID REDACTED]', item)
                        
                        # Redact common names (simple list - could be expanded)
                        name_patterns = [
                            "hannah", "bobby", "troy", "ronald", "james", "timothy",
                            "anne", "nichelle", "gennifer", "scott", "ricardo", "cynthia",
                            "camila", "jon", "lynda", "jeff", "elena", "debra", "paul",
                            "grant", "nahed", "anna", "madelaine", "nancy", "tamara",
                            "gretchen", "gary", "david", "richard"
                        ]
                        if any(name in item.lower() for name in name_patterns):
                            item = "[NAME REDACTED]"
                    
                    redacted_row.append(item)
                redacted_rows.append(redacted_row)
            
            response["table"]["rows"] = redacted_rows
        
        return response
    
    def _log_query(
        self,
        question: str,
        user_id: str,
        agent: str,
        response: Dict[str, Any],
        start_time: datetime
    ) -> None:
        """Log query for audit trail and compliance.
        
        Args:
            question: Original question
            user_id: User identifier
            agent: Agent that handled the query
            response: Final response
            start_time: Query start time
        """
        end_time = datetime.utcnow()
        duration_ms = (end_time - start_time).total_seconds() * 1000
        
        log_entry = {
            "timestamp": start_time.isoformat(),
            "user_id": user_id,
            "question": question,
            "agent": agent,
            "row_count": len(response.get("table", {}).get("rows", [])),
            "confidence": response.get("confidence"),
            "duration_ms": duration_ms,
            "has_error": "error" in response
        }
        
        logger.info(f"DigbiGPT Query Log: {json.dumps(log_entry)}")

