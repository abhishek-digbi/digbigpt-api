from typing import TYPE_CHECKING

import utils.slack_util
from agents.exceptions import OutputGuardrailTripwireTriggered
from agent_core.config.logging_config import logger
from agent_core.guardrails import (
    REFERENCED_VIDEO_DOES_NOT_EXIST_GUARDRAIL,
    REFERENCED_VIDEO_DOES_NOT_EXIST_GUARDRAIL_MESSAGE,
    SUMMARIZER_DUPLICATE_LINK_GUARDRAIL_MESSAGE,
    SUMMARIZER_NO_DUPLICATE_LINK_GUARDRAIL,
    _extract_candidate_messages,
)
from agent_core.services.model_context import ModelContext
from orchestrator.orchestrators.agent_models import SummarizerAgentResponse
from orchestrator.orchestrators.base_ask_digbi_agent import AskDigbiBaseAgent
from tools.definitions.common import recommend_videos

if TYPE_CHECKING:
    from agent_core.services.ai_core_service import AiCoreService


class SummarizerAgent(AskDigbiBaseAgent):
    """Runs the ASK_DIGBI summarizer workflow and enriches the response."""

    def __init__(self, aicore: "AiCoreService") -> None:
        self.ai = aicore
        self._referenced_video_does_not_exist_guidance = (
            "Video guidance: The recommendation failed. Remove any video references or actions before responding."
        )
        self._duplicate_link_guidance = (
            "Hyperlink guidance: Remove hyperlinks already provided via the video recommendation component."
        )

    async def ask(self, ctx: ModelContext) -> dict[str, object]:
        user_type = (getattr(ctx, "user_type", "") or "").strip().lower()
        ctx_data = getattr(ctx, "data", {}) or {}
        formatted_responses = ctx_data.get("formatted_responses") or []

        support_agent_response_present = any(
            isinstance(item, dict) and item.get("agent") == "support_agent" and item.get("status") != "rejected"
            for item in formatted_responses
        )

        video_feature_enabled = user_type in {"alpha"} and support_agent_response_present

        if not video_feature_enabled:
            result = await self.ai.run_agent("ASK_DIGBI_SUMMARIZER_AGENT", ctx)
            utils.slack_util.send_slack_askdigbi_log(
                f"*User_Token:* {ctx.user_token} *[{ctx.user_type}]* *Query_ID:* {ctx.query_id}\n"
                f"*USER QUERY*:```{ctx.query}``` "
                f"*FINAL RESPONSE*: ```{result}```")
            logger.info(f"Response from Digbi Summarizer: {result}")
            return result

        agent_kwargs: dict[str, object] = {}
        if video_feature_enabled:
            agent_kwargs.update(
                {
                    "tools": [recommend_videos],
                    "tool_choice": "recommend_videos",
                }
            )

        async def _invoke_summarizer(
            *, additional_messages: list[dict[str, str]] | None = None
        ) -> SummarizerAgentResponse:
            kwargs = dict(agent_kwargs)
            if additional_messages:
                kwargs["additional_messages"] = additional_messages

            return await self.ai.run_agent(
                "ASK_DIGBI_SUMMARIZER_AGENT",
                ctx,
                output_type=SummarizerAgentResponse,
                output_guardrails=[
                    REFERENCED_VIDEO_DOES_NOT_EXIST_GUARDRAIL,
                    SUMMARIZER_NO_DUPLICATE_LINK_GUARDRAIL,
                ],
                **kwargs,
            )

        logger.info(
            "Asking Summarizer Agent: user=%s qid=%s",
            getattr(ctx, "user_token", None),
            getattr(ctx, "query_id", None),
        )

        try:
            response: SummarizerAgentResponse = await _invoke_summarizer()
        except OutputGuardrailTripwireTriggered as guardrail_exc:

            retry_messages = self._build_retry_messages(guardrail_exc)
            agent_kwargs.pop("tools", None)
            agent_kwargs.pop("tool_choice", None)
            try:
                response = await _invoke_summarizer(additional_messages=retry_messages)
            except OutputGuardrailTripwireTriggered:
                return {
                    "status": "error",
                    "message": REFERENCED_VIDEO_DOES_NOT_EXIST_GUARDRAIL_MESSAGE,
                    "meta": {}
                }

        utils.slack_util.send_slack_askdigbi_log(
            f"*User_Token:* {ctx.user_token} *[{ctx.user_type}]* *Query_ID:* {ctx.query_id}\\n"
            f"*USER QUERY*:```{ctx.query}``` "
            f"*FINAL RESPONSE*: ```{response.message}```"
        )
        logger.info("Response from Digbi Summarizer: %s", response)

        return {
            "status": response.status,
            "message": response.message,
            "meta": response.meta.model_dump()
        }

    def _build_retry_messages(
        self, guardrail_exc: OutputGuardrailTripwireTriggered
    ) -> list[dict[str, str]]:
        retry_messages: list[dict[str, str]] = []
        prior_output = guardrail_exc.guardrail_result.agent_output
        prior_message = None
        if prior_output is not None:
            candidate_messages = _extract_candidate_messages(prior_output)
            for msg in candidate_messages:
                if msg:
                    prior_message = msg
                    break
            if prior_message:
                retry_messages.append({"role": "assistant", "content": prior_message})

        retry_messages.append(
            {
                "role": "system",
                "content": self._select_guardrail_guidance(guardrail_exc),
            }
        )
        logger.warning(
            "Summarizer guardrail triggered; retrying with additional instructions"
        )
        return retry_messages

    def _select_guardrail_guidance(
        self, guardrail_exc: OutputGuardrailTripwireTriggered
    ) -> str:
        result = guardrail_exc.guardrail_result
        name = result.guardrail.get_name()
        output_info = result.output.output_info

        if name == "summarizer_no_duplicate_links":
            return self._duplicate_link_guidance

        if isinstance(output_info, str) and output_info == SUMMARIZER_DUPLICATE_LINK_GUARDRAIL_MESSAGE:
            return self._duplicate_link_guidance

        return self._referenced_video_does_not_exist_guidance
