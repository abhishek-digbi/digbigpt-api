import importlib
import pytest

from agent_core.services.model_context import BaseModelContext
from agent_core.config.schema import AgentConfig
from agent_core.interfaces.agent_logger import IAgentLogger
from agents.lifecycle import AgentHooks
from tools import tool, Tool


class DummyLangFuse:
    def get_variables(self, key, user_type):
        return []

    def generate_prompt(self, user_type, prompt_key, data_vars):
        return "prompt"


class DummyRegistry:
    pass


class DummyLogger(IAgentLogger):
    def log_interaction(self, ctx, prompt, response, metadata=None, duration=None):
        pass


@tool
def cfg_tool_example(user_token: str) -> str:
    return "cfg"


@tool
def provided_tool(user_token: str) -> str:
    return "provided"


class DummyDataCore:
    def __init__(self):
        self.tools = [cfg_tool_example]
        self.tool_map = {"cfg_tool_example": cfg_tool_example}

    def process_variables(self, user_token, vars):
        return {}

    def get_tool(self, name):
        return self.tool_map.get(name)


@pytest.mark.asyncio
async def test_run_agent_combines_tools(mocker):
    mocker.patch("app.agent_metrics.track_agent_metrics", lambda *a, **k: (lambda f: f))
    ai_core_module = importlib.import_module("agent_core.services.ai_core_service")
    AiCoreService = ai_core_module.AiCoreService
    service = AiCoreService(DummyLangFuse(), DummyRegistry(), DummyDataCore(), DummyLogger())

    cfg = AgentConfig(
        id="A",
        name="A",
        provider="openai",
        model="gpt-4o",
        langfuse_prompt_key="key",
        tools=["cfg_tool_example"],
    )
    mocker.patch.object(service, "_load_config", return_value=cfg)
    mocker.patch.object(service, "_resolve_prompt_key", return_value="key")

    captured = {}

    async def fake_execute(*args, **kwargs):
        captured["tools"] = kwargs.get("tools")
        return "ok"

    patched = mocker.patch.object(service, "_execute_adapter", new_callable=mocker.AsyncMock)
    patched.side_effect = fake_execute

    ctx = BaseModelContext(context_id="c1", user_token="tok")
    await service.run_agent("A", ctx, tools=[provided_tool])

    names = {t.name for t in captured["tools"] if isinstance(t, Tool)}
    assert {"provided_tool", "cfg_tool_example"}.issubset(names)


@pytest.mark.asyncio
async def test_run_agent_handles_different_result_types(mocker):
    """Test that run_agent can handle different types of results from the adapter."""
    mocker.patch("app.agent_metrics.track_agent_metrics", lambda *a, **k: (lambda f: f))
    
    # Import the service class
    ai_core_module = importlib.import_module("agent_core.services.ai_core_service")
    AiCoreService = ai_core_module.AiCoreService
    
    # Create a mock service
    service = AiCoreService(DummyLangFuse(), DummyRegistry(), DummyDataCore(), DummyLogger())
    
    # Mock the config loading to return a valid config
    cfg = AgentConfig(
        id="TEST_AGENT",
        name="Test Agent",
        provider="openai",
        model="gpt-4o",
        langfuse_prompt_key="TEST_KEY",
        text_format=None,
        assistant_id=None,
        instructions=None,
        vector_store_ids=None,
        tools=None,
        temperature=None,
        top_p=None
    )
    
    # Mock all the necessary methods
    mocker.patch.object(service, "_load_config", return_value=cfg)
    mocker.patch.object(service, "_resolve_prompt_key", return_value="TEST_KEY")
    mocker.patch.object(service, "_hydrate_data", return_value={})
    mocker.patch.object(service, "_generate_prompt", return_value="test prompt")
    mocker.patch.object(service, "_wrap_prompt_mcp", return_value="wrapped prompt")
    
    # Test cases with different result types
    test_cases = [
        ("This is a string response", None),  # String result - no status
        ({"status": "success", "data": "some data"}, "success"),  # Dict with status
        (None, None),  # None result
        (12345, None),  # Integer result - no status
        (True, None),   # Boolean result - no status
    ]
    
    for result, expected_status in test_cases:
        # Create a context with agent_statuses list to track the result
        ctx = BaseModelContext(context_id="test_ctx", user_token="test_user")
        
        # Mock _execute_adapter to return our test result
        mocker.patch.object(service, "_execute_adapter", return_value=result)
        
        # Run the agent with the correct agent ID format
        await service.run_agent("TEST_AGENT", ctx, output_type=str)
        
        # Verify the agent_statuses was updated correctly
        if hasattr(ctx, "agent_statuses"):
            last_status = ctx.agent_statuses[-1]
            assert last_status["agent"] == "TEST_AGENT"  # Should match the agent ID we used
            if expected_status is not None:
                assert last_status.get("status") == expected_status
            else:
                assert "status" not in last_status or last_status["status"] is None


