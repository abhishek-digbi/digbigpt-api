# Retry With Run Output

This pattern resends only the most recent user turn and the previous assistant
output, then appends guidance that tells the model how to fix the issue. It is
typically used after a guardrail trip, but can apply to any scenario where the
final answer needs refinement without replaying intermediate tool calls.

## How guardrails trigger retries

1. Guardrail functions raise `InputGuardrailTripwireTriggered` or
   `OutputGuardrailTripwireTriggered`. The OpenAI adapter surfaces these to the
   caller without swallowing them (`agent_core/services/adapters/openai_service.py:389-412`).
2. The Summarizer orchestrator catches the exception, removes optional tools,
   and constructs retry messages that include the offending response plus
   remediation instructions (`orchestrator/orchestrators/summarizer_agent.py:50-88`).
3. The retry uses `additional_messages` so the base prompt stays intact while
   the agent sees both its prior answer and the guardrail guidance.

See `docs/guardrails.md` for a catalog of guardrails and integration details.

## Example: video reference guardrail

```
First run payload (simplified):
  - {"role": "system", "content": "Summarizer instructions and context"}
  - {"role": "user", "content": "Summarize the latest guidance"}

Assistant output that triggered the guardrail:
  - {"role": "assistant", "content": "Watch this video"}

Messages sent to OpenAI on the retry:
  - {"role": "system", "content": "Summarizer instructions and context"}
  - {"role": "user", "content": "Summarize the latest guidance"}
  - {"role": "assistant", "content": "Watch this video"}
  - {
      "role": "system",
      "content": "Video guidance: The recommendation failed. Remove any video references or actions before responding."
    }

Outcome: the guardrail no longer triggers, and the summarizer returns guidance
without video references on the second attempt.
```

Unit tests covering the behavior: `tests/test_summarizer_agent.py:109-149`.
