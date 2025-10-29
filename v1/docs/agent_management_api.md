# Agent Management API

This guide explains how to manage custom AI agents through the service's REST endpoints. These APIs allow you to create, update, run, and list agent configurations at runtime.

## Create an Agent

`POST /api/agents`

Create a new agent configuration. `id` and `langfuse_prompt_key` are required. `name` is optional and defaults to the same value as `id`. Other fields use defaults if omitted.

```json
{
  "id": "MY_AGENT",
  "name": "MY_AGENT",
  "provider": "openai",
  "model": "gpt-4o",
  "langfuse_prompt_key": "prompt_key",
  "text_format": "markdown",
  "assistant_id": "asst_123",
  "instructions": "Optional instructions",
  "vector_store_ids": ["store1", "store2"]
}
```

Responses:
- **201** Agent created
- **400** Invalid input
- **500** Error creating agent

## Update an Agent

`PUT /api/agents/{agent_id}`

Update an existing agent. The request body follows the same format as creation. `langfuse_prompt_key` must be provided.

Responses:
- **200** Agent updated
- **404** Agent not found
- **400** Invalid input
- **500** Error updating agent

## Run an Agent

`POST /api/run-agent/{agent_id}`

Execute an agent by identifier. Provide a context payload that becomes the model context.

Example request:
```json
{
  "query_id": "12345",
  "query": "How much protein is in 2 eggs?",
  "feature_context": "nutrition",
  "user_type": "PRODUCTION",
  "conversation_history": {},
  "data": {},
  "user_token": "token123"
}
```

Responses:
- **200** Result from the agent in `result`
- **500** Error processing the task

## List Agents

`GET /api/agents`

Retrieve all stored agent configurations.

Responses:
- **200** Array of agents with their fields (id, name, provider, model, etc.)
- **500** Error fetching agents
