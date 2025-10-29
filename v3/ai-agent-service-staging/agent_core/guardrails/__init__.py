"""Guardrail implementations used across agent services."""

from __future__ import annotations

from .referenced_video_does_not_exist import (
    NO_VIDEO_WITHOUT_RECOMMENDATION_GUARDRAIL,
    REFERENCED_VIDEO_DOES_NOT_EXIST_GUARDRAIL,
    REFERENCED_VIDEO_DOES_NOT_EXIST_GUARDRAIL_MESSAGE,
    referenced_video_does_not_exist_guardrail,
)
from .summarizer_no_duplicate_links import (
    SUMMARIZER_DUPLICATE_LINK_GUARDRAIL_MESSAGE,
    SUMMARIZER_NO_DUPLICATE_LINK_GUARDRAIL,
    summarizer_no_duplicate_links_guardrail,
)
from .support_agent_no_kit_registration import (
    SUPPORT_AGENT_KIT_REGISTRATION_MESSAGE,
    SUPPORT_AGENT_NO_KIT_REGISTRATION_GUARDRAIL,
    support_agent_no_kit_registration_guardrail,
)
from .utils import _extract_candidate_messages

__all__ = [
    "SUPPORT_AGENT_KIT_REGISTRATION_MESSAGE",
    "SUPPORT_AGENT_NO_KIT_REGISTRATION_GUARDRAIL",
    "support_agent_no_kit_registration_guardrail",
    "REFERENCED_VIDEO_DOES_NOT_EXIST_GUARDRAIL_MESSAGE",
    "NO_VIDEO_WITHOUT_RECOMMENDATION_GUARDRAIL",
    "REFERENCED_VIDEO_DOES_NOT_EXIST_GUARDRAIL",
    "referenced_video_does_not_exist_guardrail",
    "SUMMARIZER_DUPLICATE_LINK_GUARDRAIL_MESSAGE",
    "SUMMARIZER_NO_DUPLICATE_LINK_GUARDRAIL",
    "summarizer_no_duplicate_links_guardrail",
    "_extract_candidate_messages",
]
