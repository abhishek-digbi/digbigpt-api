from typing import Dict
from agent_core.services.base_agent import BaseAgentAdapter
from agent_core.services.adapters.openai_service import OpenAIService


class AdapterRegistry:
    def __init__(self, openAIService: OpenAIService):
        # bootstrap your adapters however you load credentials
        self._adapters: Dict[str, BaseAgentAdapter] = {
            "openai": openAIService,
            # "anthropic": AnthropicService(config.ANTHROPIC_API_KEY),
        }

    def get(self, adapter_name: str) -> BaseAgentAdapter:
        try:
            return self._adapters[adapter_name]
        except KeyError:
            raise ValueError(f"No provider registered under '{adapter_name}'")
