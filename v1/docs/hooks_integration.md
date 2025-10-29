# Hooks Integration

This guide outlines how lifecycle hooks flow through the AI Agent Service and
how to extend them for custom instrumentation or orchestration.

## Lifecycle hook classes

The underlying `agents` library exposes two hook interfaces in
`agents/lifecycle.py`:

- `AgentHooks` receives callbacks scoped to a single `Agent` instance (start,
  end, handoffs, tool calls).
- `RunHooks` observes the entire `Runner.run` execution, including agent
  switches and tool invocations across nested handoffs.

Subclass either interface and override the `async` callbacks you need. Each
callback receives a `RunContextWrapper` that exposes the active model context,
tooling results, and run metadata.

## Propagation through AiCoreService

1. Orchestrators call `AiCoreService.run_agent(..., hooks=my_hooks)` to attach a
   hook instance to an agent execution (`agent_core/services/ai_core_service.py:52`).
2. `run_agent` forwards the hook to `_execute_adapter` unchanged, alongside
   other adapter parameters (`agent_core/services/ai_core_service.py:133`).
3. `_execute_adapter` injects the hook into the selected adapter via the
   `hooks` keyword argument (`agent_core/services/ai_core_service.py:320`).
4. `OpenAIService.run` receives the hook and only applies it when the OpenAI
   agent workflow is selected (i.e., when `agent_id` is provided)
   (`agent_core/services/adapters/openai_service.py:62`).

This means hooks are ignored for assistant threads and raw chat completions, but
fully supported for agent-driven runs where the `Runner` is in play.

## Agent vs. run hooks inside OpenAIService

When `_agent_flow` is invoked, the adapter inspects the provided hook instance
(`agent_core/services/adapters/openai_service.py:169`):

- If the hook is an `AgentHooks` subclass, it is attached directly to the newly
  constructed `Agent` (`agent_core/services/adapters/openai_service.py:214`).
- If the hook is a `RunHooks` subclass, it is forwarded to `Runner.run` so that
  callbacks fire for every agent transition and tool call during the run
  (`agent_core/services/adapters/openai_service.py:231`).

Passing a `RunHooks` instance allows you to observe nested agents launched via
handoffs, while `AgentHooks` limits callbacks to the specific agent being
instantiated. You can also wrap both behaviors by creating a composite object
that exposes the two interfaces and dispatches to shared logic.

## Working with run data

`OpenAIService` captures the model SDK's `input_list` on the context for each
run (`agent_core/services/adapters/openai_service.py:403`). Hook callbacks can
read or augment the same `ctx.data["run_data"]` structure via the
`RunContextWrapper` to keep observability in sync with other runtime metadata.

## Implementing and testing hooks

1. Subclass `AgentHooks` or `RunHooks` and implement the desired callbacks. Keep
   callback bodies lightweight; long-running work should be `await`ed to avoid
   blocking subsequent turns.
2. Pass the hook to `AiCoreService.run_agent` (or directly to
   `OpenAIService.run` in lower-level tests) and ensure your callbacks are
   invoked.
3. In tests, patch `Runner.run` to a stub that records the `hooks` argument, as
   demonstrated in `tests/test_openai_tool_invocation.py` for other run-time
   parameters.
4. Record any additional telemetry on the provided context rather than global
   state so subsequent agents in the same workflow can observe it.

Following this pattern keeps hook integrations localized, testable, and aligned
with the existing agent execution pipeline.
