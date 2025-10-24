import json
from dataclasses import dataclass

from agent_core.config.logging_config import logger
from agent_core.services.ai_core_service import AiCoreService
from orchestrator.orchestrators.base_ask_digbi_agent import AskDigbiBaseAgent
from agent_core.services.model_context import ModelContext
@dataclass
class Sensitivities:
    sensitivities: list[str]

    def __init__(self):
        self.sensitivities = []

class SensitivityAgent(AskDigbiBaseAgent):
    def __init__(self, ai_core: AiCoreService):
        self.ai = ai_core

    async def identify_sensitivities(self, ctx: ModelContext, request_context):
        """
        Identify sensitivities in the item list
        """

        request_context["agent_interactions"]["sensitivities_identifier"] = {"agent": self.__class__.__name__, "ctx.data": ctx.data}
        result = await self.ai.run_agent("MEAL_SENSITIVITIES_IDENTIFIER_AGENT", ctx, output_type=Sensitivities)
        request_context["agent_interactions"]["sensitivities_identifier"]["response"] = result
        logger.info(f"response from sensitivities agent: {result}")
        if isinstance(result, Sensitivities):
            return result.sensitivities
        else:
            logger.warning(f"Unexpected response type: {type(result)}")
            return []

    async def ask(self, ctx: ModelContext) -> dict[str, str]:
        result = await self.ai.run_agent("MEAL_SENSITIVITIES_IDENTIFIER_AGENT", ctx, output_type=Sensitivities)
        logger.info(f"response from sensitivities agent: {result}")
        if isinstance(result, Sensitivities):
            return {"status": "success", "sensitivities": result.sensitivities}
        else:
            logger.warning(f"Unexpected response type: {type(result)}")
            return {"status": "error", "sensitivities": None}


