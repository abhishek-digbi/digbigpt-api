"""Guardrail preventing duplicate hyperlinks in summarizer responses."""

from __future__ import annotations

from typing import Any

from agents import output_guardrail
from agents.guardrail import GuardrailFunctionOutput

from agent_core.config.logging_config import logger


def _extract_urls_from_actions(actions: Any) -> set[str]:
    urls: set[str] = set()

    if not actions:
        return urls

    for action in actions:
        if isinstance(action, dict):
            data = action.get("data")
        else:
            data = getattr(action, "data", None)

        if not data:
            continue

        if not isinstance(data, (list, tuple)):
            data_iterable = [data]
        else:
            data_iterable = data

        for item in data_iterable:
            if isinstance(item, dict):
                url = item.get("url")
            else:
                url = getattr(item, "url", None)

            if not url:
                continue

            try:
                url_text = str(url).strip()
            except Exception:
                logger.debug("Unable to coerce URL from action data: %r", url)
                continue

            if url_text:
                urls.add(url_text)

    return urls


SUMMARIZER_DUPLICATE_LINK_GUARDRAIL_MESSAGE = (
    "Remove hyperlinks that already exist in the video recommendation component."
)


@output_guardrail(name="summarizer_no_duplicate_links")
def summarizer_no_duplicate_links_guardrail(
    context,
    agent,
    agent_output: Any,
) -> GuardrailFunctionOutput:
    """Trip when the summarizer repeats hyperlinks already surfaced via actions."""

    message: str | None = None
    meta: Any = None
    if isinstance(agent_output, dict):
        raw_message = agent_output.get("message")
        message = str(raw_message).strip() if raw_message is not None else None
        meta = agent_output.get("meta")
    else:
        raw_message = getattr(agent_output, "message", None)
        message = str(raw_message).strip() if raw_message is not None else None
        meta = getattr(agent_output, "meta", None)

    if not message:
        return GuardrailFunctionOutput(output_info=None, tripwire_triggered=False)

    if isinstance(meta, dict):
        actions = meta.get("actions")
    else:
        actions = getattr(meta, "actions", None)

    urls = _extract_urls_from_actions(actions)
    if not urls:
        return GuardrailFunctionOutput(output_info=None, tripwire_triggered=False)

    message_lower = message.lower()

    for url in urls:
        url_lower = url.lower()
        if url_lower and url_lower in message_lower:
            return GuardrailFunctionOutput(
                output_info=SUMMARIZER_DUPLICATE_LINK_GUARDRAIL_MESSAGE,
                tripwire_triggered=True,
            )

        if url_lower.startswith("http://") or url_lower.startswith("https://"):
            stripped = url_lower.split("://", 1)[1]
            if stripped and stripped in message_lower:
                return GuardrailFunctionOutput(
                    output_info=SUMMARIZER_DUPLICATE_LINK_GUARDRAIL_MESSAGE,
                    tripwire_triggered=True,
                )

    return GuardrailFunctionOutput(output_info=None, tripwire_triggered=False)


SUMMARIZER_NO_DUPLICATE_LINK_GUARDRAIL = summarizer_no_duplicate_links_guardrail
