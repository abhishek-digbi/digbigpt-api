# Understanding Tools

A **tool** is simply a Python function that the AI Agent Service can call during an agent run. Tools give the language model access to actions or data it cannot produce on its own, such as fetching user information or performing calculations. Any function can become a tool by decorating it with `@tool` from the `tools` package.

```python
from tools import tool

@tool
def greet(name: str) -> str:
    """Return a friendly greeting."""
    return f"Hello {name}!"
```

Decorated functions are automatically added to the global tool registry. You can reference them by name in an agent configuration or provide them directly when calling `AiCoreService.run_agent`.

## Where to Define Tools

Built‑in tool functions live under `tools/definitions/`. To add a new tool:

1. Create a module in `tools/definitions/` (for example `tools/definitions/greeting.py`).
2. Import `tool` from the `tools` package and decorate your function.
3. Importing the top‑level `tools` package automatically discovers all modules in `tools/definitions`, so no extra registration code is required.

```python
# tools/definitions/greeting.py
from tools import tool

@tool
def greet(name: str) -> str:
    """Return a friendly greeting."""
    return f"Hello {name}!"
```

Any functions defined this way become available to agents just like the built‑ins described below.

## When to Use Tools

- **Fetching external data.** Use tools when the model needs user‑specific information or data from another service.
- **Performing custom logic.** Tools are useful for calculations or operations that are easier in Python than in a prompt.
- **Structured outputs.** When you need a predictable JSON result, a tool can guarantee the correct format.

## When Not to Use Tools

- **Simple text generation.** If the model can answer using only its prompt and context, tools are unnecessary.
- **Heavy computation.** Long‑running or resource‑intensive tasks should be handled outside of the agent workflow.

## Built‑in Tools

The `ToolService` automatically exposes tools for each entry in `api_data_config`. For every variable name there is a corresponding tool named `get_<variable>`. For example, the configuration defines `gut_report_data`, so you automatically get a `get_gut_report_data` tool that returns that value for a given user token.

```python
from tools import ToolService

svc = ToolService()
my_tool = svc.get_tool("get_gut_report_data")
```

Generated tools optionally accept a `last_num_days` argument when their API mapping supports time ranges. For those tools, the function calculates the corresponding `from_date` and `to_date` internally, defaulting to the previous seven days. These built‑ins allow agents to retrieve API data without writing custom functions.

## Using Tools with Agents

List tool names in the agent configuration or pass tool objects to `run_agent`:

```yaml
MY_AGENT:
  langfuse_prompt_key: my_prompt
  tools:
    - get_gut_report_data
```

```python
ctx = BaseModelContext(query="hello", user_token="abc")
result = await ai_core.run_agent("MY_AGENT", ctx, tools=[greet])
```

The service merges any provided tools with those listed in the configuration and the built‑ins from `ToolService`.

For a step‑by‑step example see `docs/example_function_tools_agent.md`.
