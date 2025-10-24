# Retry With Run Input List

This pattern replays the full input list from the previous attempt—messages,
tool calls, and results—before adding corrective guidance. We commonly use it
when the agent skipped a required tool such as the knowledge base
(`file_search`). The orchestrator captures the first run’s inputs, appends the
reminder, and replays the conversation so the model can comply.

## How detection works

1. `OpenAIService` resets and stores each run’s `input_list` inside the model
   context (`agent_core/services/adapters/openai_service.py:398-439`).
2. `did_run_use_file_search(ctx, agent_id)` inspects the latest list for a
   `file_search_call` entry (`agent_core/services/adapters/openai_service.py:472-487`).
3. If the knowledge base was skipped, orchestrators fetch the prior list via
   `get_run_input_list(...)` and construct a retry payload with an extra system
   reminder (`orchestrator/orchestrators/support_agent.py:111-128`,
   `orchestrator/orchestrators/nutrition_agent.py:606-624`).

See `docs/knowledge_base_usage.md` for full tracking and concurrency details.

## Example: ask digbi meal feedback follow-up request to nutrition agent

```
First run messages sent to OpenAI:
  - {"role": "system", "content": "Instructions and user context/data"}
  - {"role": "user", "content": "How was my meal rated?"}

Input list captured after first run (no KB query observed):
  1. {"type": "message", "role": "system", "content": "Instructions and user context/data"}
  2. {"type": "message", "role": "user", "content": "How was my meal rated?"}
  3. {"type": "tool_call", "tool_name": "get_meal_feedback", "arguments": {"meal_id": "abc123"}}
  4. {"type": "tool_result", "tool_name": "get_meal_feedback", "output": {"score": 14, "notes": "Great balance"}}
  5. {"type": "message", "role": "assistant", "content": "Your meal scored 14 with feedback: Great balance."}

Retry messages sent to OpenAI (adds KB guidance):
  1. {"type": "message", "role": "system", "content": "Instructions and user context/data"}
  2. {"type": "message", "role": "user", "content": "How was my meal rated?"}
  3. {"type": "tool_call", "tool_name": "get_meal_feedback", "arguments": {"meal_id": "abc123"}}
  4. {"type": "tool_result", "tool_name": "get_meal_feedback", "output": {"score": 14, "notes": "Great balance"}}
  5. {"type": "message", "role": "assistant", "content": "Your meal scored 14 with feedback: Great balance."}
  6. {
       "role": "system",
       "content": "Before finalizing your answer, perform a knowledge-base file search using the file_search tool so your response reflects the latest KB context."
     }

Outcome: the subsequent input list now includes a `file_search_call` followed by
the assistant’s revised reply, so the orchestrator can confirm the knowledge
base was used on the retry.
```

Unit tests that exercise this pattern: `tests/test_support_agent.py:138-150` and
`tests/test_nutrition_agent.py:156-184`.
