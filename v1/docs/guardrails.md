# Guardrails Integration

This guide explains how runtime guardrails are defined, wired into agent runs,
and handled across the AI Agent Service codebase.

## Guardrail definitions

- Output guardrails live in `agent_core/guardrails/`. Each guardrail is defined
  in its own module (for example,
  `agent_core/guardrails/support_agent_no_kit_registration.py`), decorated with
  `@output_guardrail`, and re-exported through `agent_core/guardrails/__init__.py`
  for backwards compatibility.
- The package currently exposes guardrails for:
  - Blocking kit registration instructions from support flows (definition is
    present but not actively wired into the Support agent at this time).
  - Removing video mentions when no recommendation was produced.
  - Preventing duplicate hyperlinks in summarizer responses.

## Attaching guardrails to a run

1. An orchestrator passes `output_guardrails` and/or `input_guardrails` to
   `AiCoreService.run_agent` (`agent_core/services/ai_core_service.py:57-61`).
2. `AiCoreService._execute_adapter` forwards those collections to the provider
   adapter alongside the other run kwargs
   (`agent_core/services/ai_core_service.py:332-360`).
3. `OpenAIService._create_agent` registers the guardrails on the `Agent`
   instance that will be executed (`agent_core/services/adapters/openai_service.py:176-285`).

At runtime the underlying agents library evaluates guardrails before and/or
after each turn depending on the type (input vs. output).

## Handling tripwire exceptions

- If a guardrail fires, the agents runtime raises
  `InputGuardrailTripwireTriggered` or `OutputGuardrailTripwireTriggered`.
  `OpenAIService._invoke_agent` does not swallow these—it propagates them to the
  caller so orchestrators or tools can respond (`agent_core/services/adapters/openai_service.py:389-412`).
- The Summarizer orchestrator retries with additional guidance when an output
  guardrail trips, removing optional tools on the second attempt
  (`orchestrator/orchestrators/summarizer_agent.py:50-88`).
- Shared tools, such as `recommend_videos`, log and return `None` when a
  guardrail blocks the nested agent run to keep parent agents stable
  (`tools/definitions/common.py:52-64`).

## Example usage

- Summarizer attaches the "no video" and "no duplicate link" guardrails to
  every request and builds retry messages from the first response when a
  guardrail fires (`tests/test_summarizer_agent.py:75-149`).

## Adding a new guardrail

1. Create a new module under `agent_core/guardrails/` and implement the guardrail
   function inside it. Decorate the function with `@output_guardrail` (or the
   appropriate decorator) and add any helper constants nearby for clarity.
2. Re-export the guardrail from `agent_core/guardrails/__init__.py` so existing
   imports continue to work.
3. Decide which orchestrators or tools should apply it and pass the guardrail in
   their `run_agent` call.
4. Write tests that simulate the tripwire by raising the corresponding
   guardrail exception, ensuring retry behavior or failure handling matches
   expectations (see `tests/test_summarizer_agent.py:131-189` for a pattern).

Following this pattern keeps guardrail behavior observable, testable, and easy
to extend as policies evolve.
