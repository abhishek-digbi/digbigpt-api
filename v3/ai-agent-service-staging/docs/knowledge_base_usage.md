# Knowledge Base Usage Tracking

This guide explains how the service determines whether an agent run actually
invoked the knowledge base (file search) tooling, and how orchestrators react
when it does not.

## Data captured during agent execution

1. `OpenAIService._invoke_agent` clears a `run_data` slot on the model context
   before each run (`agent_core/services/adapters/openai_service.py:398-406`).
2. After `Runner.run` returns, the adapter calls `_store_run_input_list`, which
   persists the agent’s `to_input_list()` output inside `ctx.data["run_data"]`
   under a key of the form `<agent_id>::<context_id>`
   (`agent_core/services/adapters/openai_service.py:424-439`). This list
   captures every turn and tool invocation produced by the runner.

The structure is lightweight, so multiple runs of the same agent append entries
to that key, with the most recent input list available via
`OpenAIService.get_run_input_list(...)` (`agent_core/services/adapters/openai_service.py:452-470`).

## Detecting knowledge base access

`OpenAIService.did_run_use_file_search(ctx, agent_id)` inspects the stored input
list and returns `True` when any entry has `type == "file_search_call"`
(`agent_core/services/adapters/openai_service.py:472-487`). The presence of this
marker indicates the run called the OpenAI `file_search` tool, which is how the
knowledge base is currently exposed to agents.

## How orchestrators use the signal

- Support and Nutrition orchestrators call `did_run_use_file_search` after each
  delegated agent run. If the result is `False`, they construct a new message
  list (via `OpenAIService.get_run_input_list`) and retry the agent with a
  system instruction that nudges it to perform a knowledge-base search
  (`orchestrator/orchestrators/support_agent.py:111-128`,
  `orchestrator/orchestrators/nutrition_agent.py:606-624`).
- Unit tests assert both the detection logic and the retry payload assembly
  (`tests/test_support_agent.py:138-150`, `tests/test_nutrition_agent.py:156-184`).

## Extending the tracking

- Any new adapter or orchestrator can rely on the same helper: ensure the
  adapter stores the runner input list (or implements an equivalent hook) and
  check for `file_search_call` entries to confirm knowledge base usage.
- If additional knowledge mechanisms are added (e.g., vector DB lookups exposed
  as different tool types), extend `_store_run_input_list` or
  `did_run_use_file_search` to recognize the new markers.

## Concurrency considerations

- The run-data cache lives on `ctx.data`, so concurrent agent executions must
  operate on distinct `ModelContext` instances. Each request handler builds a
  new `BaseModelContext` before invoking `run_agent`
  (e.g. `orchestrator/api/controllers/ask_digbi_controller.py:82-111`,
  `orchestrator/api/controllers/meal_rating_controller.py:209-248`),
  ensuring isolation between simultaneous users.
- Within a single request, repeated calls to `run_agent` with the same
  `agent_id` happen sequentially; `_reset_run_data_entry` clears the slot before
  each call, and `_store_run_input_list` appends the newest input list. This
  guarantees the retry logic always inspects the most recent attempt while still
  preserving earlier entries for debugging.
- When Ask Digbi fans out actions concurrently it creates a shallow copy of the
  model context per action and clones the `data` dict before dispatching to the
  downstream agent (`orchestrator/orchestrators/ask_digbi_agent.py:108-156`).
  That keeps each parallel agent run’s `run_data` independent even though they
  share the same parent request.

By keeping the evidence in `ctx.data["run_data"]` we avoid global state and make
each run self-diagnosing, which is especially useful for retries, telemetry, and
tests.
