from __future__ import annotations

from collections.abc import Mapping
from logging import Logger
from typing import TypeVar

from agent_core.services.adapters.openai_service import OpenAIService
from agent_core.services.ai_core_service import AiCoreService
from agent_core.services.model_context import ModelContext


T = TypeVar("T")

_GUIDANCE_MESSAGE = {
    "role": "system",
    "content": (
        "Before finalizing your answer, perform a knowledge-base file search "
        "using the file_search tool so your response reflects the latest KB context."
    ),
}


async def maybe_retry_with_kb_guidance(
    *,
    ai: AiCoreService,
    ctx: ModelContext,
    agent_kwargs: Mapping[str, object],
    result: T,
    logger: Logger,
    log_message: str,
    log_args: tuple[object, ...] = (),
    usage_key: str | None = None,
) -> T:
    """Ensure the run utilizes knowledge base search before returning.

    If the initial run skipped file search, retry with an appended guidance message.
    """

    key = usage_key or agent_kwargs.get("agent_id")
    if not key:
        return result

    used = OpenAIService.did_run_use_file_search(ctx, key)  # type: ignore[arg-type]
    if used:
        return result

    logger.info(log_message, *log_args)

    run_input = OpenAIService.get_run_input_list(ctx, key)  # type: ignore[arg-type]
    retry_messages = list(run_input) if isinstance(run_input, list) else []
    retry_messages.append(_GUIDANCE_MESSAGE.copy())

    retry_kwargs = dict(agent_kwargs)
    retry_kwargs["input_messages"] = retry_messages

    return await ai.run_agent(**retry_kwargs)
