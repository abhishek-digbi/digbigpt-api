from agent_core.config.logging_config import logger
from agent_core.services.ai_core_service import AiCoreService
from orchestrator.orchestrators.base_ask_digbi_agent import AskDigbiBaseAgent
from agent_core.services.model_context import ModelContext


class PersonalizationAgent(AskDigbiBaseAgent):
    def __init__(self, ai_core: AiCoreService):
        self.ai = ai_core

    async def ask(self, ctx: ModelContext):
        logger.info(f"Asking USER_DATA_AGENT: user={ctx.user_token} qid={ctx.query_id}")
        result = await self.ai.run_agent('USER_DATA_AGENT', ctx)
        return {"status": "accepted", "message": result}
