from abc import ABC, abstractmethod
from typing import Optional, Any, Dict

from agent_core.services.model_context import ModelContext


class BaseAgentAdapter(ABC):
    """
    Base abstract class for agent adapters that handle interactions with AI models.

    This class defines the interface for implementing different AI model adapters,
    ensuring consistent behavior across various model implementations.
    """

    @abstractmethod
    def run(
        self,
        prompt: str,
        ctx: ModelContext,
        image_url: Optional[str] = None,
        max_tokens: int = 1000,
        context_id: Optional[str] = None,
        user_token: Optional[str] = None,
        user_type: Optional[str] = None,
        user_query: Optional[str] = None,
        feature_context: Optional[str] = None,
        model: Optional[str] = None,
        text_format: Optional[str] = None,
        assistant_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        instructions: Optional[str] = None,
        output_type: type[Any] = str,
        vector_store_ids: Optional[list[str]] = None,
        strict_json_schema: bool = True,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        tool_choice: Optional[str] = None,
        tools: Optional[list[Any]] = None,
        file_filters: Optional[Dict[str, Any]] = None,
        hooks: Optional[list[Any]] = None,
        output_guardrails: Optional[list[Any]] = None,
        input_guardrails: Optional[list[Any]] = None,
        role_based_messages_as_input: Optional[bool] = False,
        additional_messages: Optional[list[dict[str, str]]] = None,
        input_messages: Optional[list[dict[str, Any]]] = None,
    ) -> Any:
        """
        Generates text or performs actions based on the given prompt.

        This method is responsible for executing the core functionality of the agent,
        which may include text generation, image processing, or other AI tasks.

        Args:
            prompt: The input prompt for text generation or task execution.
            image_url: Optional URL of an image to be processed (if applicable).
            max_tokens: Maximum number of tokens to generate (default: 1000).
            model: Specific AI model to use (optional).
            text_format: Desired format of the response (e.g., 'json', 'text').
            assistant_id: ID of the assistant to use (optional).
            agent_id: ID of the agent executing the task (optional).
            instructions: Additional instructions to guide the AI (optional).
            output_type: Expected type of the output (default: str).
            vector_store_ids: List of vector store IDs to use for context (optional).

        Returns:
            Any: The generated output, which can be of any type specified by output_type.

        Raises:
            NotImplementedError: If the method is not implemented by a concrete adapter.
            :param strict_json_schema:
        """
        pass
