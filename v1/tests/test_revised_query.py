import asyncio
import json
import pytest
import sys
import types

from orchestrator.orchestrators.agent_models import Action, AgentRequest
from agent_core.services.model_context import BaseModelContext


class DummyAgent:
    def __init__(self):
        self.received_queries = []

    async def ask(self, ctx):
        # Yield control to allow concurrent tasks to run and potentially mutate
        # shared state if not properly isolated.
        await asyncio.sleep(0)
        self.received_queries.append(ctx.data.get("user_query"))
        return {"status": "ok", "message": "done"}


def setup_agent(monkeypatch):
    module = types.ModuleType("agent_metrics")

    def dummy_decorator(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

    module.track_agent_metrics = dummy_decorator
    app_module = types.ModuleType("app")
    app_module.agent_metrics = module
    monkeypatch.setitem(sys.modules, "app", app_module)
    monkeypatch.setitem(sys.modules, "app.agent_metrics", module)
    from orchestrator.orchestrators.ask_digbi_agent import AskDigbiAgent

    dummy = DummyAgent()
    agent = AskDigbiAgent(
        aicore=None,
        health_insights_agent=dummy,
        nutrition_agent=dummy,
        personalization_agent=dummy,
        support_agent=dummy,
        summarizer_agent=dummy,
        recipeAgent=dummy,
    )
    return agent, dummy


@pytest.mark.asyncio
async def test_process_action_uses_revised_query(monkeypatch):
    monkeypatch.setattr("utils.env_loader.get_ask_digbi_assistant_id", lambda: "assist")
    agent, dummy = setup_agent(monkeypatch)
    ctx = BaseModelContext(context_id="1", query="original")
    action = Action(action="call", message="", agent="health_insights_agent", revised_query="revised")
    await agent._process_action(action, ctx)
    assert dummy.received_queries == ["revised"]


@pytest.mark.asyncio
async def test_process_action_defaults_to_original_query(monkeypatch):
    monkeypatch.setattr("utils.env_loader.get_ask_digbi_assistant_id", lambda: "assist")
    agent, dummy = setup_agent(monkeypatch)
    ctx = BaseModelContext(context_id="1", query="original")
    action = Action(action="call", message="", agent="health_insights_agent")
    await agent._process_action(action, ctx)
    assert dummy.received_queries == ["original"]


@pytest.mark.asyncio
async def test_process_action_handles_concurrent_revised_queries(monkeypatch):
    """Ensure revised queries don't clobber each other when actions run concurrently."""
    monkeypatch.setattr("utils.env_loader.get_ask_digbi_assistant_id", lambda: "assist")
    agent, dummy = setup_agent(monkeypatch)
    ctx = BaseModelContext(context_id="1", query="original")
    action1 = Action(action="call", message="", agent="health_insights_agent", revised_query="rev1")
    action2 = Action(action="call", message="", agent="nutrition_agent", revised_query="rev2")

    await asyncio.gather(
        agent._process_action(action1, ctx),
        agent._process_action(action2, ctx),
    )

    assert sorted(dummy.received_queries) == ["rev1", "rev2"]


class _SummaryStub:
    async def ask(self, ctx):
        return {
            "status": "ok",
            "message": "summary",
            "meta": json.dumps({
                "actions": ["summary_action"],
                "from_summary": True,
            }),
        }


class _StringSummaryStub:
    async def ask(self, ctx):
        return "plain summary"


@pytest.mark.asyncio
async def test_handle_response_parses_string_meta(monkeypatch):
    monkeypatch.setattr("utils.env_loader.get_ask_digbi_assistant_id", lambda: "assist")
    agent, dummy = setup_agent(monkeypatch)
    agent.summarizer_agent = _SummaryStub()

    async def _fake_process_action(action, ctx):
        return {
            "status": "ok",
            "message": "done",
            "meta": json.dumps({
                "actions": ["agent_action"],
                "from_agent": True,
            }),
        }

    agent._process_action = _fake_process_action  # type: ignore[assignment]

    ctx = BaseModelContext(context_id="1", query="original")
    request = AgentRequest(actions=[Action(action="delegate", message="", agent="support_agent")], details="")

    result = await agent.handle_intent_classifier_response(request, ctx)

    assert result["message"] == "summary"
    assert result["status"] == "ok"
    assert result["meta"]["from_agent"] is True
    assert result["meta"]["from_summary"] is True
    assert result["meta"]["actions"] == ["agent_action", "summary_action"]


@pytest.mark.asyncio
async def test_handle_response_coerces_string_summary(monkeypatch):
    monkeypatch.setattr("utils.env_loader.get_ask_digbi_assistant_id", lambda: "assist")
    agent, dummy = setup_agent(monkeypatch)
    agent.summarizer_agent = _StringSummaryStub()

    async def _fake_process_action(action, ctx):
        return {
            "status": "ok",
            "message": "done",
            "meta": json.dumps({
                "actions": ["agent_action"],
                "from_agent": True,
            }),
        }

    agent._process_action = _fake_process_action  # type: ignore[assignment]

    ctx = BaseModelContext(context_id="1", query="original")
    request = AgentRequest(actions=[Action(action="delegate", message="", agent="support_agent")], details="")

    result = await agent.handle_intent_classifier_response(request, ctx)

    assert result["message"] == "plain summary"
    assert result["status"] == "completed"
    assert result["meta"]["from_agent"] is True
    assert result["meta"]["actions"] == ["agent_action"]
    assert "from_summary" not in result["meta"]
