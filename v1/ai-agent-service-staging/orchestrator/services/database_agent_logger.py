from typing import Any, Dict, Optional

from agent_core.interfaces.agent_logger import IAgentLogger, AgentLogEntry
from orchestrator.repositories.agent_logs_repository import AgentLogsRepository
from utils.db import logger


class DatabaseAgentLogger(IAgentLogger):
    """
    Implementation of IAgentLogger that stores logs in a database using AgentLogsRepository.
    
    This class provides a concrete implementation of the IAgentLogger interface
    that persists agent interactions to a PostgreSQL database.
    """
    
    def __init__(self, repository: AgentLogsRepository):
        """
        Initialize the DatabaseAgentLogger with a repository instance.
        
        Args:
            repository: An instance of AgentLogsRepository for database operations
        """
        self.repository = repository
    
    def log_interaction(
        self,
        ctx: Any,
        prompt: str,
        response: Any,
        metadata: Optional[Dict[str, Any]] = None,
        duration: Optional[float] = None,
    ) -> None:
        """
        Log an agent interaction to the database.
        
        Args:
            ctx: The context object containing context_id, user_token, and other context data
            prompt: The input prompt sent to the agent
            response: The agent's response (can be a dictionary, AgentRequest, or any serializable object)
            metadata: Additional metadata to include with the log
            duration: Time taken to execute the agent in seconds
            
        Example:
            logger = DatabaseAgentLogger(agent_logs_repository)
            logger.log_interaction(
                ctx=context_object,
                prompt="What's the weather like?",
                response={"answer": "It's sunny today!"},
                metadata={"source": "weather_agent"}
            )
        """
        try:
            # Convert response to a serializable format if needed
            serializable_response = response
            if hasattr(response, 'to_dict') and callable(getattr(response, 'to_dict')):
                serializable_response = response.to_dict()
            elif not isinstance(response, (dict, list, str, int, float, bool, type(None))):
                # Try to convert to dict if it's not a basic type
                try:
                    serializable_response = dict(response)
                except (TypeError, ValueError):
                    # Fall back to string representation if conversion fails
                    serializable_response = str(response)
            
            log_entry = self.create_log_entry(
                ctx,
                prompt,
                serializable_response,
                metadata,
                duration,
            )
            
            self.repository.log_ai_agent(
                agent_id=log_entry.agent_id,
                prompt=log_entry.prompt,
                response_json=log_entry.response,
                context_id=log_entry.context_id,
                user_token=log_entry.user_token,
                model_context=log_entry.model_context,
                metadata=log_entry.metadata,
                duration=log_entry.duration,
            )
        except Exception as e:
            logger.error(f"Error logging AI agent interaction: {str(e)}")
            raise
    
    def get_logs_by_context(self, context_id: str) -> list[Dict[str, Any]]:
        """
        Retrieve all logs for a specific context_id.
        
        Args:
            context_id: The context_id to filter logs by
            
        Returns:
            List of log entries with parsed JSON fields
        """
        return self.repository.get_logs_by_context(context_id)
    
    def get_paginated_logs(
        self,
        context_id: str,
        page: int = 1,
        per_page: int = 10
    ) -> tuple[list[Dict[str, Any]], Dict[str, Any]]:
        """
        Retrieve paginated logs for a specific context_id.
        
        Args:
            context_id: The context_id to filter logs by
            page: Page number (1-based)
            per_page: Number of items per page
            
        Returns:
            Tuple of (logs, pagination_metadata)
        """
        return self.repository.get_paginated_logs_by_context(
            context_id=context_id,
            page=page,
            per_page=per_page
        )
