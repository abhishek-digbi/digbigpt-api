import utils.slack_util
from agent_core.config.logging_config import logger
from agent_core.models.support_intents import InviteDependentIntent
from agent_core.services.ai_core_service import AiCoreService
from agent_core.services.model_context import ModelContext
from orchestrator.orchestrators.agent_models import (
    SupportAgentResponse, Meta, InteractiveComponent, ProgramDetailsAgentResponse
)
from orchestrator.orchestrators.base_ask_digbi_agent import AskDigbiBaseAgent
from orchestrator.orchestrators.kb_retry import maybe_retry_with_kb_guidance

agent_id = "UNIFIED_SUPPORT_AGENT"


class UnifiedSupportAgent(AskDigbiBaseAgent):
    def __init__(self, aicore: AiCoreService):
        self.ai = aicore
        self.agent_id = "UNIFIED_SUPPORT_AGENT"

    async def ask(self, ctx: ModelContext):

        try:

            program_details_response: ProgramDetailsAgentResponse = await self.ai.run_agent(
                "PROGRAM_DETAILS_AGENT",
                ctx,
                output_type=ProgramDetailsAgentResponse,
                strict_json_schema=False,
                file_filters=None
            )

            logger.info(f"Response from PROGRAM_DETAILS_AGENT: {program_details_response.model_dump()}")
            if program_details_response.status == "error" or not program_details_response.program_details:
                raise RuntimeError("PROGRAM_DETAILS_AGENT failed in unified support meta agent")
            ctx.data.update(program_details_response.program_details)

            agent_kwargs: dict[str, object] = {
                "agent_id": agent_id,
                "ctx": ctx,
                "output_type": SupportAgentResponse,
            }

            support_agent_response: SupportAgentResponse = await self.ai.run_agent(
                **agent_kwargs
            )

            logger.info(f"Response from {agent_id}: {support_agent_response.model_dump()}")

            support_agent_response = await maybe_retry_with_kb_guidance(
                ai=self.ai,
                ctx=ctx,
                agent_kwargs=agent_kwargs,
                result=support_agent_response,
                logger=logger,
                log_message="Retrying unified support agent %s with knowledge base guidance",
                log_args=(agent_id,),
                usage_key=agent_id,
            )

            logger.info(f"Response from {agent_id}: {support_agent_response.model_dump()}")
            utils.slack_util.send_slack_askdigbi_log(
                f"Response from {agent_id}: ```{support_agent_response.model_dump_json(indent=2)}```"
            )

            meta = Meta(actions=[])

            if support_agent_response.invite_dependent_intent is InviteDependentIntent.TRUE:
                invite_component = InteractiveComponent(
                    screen_name="InviteDependent",
                    type="SLIDEUP",
                    icon="ask-digbi-invite-family",
                    color="blue",
                    display_text="Share Digbi for free!",
                )
                meta.actions.append(invite_component)
            return {
                "status": support_agent_response.status,
                "message": support_agent_response.message,
                "meta": meta.model_dump_json(),
            }

        except Exception as e:
            logger.exception(f"Error running agent {agent_id}: {e}")
            utils.slack_util.send_slack_askdigbi_log(
                f"Error running agent {agent_id} {str(e)}"
            )
            response = SupportAgentResponse(
                status="error",
                message=f"Error running agent {agent_id} {str(e)}",
            )
            return response
