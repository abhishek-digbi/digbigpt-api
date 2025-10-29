from abc import ABC, abstractmethod

from agent_core.services.model_context import ModelContext


class AskDigbiBaseAgent(ABC):
    @abstractmethod
    def ask(self, context: ModelContext) -> dict[str, object]:
        """Submit a query to the agent and return a response."""
        pass

