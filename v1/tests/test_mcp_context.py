import json
from agent_core.services.model_context import BaseModelContext, MCP_VERSION


def test_to_mcp_payload():
    ctx = BaseModelContext(context_id="123", metadata={"source": "test"})
    wrapped = ctx.to_mcp_payload("hello")
    payload = json.loads(wrapped)
    assert payload["mcp_version"] == MCP_VERSION
    assert payload["prompt"] == "hello"
    assert payload["metadata"] == {"source": "test"}
    assert payload["state"] == {}


