import inspect
import pytest

from agent_core.services.adapters.openai_service import OpenAIService
from agent_core.services.model_context import BaseModelContext
import tools.registry as tools_module
from tools import tool, Tool


@pytest.mark.asyncio
async def test_tool_invocation_through_openai_service(mocker):
    service = OpenAIService(api_key="test")

    # Avoid converting Tool -> OpenAI FunctionTool for this test
    mocker.patch(
        "agent_core.services.adapters.openai_service.to_openai_function_tool",
        lambda t: t,
    )

    class DummyAgent:
        def __init__(self, *, tools=None, **kwargs):
            self.tools = tools or []

    mocker.patch(
        "agent_core.services.adapters.openai_service.Agent",
        DummyAgent,
    )
    mocker.patch(
        "agent_core.services.adapters.openai_service.ModelSettings",
        lambda *a, **kw: None,
    )
    mocker.patch(
        "agent_core.services.adapters.openai_service.AgentOutputSchema",
        lambda *a, **kw: None,
    )

    async def fake_run(agent, payload, context, max_turns=20, hooks=None):
        tool_obj = agent.tools[0]
        func = tool_obj.func if isinstance(tool_obj, Tool) else tool_obj
        if inspect.iscoroutinefunction(func):
            result = await func("Bob")
        else:
            result = func("Bob")
        return type("Res", (), {"final_output": result, "new_items": []})()

    mocker.patch(
        "agent_core.services.adapters.openai_service.Runner.run",
        side_effect=fake_run,
    )

    tools_module._TOOL_REGISTRY.clear()

    @tool
    def greet(name: str) -> str:
        return f"Hello {name}!"

    result = await service.run(prompt="hi", ctx=BaseModelContext(context_id=""), agent_id="A", tools=[greet])
    assert result == "Hello Bob!"

@pytest.mark.asyncio
async def test_async_tool_invocation_through_openai_service(mocker):
    service = OpenAIService(api_key="test")
    mocker.patch(
        "agent_core.services.adapters.openai_service.to_openai_function_tool",
        lambda t: t,
    )

    class DummyAgent:
        def __init__(self, *, tools=None, **kwargs):
            self.tools = tools or []

    mocker.patch(
        "agent_core.services.adapters.openai_service.Agent",
        DummyAgent,
    )
    mocker.patch(
        "agent_core.services.adapters.openai_service.ModelSettings",
        lambda *a, **kw: None,
    )
    mocker.patch(
        "agent_core.services.adapters.openai_service.AgentOutputSchema",
        lambda *a, **kw: None,
    )

    async def fake_run(agent, payload, context, max_turns=20, hooks=None):
        tool_obj = agent.tools[0]
        func = tool_obj.func if isinstance(tool_obj, Tool) else tool_obj
        if inspect.iscoroutinefunction(func):
            result = await func("Bob")
        else:
            result = func("Bob")
        return type("Res", (), {"final_output": result, "new_items": []})()

    mocker.patch(
        "agent_core.services.adapters.openai_service.Runner.run",
        side_effect=fake_run,
    )

    tools_module._TOOL_REGISTRY.clear()

    @tool
    async def greet(name: str) -> str:
        return f"Hello {name}!"

    result = await service.run(prompt="hi", ctx=BaseModelContext(context_id=""), agent_id="A", tools=[greet])
    assert result == "Hello Bob!"


@pytest.mark.asyncio
async def test_file_search_filters_passed(mocker):
    service = OpenAIService(api_key="test")
    mocker.patch(
        "agent_core.services.adapters.openai_service.to_openai_function_tool",
        lambda t: t,
    )

    captured = {}

    class DummyAgent:
        def __init__(self, *, tools=None, **kwargs):
            captured["tools"] = tools or []

    mocker.patch(
        "agent_core.services.adapters.openai_service.Agent",
        DummyAgent,
    )
    mocker.patch(
        "agent_core.services.adapters.openai_service.ModelSettings",
        lambda *a, **kw: None,
    )
    mocker.patch(
        "agent_core.services.adapters.openai_service.AgentOutputSchema",
        lambda *a, **kw: None,
    )

    async def fake_run(agent, payload, context, max_turns=20, hooks=None):
        return type("Res", (), {"final_output": "ok", "new_items": []})()

    mocker.patch(
        "agent_core.services.adapters.openai_service.Runner.run",
        side_effect=fake_run,
    )

    filters = {"team": "eng"}
    await service.run(
        prompt="hi",
        ctx=BaseModelContext(context_id=""),
        agent_id="A",
        vector_store_ids=["v1"],
        file_filters=filters,
    )

    fs_tool = [t for t in captured["tools"] if getattr(t, "name", None) == "file_search"][0]
    assert fs_tool.filters == filters


