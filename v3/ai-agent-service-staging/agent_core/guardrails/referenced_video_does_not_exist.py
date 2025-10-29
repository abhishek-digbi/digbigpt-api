"""Guardrail ensuring agents do not reference unavailable videos."""

from __future__ import annotations

import re
from typing import Any, Iterable

from agents import output_guardrail
from agents.guardrail import GuardrailFunctionOutput

from agent_core.config.logging_config import logger

REFERENCED_VIDEO_DOES_NOT_EXIST_GUARDRAIL_MESSAGE = (
    "Video recommendation is unavailable; remove video references from the response."
)

_VIDEO_KEYWORD_PATTERN = re.compile(r"video", re.IGNORECASE)
_VIDEO_SCREEN_NAMES = {"videopopupscreen"}


def _video_keyword_present(text: Any) -> bool:
    if not text:
        return False
    try:
        text_value = str(text)
    except Exception:
        return False
    return bool(_VIDEO_KEYWORD_PATTERN.search(text_value))


def _normalize_meta_actions(agent_output: Any) -> Iterable[Any]:
    if agent_output is None:
        return []

    if isinstance(agent_output, dict):
        meta = agent_output.get("meta") or {}
        if isinstance(meta, dict):
            actions = meta.get("actions")
        else:
            actions = getattr(meta, "actions", None)
        if actions is None:
            actions = agent_output.get("actions")
    else:
        meta = getattr(agent_output, "meta", None)
        actions = getattr(meta, "actions", None)
        if actions is None:
            actions = getattr(agent_output, "actions", None)

    if not actions:
        return []

    if isinstance(actions, Iterable) and not isinstance(actions, (str, bytes)):
        return actions

    return [actions]


def _has_video_action(agent_output: Any) -> bool:
    for action in _normalize_meta_actions(agent_output):
        if action is None:
            continue

        if isinstance(action, dict):
            screen_name = str(action.get("screen_name", "")).strip().lower()
            display_text = action.get("display_text")
        else:
            screen_name = str(getattr(action, "screen_name", "")).strip().lower()
            display_text = getattr(action, "display_text", None)

        if screen_name in _VIDEO_SCREEN_NAMES:
            return True

        if _video_keyword_present(display_text):
            return True

        if not isinstance(action, (str, bytes)) and _video_keyword_present(action):
            return True

    return False


@output_guardrail(name="referenced_video_does_not_exist")
def referenced_video_does_not_exist_guardrail(
    context,
    agent,
    agent_output: Any,
) -> GuardrailFunctionOutput:
    """Ensure video references are removed when no recommendation is available."""

    try:
        has_video_action = _has_video_action(agent_output)

        if isinstance(agent_output, dict):
            message_flag_raw = agent_output.get("message_references_a_video", False)
        else:
            message_flag_raw = getattr(
                agent_output, "message_references_a_video", False
            )

        try:
            message_flag = bool(message_flag_raw)
        except Exception:
            message_flag = False

        if message_flag and not has_video_action:
            return GuardrailFunctionOutput(
                output_info=REFERENCED_VIDEO_DOES_NOT_EXIST_GUARDRAIL_MESSAGE,
                tripwire_triggered=True,
            )

        return GuardrailFunctionOutput(output_info=None, tripwire_triggered=False)
    except Exception as exc:  # pragma: no cover - guardrail must fail open
        logger.exception("Support agent no-video guardrail failed open: %s", exc)
        return GuardrailFunctionOutput(output_info=None, tripwire_triggered=False)


REFERENCED_VIDEO_DOES_NOT_EXIST_GUARDRAIL = (
    referenced_video_does_not_exist_guardrail
)

NO_VIDEO_WITHOUT_RECOMMENDATION_GUARDRAIL = (
    referenced_video_does_not_exist_guardrail
)
