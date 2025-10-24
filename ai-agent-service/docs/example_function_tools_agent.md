# Example: Agent with Function Tools

This example demonstrates how to define custom function tools and provide them when running an agent.  Decorating a function with `@tool` automatically registers it so it can be referenced by name in your agent config. Any tools passed to `run_agent` are automatically combined with tools listed in the configuration and the built-ins from `ToolService`.
Functions may be synchronous or `async`. Each tool should include a description,
either via the optional `description` argument to `@tool` or in the function's
docstring. If no description is provided, a warning is logged when the tool is
registered.

```python
from tools import tool
from agent_core.services.ai_core_service import AiCoreService
from agent_core.services.model_context import BaseModelContext

# Define a simple tool using the decorator
@tool
def greet(name: str) -> str:
    """Return a friendly greeting."""
    return f"Hello {name}!"

async def main(ai_core: AiCoreService):
    ctx = BaseModelContext(query="Say hello", user_token="demo")
    result = await ai_core.run_agent(
        "USER_DATA_AGENT",
        ctx,
        tools=[greet],
    )
    print(result)
```

The agent configuration can list built-in tool names so they are loaded automatically:

```yaml
USER_DATA_AGENT:
  name: USER_DATA_AGENT
  langfuse_prompt_key: user_profile_info
  tools:
    - get_gut_report_data
```