@pytest.mark.asyncio
async def test_file_search_usage_recorded_in_context(mocker):
    service = OpenAIService(api_key="test")
    mocker.patch(
        "agent_core.services.adapters.openai_service.to_openai_function_tool",
        lambda t: t,
    )

    class DummyAgent:
        def __init__(self, *, tools=None, **kwargs):
            self.tools = tools or []

    mocker.patch(
        "agent_core.services.adapters.openai_service.Agent",
        DummyAgent,
    )
    mocker.patch(
        "agent_core.services.adapters.openai_service.ModelSettings",
        lambda *a, **kw: None,
    )
    mocker.patch(
        "agent_core.services.adapters.openai_service.AgentOutputSchema",
        lambda *a, **kw: None,
    )

    fake_result = type(
        "Res",
        (),
        {
            "final_output": "ok",
            "to_input_list": lambda self: [
                {"role": "assistant", "content": "Response"},
                {"type": "file_search_call", "queries": ["orientation video"], "results": None},
            ],
        },
    )()

    async def fake_run(agent, payload, context, max_turns=20, hooks=None):
        return fake_result

    mocker.patch(
        "agent_core.services.adapters.openai_service.Runner.run",
        side_effect=fake_run,
    )

    ctx = BaseModelContext(context_id="", data={})
    await service.run(
        prompt="hi",
        ctx=ctx,
        agent_id="A",
        vector_store_ids=["v1"],
    )

    assert OpenAIService.did_run_use_file_search(ctx, "A")
    messages = OpenAIService.get_run_input_list(ctx, "A")
    assert messages == [
        {"role": "assistant", "content": "Response"},
        {"type": "file_search_call", "queries": ["orientation video"], "results": None},
    ]
    assert "result_new_items" not in ctx.data


@pytest.mark.asyncio
async def test_file_search_usage_absent_sets_flags(mocker):
    service = OpenAIService(api_key="test")

    class DummyAgent:
        def __init__(self, *, tools=None, **kwargs):
            self.tools = tools or []

    mocker.patch(
        "agent_core.services.adapters.openai_service.Agent",
        DummyAgent,
    )
    mocker.patch(
        "agent_core.services.adapters.openai_service.ModelSettings",
        lambda *a, **kw: None,
    )
    mocker.patch(
        "agent_core.services.adapters.openai_service.AgentOutputSchema",
        lambda *a, **kw: None,
    )
    mocker.patch(
        "agent_core.services.adapters.openai_service.to_openai_function_tool",
        lambda t: t,
    )

    empty_result = type(
        "Res",
        (),
        {
            "final_output": "ok",
            "to_input_list": lambda self: [
                {"role": "assistant", "content": "Plain response"}
            ],
        },
    )()

    async def fake_run(agent, payload, context, max_turns=20, hooks=None):
        return empty_result

    mocker.patch(
        "agent_core.services.adapters.openai_service.Runner.run",
        side_effect=fake_run,
    )

    ctx = BaseModelContext(context_id="", data={})

    await service.run(
        prompt="hi",
        ctx=ctx,
        agent_id="A",
    )

    assert not OpenAIService.did_run_use_file_search(ctx, "A")
    messages = OpenAIService.get_run_input_list(ctx, "A")
    assert messages == [{"role": "assistant", "content": "Plain response"}]
    assert "result_new_items" not in ctx.data


def test_build_agent_payload_preserves_base_messages_on_retry():
    payload = OpenAIService._build_agent_payload(
        "summarize please",
        image_url=None,
        additional_messages=[{"role": "system", "content": "Retry with guidance"}],
    )

    assert payload[0] == {"role": "user", "content": "summarize please"}
    assert payload[1] == {"role": "system", "content": "Retry with guidance"}


def test_build_agent_payload_v2_appends_retry_messages_without_dropping_context():
    context = BaseModelContext(
        context_id="ctx",
        query="latest user question",
        conversation_history={
            "recent_messages": [
                {"sender": "assistant", "content": "previous assistant reply", "timestamp": 1},
                {"sender": "user", "content": "previous user question", "timestamp": 2},
            ]
        },
    )

    additional = [
        {"role": "assistant", "content": "guardrail retry response"},
        {"role": "system", "content": "Remove video references"},
    ]

    service = OpenAIService(api_key="dummy")
    payload = service._build_agent_payload_v2(
        prompt="base system prompt",
        image_url=None,
        ctx=context,
        additional_messages=additional,
    )

    assert payload[0] == {"role": "system", "content": "base system prompt"}
    assert payload[1] == {"role": "assistant", "content": "previous assistant reply"}
    assert payload[2] == {"role": "user", "content": "latest user question"}
    assert payload[3:] == additional
    assert all(entry.get("content") != "previous user question" for entry in payload)
