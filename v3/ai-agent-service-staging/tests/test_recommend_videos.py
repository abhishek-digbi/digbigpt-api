from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from agents.exceptions import InputGuardrailTripwireTriggered
from agents.guardrail import GuardrailFunctionOutput, InputGuardrailResult
from orchestrator.orchestrators.agent_models import (
    InteractiveComponent,
    VideoRecommendationResult,
)
from tools.definitions.common import recommend_videos


@pytest.mark.asyncio
async def test_recommend_videos_attaches_video_guardrail():
    component = InteractiveComponent(
        id="video-1",
        display_text="Watch",
        screen_name="VideoPopUpScreen",
        type="ROUTE",
        data=[],
    )

    explanation = "Matched workout intent"
    ai_runner = AsyncMock(
        return_value=VideoRecommendationResult(video=component, explanation=explanation)
    )
    model_ctx = SimpleNamespace(
        data={"video_agent_input": "show me workouts"},
        ai_runner=ai_runner,
        query="Original question",
    )
    ctx = SimpleNamespace(context=model_ctx)

    result = await recommend_videos.func(ctx)

    assert isinstance(result, VideoRecommendationResult)
    assert result.video == component
    assert result.explanation == explanation
    assert ai_runner.await_count == 1
    call_args = ai_runner.await_args
    assert call_args.args == ("VIDEO_RECOMMENDER_AGENT", model_ctx)
    kwargs = call_args.kwargs
    assert kwargs.get("output_type") is VideoRecommendationResult
    assert kwargs.get("tool_choice") == "file_search"
    assert kwargs.get("strict_json_schema") is True
    assert "input_guardrails" not in kwargs or kwargs["input_guardrails"] in (None, [])
    assert kwargs.get("output_guardrails") in (None, [])
    assert model_ctx.data == {"video_agent_input": "show me workouts"}


@pytest.mark.asyncio
async def test_recommend_videos_returns_none_when_guardrail_triggers():
    guardrail_output = GuardrailFunctionOutput(output_info="blocked", tripwire_triggered=True)
    guardrail_result = InputGuardrailResult(guardrail=None, output=guardrail_output)
    guardrail_exception = InputGuardrailTripwireTriggered(guardrail_result)

    ai_runner = AsyncMock(side_effect=guardrail_exception)
    model_ctx = SimpleNamespace(
        data={"video_agent_input": "Tell me about the SmartMeter scale setup"},
        ai_runner=ai_runner,
        query="Original question",
    )
    ctx = SimpleNamespace(context=model_ctx)

    result = await recommend_videos.func(ctx)

    assert result is None
    assert ai_runner.await_count == 1
    call_args = ai_runner.await_args
    assert call_args.args == ("VIDEO_RECOMMENDER_AGENT", model_ctx)
    kwargs = call_args.kwargs
    assert "input_guardrails" not in kwargs or kwargs["input_guardrails"] in (None, [])
    assert kwargs.get("output_guardrails") in (None, [])
    assert kwargs.get("output_type") is VideoRecommendationResult
    assert model_ctx.data == {
        "video_agent_input": "Tell me about the SmartMeter scale setup"
    }


@pytest.mark.asyncio
async def test_recommend_videos_handles_general_exception():
    async def failing_runner(*args, **kwargs):
        raise RuntimeError("model error")

    model_ctx = SimpleNamespace(
        data={"video_agent_input": "lower back stretches"},
        ai_runner=failing_runner,
        query="Original question",
    )
    ctx = SimpleNamespace(context=model_ctx)

    result = await recommend_videos.func(ctx)

    assert result is None
    assert model_ctx.data == {"video_agent_input": "lower back stretches"}


@pytest.mark.asyncio
async def test_recommend_videos_backfills_query_when_context_missing():
    component = InteractiveComponent(
        id="video-1",
        display_text="Watch",
        screen_name="VideoPopUpScreen",
        type="ROUTE",
        data=[],
    )

    ai_runner = AsyncMock(
        return_value=VideoRecommendationResult(video=component, explanation=None)
    )
    model_ctx = SimpleNamespace(
        data={"video_agent_input": "  show me workouts   "},
        ai_runner=ai_runner,
        query=None,
    )
    ctx = SimpleNamespace(context=model_ctx)

    result = await recommend_videos.func(ctx)

    assert isinstance(result, VideoRecommendationResult)
    assert result.video == component
    assert result.explanation is None
    assert ai_runner.await_count == 1
    call_args = ai_runner.await_args
    assert call_args.args == ("VIDEO_RECOMMENDER_AGENT", model_ctx)
    kwargs = call_args.kwargs
    assert kwargs.get("output_guardrails") in (None, [])
    assert kwargs.get("output_type") is VideoRecommendationResult
    assert kwargs.get("tool_choice") == "file_search"
    assert kwargs.get("strict_json_schema") is True
    assert model_ctx.query is None
    assert model_ctx.data == {"video_agent_input": "  show me workouts   "}
