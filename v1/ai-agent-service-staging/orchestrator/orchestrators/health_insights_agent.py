from dataclasses import dataclass
from typing import Literal
from pydantic import BaseModel
from agent_core.config.logging_config import logger
import utils.env_loader
from agent_core.services.ai_core_service import AiCoreService
from orchestrator.orchestrators.base_ask_digbi_agent import AskDigbiBaseAgent
from agent_core.services.model_context import ModelContext
import utils.slack_util


class HealthInsightsAgentResponse(BaseModel):
    status: Literal["success", "failure"]
    message: str


class HealthInsightsAgent(AskDigbiBaseAgent):
    def __init__(self, aicore: AiCoreService):
        self.ai = aicore

    async def ask(self, ctx: ModelContext) -> dict[str, str]:
        if ctx.user_token is None:
            return {}

        logger.info(
            f"Asking Health Insights Agent: user={ctx.user_token} qid={ctx.query_id}"
        )
        result = await self.ai.run_agent(
            "ASK_DIGBI_HEALTH_INSIGHTS_AGENT",
            ctx,
            output_type=HealthInsightsAgentResponse,
        )

        if not isinstance(result, HealthInsightsAgentResponse):
            logger.warning(f"Unexpected response type: {type(result)}")
            raise ValueError("Error parsing response from report metadata assistant")

        status = result.status
        message = result.message

        if status == "success":
            logger.info(f"Response from health_insights_agent: {result}")
            return {"status": status, "message": message}
        else:
            logger.info(
                f"Asking GPT Knowledge Base: user={ctx.user_token} qid={ctx.query_id}"
            )
            result: HealthInsightsAgentResponse = await self.ai.run_agent(
                "ASK_DIGBI_HEALTH_INSIGHTS_GPT_AGENT",
                ctx,
                output_type=HealthInsightsAgentResponse,
            )
            logger.info(
                f"Health insights GPT agent response: {result.model_dump_json()}"
            )

            utils.slack_util.send_slack_askdigbi_log(
                f"*QUERY_ID:* {ctx.query_id} *[{ctx.user_type}] ```Using GPT Knowledge with Prompt:"
                f" {ctx.query}\nGPT Response: {result.model_dump_json()} ```"
            )

            return {"status": result.status, "message": result.message}
