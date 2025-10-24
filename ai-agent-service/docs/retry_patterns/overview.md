# Retry Patterns Overview

The service implements two retry strategies when agent runs need correction:

- **Retry with run input list** – the second attempt replays the *entire*
  previous conversation, including tool calls and responses, then adds a system
  message instructing the model to invoke the missing tooling. See
  `retry_with_run_input_list.md`.
- **Retry with run output** – the retry only sends the most recent user turn and
  the previous assistant output, followed by targeted guidance. This keeps the
  base prompt intact while nudging the final answer. See
  `retry_with_run_output.md`.

Both patterns rely on the run metadata captured by `OpenAIService`, but they
target different failure modes and therefore differ in how much history they
resend.
