from dataclasses import dataclass

from agent_core.config.logging_config import logger
from agent_core.services.ai_core_service import AiCoreService
from orchestrator.orchestrators.base_ask_digbi_agent import AskDigbiBaseAgent
from agent_core.services.model_context import ModelContext


@dataclass
class RenewalAgentResponse:
    """Typed response from the renewal agent."""

    status: str
    message: str

    def __init__(self) -> None:
        self.status = ""
        self.message = ""


class RenewalAgent(AskDigbiBaseAgent):
    def __init__(self, ai_core: AiCoreService):
        self.ai = ai_core

    async def ask(self, ctx: ModelContext) -> dict[str, str]:
        """Generate an in-app renewal message."""
        logger.info(f"Asking In App Renewal Agent: user={ctx.user_token} qid={ctx.query_id}")

        result = await self.ai.run_agent(
            "IN_APP_RENEWAL_AGENT",
            ctx,
            output_type=RenewalAgentResponse,
        )

        if not isinstance(result, RenewalAgentResponse):
            logger.warning("Unexpected response type from renewal agent: %s", type(result))
            return {"status": "error", "message": str(result)}

        status = result.status or "completed"
        return {"status": status, "message": result.message}