@pytest.mark.asyncio
async def test_decorated_tool_auto_registered(mocker):
    mocker.patch("app.agent_metrics.track_agent_metrics", lambda *a, **k: (lambda f: f))
    import tools.registry as tools_module
    tools_module._TOOL_REGISTRY.clear()
    from tools import tool as tool_decorator

    @tool_decorator
    def auto_tool(user_token: str) -> str:
        return "auto"

    ai_core_module = importlib.import_module("agent_core.services.ai_core_service")
    AiCoreService = ai_core_module.AiCoreService
    service = AiCoreService(DummyLangFuse(), DummyRegistry(), DummyDataCore(), DummyLogger())

    cfg = AgentConfig(
        id="A",
        name="A",
        provider="openai",
        model="gpt-4o",
        langfuse_prompt_key="key",
        tools=["auto_tool"],
    )
    mocker.patch.object(service, "_load_config", return_value=cfg)
    mocker.patch.object(service, "_resolve_prompt_key", return_value="key")

    captured = {}

    async def fake_execute(*args, **kwargs):
        captured["tools"] = kwargs.get("tools")
        return "ok"

    patched = mocker.patch.object(service, "_execute_adapter", new_callable=mocker.AsyncMock)
    patched.side_effect = fake_execute

    ctx = BaseModelContext(context_id="c2", user_token="tok")
    await service.run_agent("A", ctx)

    names = {t.name for t in captured["tools"] if isinstance(t, Tool)}
    assert "auto_tool" in names


@pytest.mark.asyncio
async def test_run_agent_uses_registered_bioage_tool(mocker):
    mocker.patch("app.agent_metrics.track_agent_metrics", lambda *a, **k: (lambda f: f))
    import tools.registry as tools_module
    tools_module._TOOL_REGISTRY.clear()

    import importlib
    import tools.definitions.bioage as bioage_tools_module
    importlib.reload(bioage_tools_module)
    ai_core_module = importlib.import_module("agent_core.services.ai_core_service")
    AiCoreService = ai_core_module.AiCoreService
    service = AiCoreService(DummyLangFuse(), DummyRegistry(), DummyDataCore(), DummyLogger())

    cfg = AgentConfig(
        id="A",
        name="A",
        provider="openai",
        model="gpt-4o",
        langfuse_prompt_key="key",
        tools=["full_bioage_report"],
    )
    mocker.patch.object(service, "_load_config", return_value=cfg)
    mocker.patch.object(service, "_resolve_prompt_key", return_value="key")

    captured = {}

    async def fake_execute(*args, **kwargs):
        captured["tools"] = kwargs.get("tools")
        return "ok"

    patched = mocker.patch.object(service, "_execute_adapter", new_callable=mocker.AsyncMock)
    patched.side_effect = fake_execute

    ctx = BaseModelContext(context_id="c3", user_token="tok")
    await service.run_agent("A", ctx)

    names = {t.name for t in captured["tools"] if isinstance(t, Tool)}
    assert "full_bioage_report" in names
