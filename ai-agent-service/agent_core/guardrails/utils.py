"""Shared helpers for guardrail implementations."""

from __future__ import annotations

from typing import Any, Iterable


def _extract_candidate_messages(agent_output: Any) -> Iterable[str]:
    """Yield message strings from the structured support agent output."""

    if agent_output is None:
        return []

    messages: list[str] = []

    def _maybe_add(value: Any) -> None:
        if value is None:
            return
        text = str(value).strip()
        if text:
            messages.append(text)

    if isinstance(agent_output, str):
        _maybe_add(agent_output)
        return messages

    if isinstance(agent_output, dict):
        _maybe_add(agent_output.get("message"))
        actions = agent_output.get("actions") or []
    else:
        _maybe_add(getattr(agent_output, "message", None))
        actions = getattr(agent_output, "actions", [])

    if actions:
        for action in actions:
            if isinstance(action, dict):
                _maybe_add(action.get("message"))
            else:
                _maybe_add(getattr(action, "message", None))

    return messages


__all__ = ["_extract_candidate_messages"]
