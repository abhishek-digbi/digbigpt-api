"""
DigbiGPT Orchestrator

This orchestrator handles claims database queries by routing questions to specialized agents
and formatting responses with both table data and natural language summaries.
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from agent_core.config.logging_config import logger
from agent_core.services.ai_core_service import AiCoreService
from agent_core.services.model_context import ModelContext


class DigbiGPTOrchestrator:
    """
    Main orchestrator for DigbiGPT queries.
    
    Responsibilities:
    1. Route user questions to appropriate specialist agents
    2. Execute SQL queries via tools
    3. Format responses with tables + summaries
    4. Apply PHI redaction guardrails
    5. Log all queries for audit trail
    """
    
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
    
    def __init__(self, ai_service: AiCoreService):
        """
        Initialize the orchestrator.
        
        Args:
            ai_service: AI core service for agent execution
        """
        self.ai = ai_service
        self.logger = logging.getLogger(__name__)
    
    async def process_query(
        self,
        question: str,
        user_id: str,
        ctx: Optional[ModelContext] = None
    ) -> Dict[str, Any]:
        """
        Process a user question end-to-end.
        
        Args:
            question: Natural language question
            user_id: User identifier for audit logging
            ctx: Optional model context (created if not provided)
            
        Returns:
            Dict containing:
            - answer: Plain English summary
            - table: List of row dictionaries
            - sql_executed: The SQL query that was run
            - confidence: Confidence score (0.0-1.0)
            - agent_used: Which agent handled the query
        """
        start_time = datetime.utcnow()
        
        try:
            # Create context if not provided
            if ctx is None:
                ctx = ModelContext(
                    query=question,
                    user_token=user_id,
                    query_id=f"digbigpt-{start_time.timestamp()}"
                )
            
            # Step 1: Route question to appropriate agent
            agent_name = await self._route_query(question)
            self.logger.info(f"Routed query to agent: {agent_name}")
            
            # Step 2: Execute agent with tools
            result = await self._execute_agent(agent_name, question, ctx)
            
            # Step 3: Format response
            formatted_response = await self._format_response(result, question, agent_name)
            
            # Step 4: Apply privacy guardrails
            safe_response = self._apply_privacy_guardrails(formatted_response)
            
            # Step 5: Log query for audit
            await self._log_query(
                question=question,
                user_id=user_id,
                agent=agent_name,
                response=safe_response,
                start_time=start_time
            )
            
            return safe_response
            
        except Exception as e:
            self.logger.error(f"Error processing DigbiGPT query: {e}", exc_info=True)
            return {
                "answer": f"I encountered an error processing your question: {str(e)}",
                "table": [],
                "sql_executed": None,
                "confidence": 0.0,
                "agent_used": None,
                "error": str(e)
            }
    
    async def _route_query(self, question: str) -> str:
        """
        Route question to the appropriate specialist agent based on keywords.
        
        Args:
            question: User question
            
        Returns:
            Agent name to use
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
        
        # Default to drug spend agent (most common use case)
        return "DRUG_SPEND_AGENT"
    
    async def _execute_agent(
        self,
        agent_name: str,
        question: str,
        ctx: ModelContext
    ) -> Dict[str, Any]:
        """
        Execute the agent and return its tool results.
        
        Args:
            agent_name: Name of agent to execute
            question: User question
            ctx: Model context
            
        Returns:
            Agent result with tool outputs
        """
        ctx.data = {"question": question}
        
        try:
            # Run agent - it will automatically call appropriate tools
            result = await self.ai.run_agent(agent_name, ctx)
            return result
        except Exception as e:
            self.logger.error(f"Error executing agent {agent_name}: {e}")
            raise
    
    async def _format_response(
        self,
        agent_result: Any,
        question: str,
        agent_name: str
    ) -> Dict[str, Any]:
        """
        Format the agent result into a standardized response.
        
        Args:
            agent_result: Raw result from agent
            question: Original question
            agent_name: Agent that was used
            
        Returns:
            Formatted response dictionary
        """
        # Extract table data from tool results if available
        table_data = []
        sql_executed = None
        
        # Handle different result formats
        if isinstance(agent_result, dict):
            if "rows" in agent_result:
                table_data = agent_result.get("rows", [])
            if "sql_executed" in agent_result:
                sql_executed = agent_result.get("sql_executed")
            answer = agent_result.get("response", agent_result.get("answer", str(agent_result)))
        else:
            answer = str(agent_result)
        
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
    
    def _apply_privacy_guardrails(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply PHI redaction to the response.
        
        Args:
            response: Raw response dictionary
            
        Returns:
            Response with PHI redacted
        """
        # Redact patterns in answer text
        answer = response.get("answer", "")
        
        # Redact dates of birth (MM/DD/YYYY, YYYY-MM-DD, etc.)
        answer = re.sub(
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
            '[DATE REDACTED]',
            answer
        )
        answer = re.sub(
            r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b',
            '[DATE REDACTED]',
            answer
        )
        
        # Redact SSN patterns (XXX-XX-XXXX)
        answer = re.sub(
            r'\b\d{3}-\d{2}-\d{4}\b',
            '[SSN REDACTED]',
            answer
        )
        
        # Redact phone numbers
        answer = re.sub(
            r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            '[PHONE REDACTED]',
            answer
        )
        
        # Redact member ID hashes (long hex strings)
        answer = re.sub(
            r'\b[a-f0-9]{64}\b',
            '[MEMBER_ID REDACTED]',
            answer
        )
        
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
    
    async def _log_query(
        self,
        question: str,
        user_id: str,
        agent: str,
        response: Dict[str, Any],
        start_time: datetime
    ) -> None:
        """
        Log the query for audit trail.
        
        Args:
            question: User question
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
            "sql_executed": response.get("sql_executed"),
            "row_count": len(response.get("table", [])),
            "confidence": response.get("confidence"),
            "duration_ms": duration_ms,
            "error": response.get("error")
        }
        
        self.logger.info(f"DigbiGPT Query: {json.dumps(log_entry)}")

