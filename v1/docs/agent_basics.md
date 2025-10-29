# Understanding Agents

This document explains the concept of an **Agent** in the AI Agent Service and guides non-developers on how to create one using the API. It focuses on the purpose of each configuration field so you can craft new agents without digging into the code.

## What is an Agent?

An agent is a set of instructions that the service uses to interact with a Large Language Model (LLM). Each agent has its own prompt key, model settings, and optional tools. When you invoke an agent, the service gathers the required context (such as user data) and sends a prompt to the LLM. The LLM's response becomes the agent's answer.

Agents are stored in the database and can also be seeded from the `agent_core/agents_seed.yaml` file. They can be created or updated at runtime through the **Agent Management API**.

## Creating an Agent

Use the `POST /api/agents` endpoint to create a new agent. Below are the fields you can provide. Only `id` and `langfuse_prompt_key` are required; everything else is optional.

### Parameters

| Field | Description |
|-------|-------------|
| **id** | Unique identifier for the agent. This value is used when calling the agent. |
| **name** | Human-friendly name. Defaults to the same value as `id` if omitted. |
| **provider** | LLM provider to use. Currently `openai` is supported. Defaults to `openai`. |
| **model** | The specific LLM model, e.g. `gpt-4o`. Defaults to `gpt-4o`. |
| **langfuse_prompt_key** | Key used to load the prompt from LangFuse. This ties the agent to a prompt defined in the LangFuse dashboard. **Required**. |
| **text_format** | Expected format of the LLM response. Use `markdown` for normal text or `json` when the response should be a JSON object. |
| **assistant_id** | Optional ID of an OpenAI assistant if the agent should run through the assistant API. |
| **instructions** | Extra system instructions appended to the prompt before sending it to the LLM. |
| **vector_store_ids** | List of vector store IDs that supply additional knowledge to the agent. |
| **tools** | Names of built‑in tools the agent can call during execution. Tools allow the LLM to fetch data or perform actions. See `docs/example_function_tools_agent.md` for custom tool examples. |
| **temperature** | Sampling temperature for the LLM. Lower values make responses more deterministic. |
| **top_p** | Alternative to temperature for controlling randomness. |

### Example Request

```json
{
  "id": "MY_AGENT",
  "langfuse_prompt_key": "my_prompt",
  "model": "gpt-4o",
  "text_format": "markdown",
  "tools": ["get_gut_report_data"],
  "temperature": 0.1
}
```

This creates an agent that will use the prompt stored under `my_prompt` in LangFuse, run the `gpt-4o` model, and have access to the `get_gut_report_data` tool.

## Running Your Agent

Once created, invoke the agent using `POST /api/run-agent/{agent_id}` with a context payload. The service will fetch any required variables, construct the prompt using the LangFuse key, call the model, and return the result.

For more details on the API itself, see [Agent Management API](agent_management_api.md).
