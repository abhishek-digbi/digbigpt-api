from typing import Optional

import utils.slack_util
from agent_core.config.logging_config import logger
from agent_core.services.ai_core_service import AiCoreService
from agent_core.services.model_context import ModelContext
from agent_core.models.support_intents import InviteDependentIntent
from orchestrator.orchestrators.agent_models import (
    AgentRequestV2,
    InteractiveComponent,
    Meta,
    SupportAgentResponse,
)
from orchestrator.orchestrators.base_ask_digbi_agent import AskDigbiBaseAgent
from orchestrator.orchestrators.unified_support_agent import UnifiedSupportAgent
from orchestrator.orchestrators.kb_retry import maybe_retry_with_kb_guidance
from utils.env_loader import should_enable_unified_support_agent


class SupportAgent(AskDigbiBaseAgent):
    def __init__(
        self,
        aicore: AiCoreService,
        unified_support_agent: Optional[UnifiedSupportAgent] = None,
    ):
        """Initialize SupportAgent with the core service."""
        self.ai = aicore
        self._unified_support_agent = unified_support_agent or UnifiedSupportAgent(aicore)

    async def ask(self, ctx: ModelContext):

        try:
            if getattr(ctx, "data", None) is None:
                ctx.data = {}

            user_type = (getattr(ctx, "user_type", "") or "").strip().lower()
            unified_support_enabled = should_enable_unified_support_agent()
            if user_type == "alpha" and unified_support_enabled:
                logger.info("Routing alpha user to unified support agent via env switch")
                return await self._unified_support_agent.ask(ctx)

            agent_request: AgentRequestV2 = await self.ai.run_agent(
                "SUPPORT_AGENT",
                ctx,
                output_type=AgentRequestV2,
                strict_json_schema=False,
                file_filters=None
            )
            logger.info(f"asking support agent with context: {ctx}")

            if not agent_request.actions:
                logger.warning("No actions returned from support agent")
                return {"status": "error", "message": "No actions provided"}

            if agent_request.data_to_use:
                ctx.data.update(agent_request.data_to_use)

            logger.info(f"Support agent output: {agent_request}")

            first_action = agent_request.actions[0]

            if first_action.action in [
                "request_clarification",
                "reject",
                "acknowledge",
                "respond_directly",
            ]:
                return {
                    "status": first_action.action,
                    "message": first_action.message.strip(),
                    "meta": {},
                }

            agent_id = first_action.agent
            result: SupportAgentResponse = await self._process_action(
                agent_id, ctx, None
            )

            meta = Meta(actions=[])

            if result.invite_dependent_intent is InviteDependentIntent.TRUE:
                invite_component = InteractiveComponent(
                    screen_name="InviteDependent",
                    type="SLIDEUP",
                    icon="ask-digbi-invite-family",
                    color="blue",
                    display_text="Share Digbi for free!",
                )
                meta.actions.append(invite_component)
            return {
                "status": result.status,
                "message": result.message,
                "meta": meta.model_dump_json(),
            }
        except Exception as e:
            logger.error(f"Exception in support agent {e}")
            return "Support agent erred out"

    async def _process_action(
        self,
        agent_id: str,
        ctx: ModelContext,
        file_filters: dict | None,
    ) -> SupportAgentResponse:
        """Dispatch the request to the specialized support agent."""

        try:
            # Pass through raw file_filters; AiCoreService will normalize
            filters = file_filters if (file_filters and isinstance(file_filters, dict)) else None
            agent_kwargs: dict[str, object] = {
                "agent_id": agent_id,
                "ctx": ctx,
                "output_type": SupportAgentResponse,
                "file_filters": filters,
            }

            agent_response: SupportAgentResponse = await self.ai.run_agent(
                **agent_kwargs
            )

            agent_response = await maybe_retry_with_kb_guidance(
                ai=self.ai,
                ctx=ctx,
                agent_kwargs=agent_kwargs,
                result=agent_response,
                logger=logger,
                log_message="Retrying delegated agent %s with knowledge base guidance",
                log_args=(agent_id,),
            )

            logger.info(
                f"Response from {agent_id}: {agent_response.model_dump()}"
            )
            utils.slack_util.send_slack_askdigbi_log(
                f"Response from {agent_id}: ```{agent_response.model_dump_json(indent=2)}```"
            )

            return agent_response
        except Exception as e:
            logger.exception(f"Error running agent {agent_id}: {e}")
            utils.slack_util.send_slack_askdigbi_log(f"Error running agent {agent_id} {str(e)}")
            response = SupportAgentResponse(
                status="error",
                message=f"Error running agent {agent_id} {str(e)}",
            )
            return response
