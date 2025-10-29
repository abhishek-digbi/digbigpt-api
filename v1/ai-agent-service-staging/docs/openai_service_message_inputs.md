# OpenAI Service Message Parameters

This note captures how the three message-related kwargs that travel from
`AiCoreService.run_agent` into `OpenAIService.run` behave, when they are chosen,
and who uses them today. These knobs layer on top of each other, so keeping the
intent behind each one documented helps avoid accidental regressions.

## Payload selection order

When the OpenAI adapter assembles the message payload for the agent flow, it
checks the kwargs in the following priority (`agent_core/services/adapters/openai_service.py`):

1. **`input_messages`** – If provided, it bypasses all payload builders and the
   supplied list is sent to `Runner.run` exactly as-is. This is how orchestrators
   can rerun an agent with the previous exchange plus custom guidance.
2. **`role_based_messages_as_input`** – If truthy (and `input_messages` was not
   supplied) the adapter calls `_build_agent_payload_v2`, which reconstructs a
   conversation transcript from `ModelContext.conversation_history` and the
   latest `ctx.query`, attaching any `additional_messages`. The AiCore service
   flips this flag only for agents listed in the
   `AGENTS_USING_ROLE_BASED_MESSAGES_INPUT` env var when the caller is not a beta
   or production user.
3. **Fallback (`_build_agent_payload`)** – Used when neither of the above routes
   triggers. The resulting payload contains just the current prompt (and image,
   if provided) plus any `additional_messages` appended afterward.

## Parameter cheat sheet

| Kwarg | What it controls | Who sets it | Typical use cases |
| --- | --- | --- | --- |
| `input_messages` | Complete payload override | Support and Nutrition orchestrators | Retrying after a guardrail or missing tool usage with the previously generated messages and extra system guidance |
| `role_based_messages_as_input` | Whether to rebuild the payload from structured history | AiCore service, based on env allowlist | Gradual rollout of richer, role-tagged transcripts without changing orchestrator code |
| `additional_messages` | Extra messages appended to whichever payload was built | Summarizer orchestrator and tests; available to any caller | Supplying guardrail guidance or other follow-up instructions while keeping the base prompt intact |

## Why all three stick around

- **Different layers of control** – `input_messages` is the only way to fully
  replace the payload; `role_based_messages_as_input` changes how the base
  prompt is expanded; `additional_messages` only appends to the computed list.
  Removing any of them would collapse a layer that callers depend on today.
- **Active call sites** – All three kwargs are already exercised in production
  orchestrators (`orchestrator/orchestrators/*_agent.py`) and validated in unit
  tests within `tests/test_support_agent.py`, `tests/test_nutrition_agent.py`,
  and `tests/test_openai_tool_invocation.py`. Eliminating one would require
  rewriting those flows.
- **Operational safety knobs** – The env-driven rollout for
  `role_based_messages_as_input` lets ops toggle the richer transcript feed without
  redeploying code, while `additional_messages` and `input_messages` enable
  guardrail recovery patterns that keep retries deterministic.

