from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class AgentLogEntry:
    """Data class representing an agent log entry."""
    context_id: str
    prompt: str
    response: Dict[str, Any]
    agent_id: str
    user_token: str
    model_context: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    duration: Optional[float] = None

class IAgentLogger:
    """
    Interface for logging agent interactions.
    
    Implementations of this interface should handle the persistence of agent logs
    to various storage backends (e.g., database, file system, etc.).
    """
    
    def log_interaction(
        self,
        ctx: Any,
        prompt: str,
        response: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        duration: Optional[float] = None,
    ) -> None:
        """
        Log an agent interaction.
        
        Args:
            ctx: The context object containing context_id, user_token, and other context data
            prompt: The input prompt sent to the agent
            response: The agent's response
            metadata: Additional metadata to include with the log
            duration: Time taken to execute the agent in seconds
            
        Raises:
            NotImplementedError: If the method is not implemented by a subclass
        """
        raise NotImplementedError("log_interaction method must be implemented by subclasses")
    
    def create_log_entry(
        self,
        ctx: Any,
        prompt: str,
        response: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        duration: Optional[float] = None,
    ) -> AgentLogEntry:
        """
        Create a log entry object without persisting it.
        
        Args:
            ctx: The context object (ModelContext or similar)
            prompt: The input prompt
            response: The agent's response
            metadata: Additional metadata
            duration: Time taken to execute the agent in seconds
            
        Returns:
            AgentLogEntry: The created log entry
        """
        # Extract context data safely
        context_data = {}
        if hasattr(ctx, '__dict__'):
            context_data = ctx.__dict__.copy()
        elif hasattr(ctx, 'model_dump'):
            context_data = ctx.model_dump()
            
        # Get agent name from metadata or context
        agent_id = 'unknown'
        if metadata and 'agent_id' in metadata:
            agent_id = metadata['agent_id']
            
        return AgentLogEntry(
            context_id=getattr(ctx, 'context_id', ''),
            prompt=prompt,
            response=response,
            agent_id=agent_id,
            user_token=getattr(ctx, 'user_token', ''),
            model_context=context_data,
            metadata=metadata or {},
            duration=duration,
        )
