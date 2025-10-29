import json
from typing import Protocol, Optional, Dict, Any

MCP_VERSION = "1.0"  # MCP implementation: protocol version identifier


class ModelContext(Protocol):
    context_id: str
    user_token: Optional[str]
    query_id: Optional[str]
    query: Optional[str]
    image_url: Optional[str] = None,
    feature_context: Optional[str]
    user_type: Optional[str]
    language: Optional[str]
    data: dict
    conversation_history: Optional[dict] = None
    screen_info: Optional[str]
    entity_id: Optional[str]
    agent_statuses: list


class BaseModelContext(ModelContext):
    def __init__(
            self,
            context_id: str,
            query: Optional[str] = None,
            feature_context: Optional[str] = None,
            user_type: Optional[str] = None,
            language: Optional[str] = None,
            conversation_history: Optional[dict] = None,
            data=None,
            user_token: Optional[str] = None,
            query_id: Optional[str] = None,
            image_url: Optional[str] = None,
            *,
            metadata: Optional[Dict[str, Any]] = None,
            state: Optional[Dict[str, Any]] = None,
            mcp_version: str = MCP_VERSION,
    ):
        if data is None:
            data = {}
        if context_id is None:
            raise ValueError("context_id cannot be None")
        self.context_id = context_id
        self.user_token = user_token
        self.query_id = query_id
        self.query = query
        self.image_url = image_url
        self.feature_context = feature_context
        self.user_type = user_type
        self.language = language
        self.data = data
        self.conversation_history = conversation_history
        self.screen_info = None
        self.entity_id = None
        # MCP implementation fields
        self.metadata = metadata or {}
        self.state = state or {}
        self.mcp_version = mcp_version
        self.agent_statuses = []

    def to_mcp_payload(self, prompt: str) -> str:
        """Wrap a prompt in an MCP compliant structure."""
        envelope = {
            "mcp_version": self.mcp_version,
            "metadata": self.metadata,
            "state": self.state,
            "prompt": prompt,
        }
        # MCP implementation: return JSON envelope for LLM consumption
        return json.dumps(envelope)
