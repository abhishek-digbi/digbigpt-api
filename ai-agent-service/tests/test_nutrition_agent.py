import sys
import types
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from agent_core.services.adapters.openai_service import OpenAIService


def _set_run_data(ctx_obj, agent_name, messages):
    run_key = f"{ctx_obj.context_id}::{getattr(ctx_obj, 'query_id', None) or 'unknown_query'}"
    run_data = ctx_obj.data.setdefault("run_data", {})
    agent_runs = run_data.setdefault(agent_name, {})
    agent_runs[run_key] = {
        "agent_id": agent_name,
        "context_id": ctx_obj.context_id,
        "query_id": getattr(ctx_obj, "query_id", None),
        "input_list": messages,
    }
    run_data[agent_name] = agent_runs
    ctx_obj.data["run_data"] = run_data

if "app" not in sys.modules:
    sys.modules["app"] = types.ModuleType("app")

app_module = sys.modules["app"]

metrics_module = types.ModuleType("app.metrics")


class _DummyCounter:
    def add(self, *args, **kwargs):
        return None


class _DummyHistogram:
    def record(self, *args, **kwargs):
        return None


class _DummyMeter:
    def create_counter(self, *args, **kwargs):
        return _DummyCounter()

    def create_histogram(self, *args, **kwargs):
        return _DummyHistogram()


metrics_module.meter = _DummyMeter()
def _noop_track_execution(*args, **kwargs):
    def _decorator(func):
        return func

    return _decorator


metrics_module.track_execution = _noop_track_execution
sys.modules["app.metrics"] = metrics_module
app_module.metrics = metrics_module

agent_metrics_module = types.ModuleType("app.agent_metrics")


def _noop_decorator(*args, **kwargs):
    def _decorator(func):
        return func

    return _decorator


agent_metrics_module.track_agent_metrics = _noop_decorator
sys.modules["app.agent_metrics"] = agent_metrics_module
app_module.agent_metrics = agent_metrics_module

from agent_core.services.model_context import BaseModelContext


@pytest.fixture(autouse=True)
def _set_meal_rating_assistant_env(monkeypatch):
    """Ensure NutritionAgent sees a meal rating assistant id during tests."""
    monkeypatch.setenv("MEAL_RATING_ASSISTANT_ID", "test-assistant-id")

from orchestrator.orchestrators.nutrition_agent import NutritionAgent


def _set_run_data(ctx_obj, agent_name, messages):
    run_key = f"{agent_name}::{ctx_obj.context_id}"
    run_data = ctx_obj.data.setdefault("run_data", {})
    run_data.setdefault(run_key, []).append({"input_list": messages})
    ctx_obj.data["run_data"] = run_data


@pytest.fixture
def nutrition_agent_factory():
    def _make(run_agent):
        ai = SimpleNamespace(run_agent=run_agent)
        langfuse = SimpleNamespace(generate_prompt=lambda *args, **kwargs: "prompt")
        sensitivity = SimpleNamespace()
        personalization = SimpleNamespace()
        tool_service = SimpleNamespace()
        db_client = SimpleNamespace()
        return NutritionAgent(ai, langfuse, sensitivity, personalization, tool_service, db_client)

    return _make


@pytest.mark.asyncio
async def test_nutrition_agent_retries_when_file_search_missing(nutrition_agent_factory):
    async def side_effect(*args, **kwargs):
        call_index = side_effect.calls
        side_effect.calls += 1
        ctx = kwargs.get("ctx")

        if call_index == 0:
            if ctx:
                _set_run_data(
                    ctx,
                    "ASK_DIGBI_NUTRITION_AGENT",
                    [{"role": "assistant", "content": "Initial draft"}],
                )
            return "initial"
        elif call_index == 1:
            if ctx:
                _set_run_data(
                    ctx,
                    "ASK_DIGBI_NUTRITION_AGENT",
                    [
                        {"role": "assistant", "content": "Final"},
                        {"type": "file_search_call", "queries": ["kb"]},
                    ],
                )
            return "final"
        raise AssertionError("run_agent called unexpectedly")

    side_effect.calls = 0
    run_agent_mock = AsyncMock(side_effect=side_effect)
    agent = nutrition_agent_factory(run_agent_mock)
    ctx = BaseModelContext(context_id="ctx", data={}, user_type="ALPHA", user_token="u", query_id="qid")

    result = await agent.ask(ctx)

    assert result == "final"
    assert run_agent_mock.await_count == 2
    first_kwargs = run_agent_mock.await_args_list[0].kwargs
    second_kwargs = run_agent_mock.await_args_list[1].kwargs
    assert second_kwargs["input_messages"] == [
        {"role": "assistant", "content": "Initial draft"},
        {
            "role": "system",
            "content": (
                "Before finalizing your answer, perform a knowledge-base file search "
                "using the file_search tool so your response reflects the latest KB context."
            ),
        },
    ]
    assert OpenAIService.did_run_use_file_search(ctx, "ASK_DIGBI_NUTRITION_AGENT")


@pytest.mark.asyncio
async def test_nutrition_agent_no_retry_when_file_search_used(nutrition_agent_factory):
    async def side_effect(*args, **kwargs):
        ctx = kwargs.get("ctx")
        if ctx:
            _set_run_data(
                ctx,
                "ASK_DIGBI_NUTRITION_AGENT",
                [
                    {"role": "assistant", "content": "done"},
                    {"type": "file_search_call", "queries": ["kb"]},
                ],
            )
        return "done"

    run_agent_mock = AsyncMock(side_effect=side_effect)
    agent = nutrition_agent_factory(run_agent_mock)
    ctx = BaseModelContext(context_id="ctx", data={}, user_type="beta", user_token="u", query_id="qid")

    result = await agent.ask(ctx)

    assert result == "done"
    run_agent_mock.assert_awaited_once()
    kwargs = run_agent_mock.await_args.kwargs
    assert "additional_messages" not in kwargs
    assert OpenAIService.did_run_use_file_search(ctx, "ASK_DIGBI_NUTRITION_AGENT")
