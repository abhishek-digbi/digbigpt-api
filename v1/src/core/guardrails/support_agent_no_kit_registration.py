"""Guardrail preventing kit registration instructions from the support agent."""

from __future__ import annotations

from typing import Any

from agents import output_guardrail
from agents.guardrail import GuardrailFunctionOutput

from agent_core.models.support_intents import KitRegistrationIntent

SUPPORT_AGENT_KIT_REGISTRATION_MESSAGE = (
    "Digbi users do not need to register kits; please correct the guidance."
)


@output_guardrail(name="support_agent_no_kit_registration")
def support_agent_no_kit_registration_guardrail(
    context,
    agent,
    agent_output: Any,
) -> GuardrailFunctionOutput:
    """Trip when the support agent attempts to instruct kit registration."""

    intent_value: KitRegistrationIntent | None = None
    if agent_output is not None:
        if isinstance(agent_output, dict):
            intent_value = agent_output.get("kit_registration_intent")
        else:
            intent_value = getattr(agent_output, "kit_registration_intent", None)

    if isinstance(intent_value, str):
        try:
            intent_value = KitRegistrationIntent(intent_value)
        except ValueError:
            intent_value = None

    if intent_value is KitRegistrationIntent.REGISTER:
        return GuardrailFunctionOutput(
            output_info=SUPPORT_AGENT_KIT_REGISTRATION_MESSAGE,
            tripwire_triggered=True,
        )

    return GuardrailFunctionOutput(output_info=None, tripwire_triggered=False)


SUPPORT_AGENT_NO_KIT_REGISTRATION_GUARDRAIL = support_agent_no_kit_registration_guardrail
