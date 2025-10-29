from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from agents.agent import Agent
from agents.exceptions import OutputGuardrailTripwireTriggered
from agents.guardrail import GuardrailFunctionOutput, OutputGuardrailResult

from agent_core.guardrails import (
    NO_VIDEO_WITHOUT_RECOMMENDATION_GUARDRAIL,
    REFERENCED_VIDEO_DOES_NOT_EXIST_GUARDRAIL_MESSAGE,
    SUMMARIZER_DUPLICATE_LINK_GUARDRAIL_MESSAGE,
    SUMMARIZER_NO_DUPLICATE_LINK_GUARDRAIL,
)
from agent_core.services.model_context import BaseModelContext
from orchestrator.orchestrators.agent_models import SummarizerAgentResponse
from orchestrator.orchestrators.summarizer_agent import SummarizerAgent
from tools.definitions.common import recommend_videos


@pytest.mark.asyncio
async def test_summarizer_agent_sets_recommend_videos_tool_non_prod(mocker):
    agent_response = SummarizerAgentResponse(
        status="ok",
        message="summary",
        message_references_a_video=False,
    )
    run_agent_mock = AsyncMock(return_value=agent_response)
    ai = SimpleNamespace(run_agent=run_agent_mock)
    agent = SummarizerAgent(ai)
    context = BaseModelContext(
        context_id="ctx",
        data={"formatted_responses": [{"agent": "support_agent"}]},
        user_type="alpha",
    )

    mocker.patch("utils.slack_util.send_slack_askdigbi_log")

    await agent.ask(context)

    kwargs = run_agent_mock.await_args.kwargs
    assert "hooks" not in kwargs
    assert kwargs.get("tools") == [recommend_videos]
    assert kwargs.get("tool_choice") == "recommend_videos"
    assert kwargs.get("output_type") is SummarizerAgentResponse
    assert kwargs.get("output_guardrails") == [
        NO_VIDEO_WITHOUT_RECOMMENDATION_GUARDRAIL,
        SUMMARIZER_NO_DUPLICATE_LINK_GUARDRAIL,
    ]


@pytest.mark.asyncio
async def test_summarizer_agent_preserves_formatted_responses(mocker):
    formatted = [
        {"agent": "support_agent", "status": "completed", "message": "Stay active daily."},
        {"agent": "nutrition_agent", "status": "completed", "message": "Eat more fiber."},
    ]
    run_agent_mock = AsyncMock(
        return_value=SummarizerAgentResponse(
            status="ok",
            message="summary",
            message_references_a_video=True,
        )
    )
    ai = SimpleNamespace(run_agent=run_agent_mock)
    agent = SummarizerAgent(ai)
    context = BaseModelContext(
        context_id="ctx",
        data={"formatted_responses": formatted.copy()},
        user_type="alpha",
    )

    mocker.patch("utils.slack_util.send_slack_askdigbi_log")

    await agent.ask(context)

    kwargs = run_agent_mock.await_args.kwargs
    assert kwargs.get("tools") == [recommend_videos]
    assert kwargs.get("tool_choice") == "recommend_videos"
    assert context.data.get("formatted_responses") == formatted


@pytest.mark.asyncio
async def test_summarizer_agent_skips_video_tool_when_support_missing(mocker):
    agent_response = SummarizerAgentResponse(
        status="ok",
        message="summary",
        message_references_a_video=False,
    )
    run_agent_mock = AsyncMock(return_value=agent_response)
    ai = SimpleNamespace(run_agent=run_agent_mock)
    agent = SummarizerAgent(ai)
    context = BaseModelContext(
        context_id="ctx",
        data={"formatted_responses": [{"agent": "nutrition_agent"}]},
        user_type="alpha",
    )

    mocker.patch("utils.slack_util.send_slack_askdigbi_log")

    await agent.ask(context)

    kwargs = run_agent_mock.await_args.kwargs
    assert kwargs.get("tools") is None
    assert kwargs.get("tool_choice") is None


@pytest.mark.asyncio
async def test_summarizer_agent_returns_direct_result_when_video_feature_disabled(mocker):
    agent_response = SummarizerAgentResponse(
        status="ok",
        message="summary",
        message_references_a_video=False,
    )
    run_agent_mock = AsyncMock(return_value=agent_response)
    ai = SimpleNamespace(run_agent=run_agent_mock)
    agent = SummarizerAgent(ai)
    context = BaseModelContext(context_id="ctx", data={}, user_type="production")

    mocker.patch("utils.slack_util.send_slack_askdigbi_log")

    result = await agent.ask(context)

    kwargs = run_agent_mock.await_args.kwargs
    assert kwargs == {}
    assert result is agent_response


@pytest.mark.asyncio
async def test_summarizer_agent_retries_after_guardrail(mocker):
    initial_output = SummarizerAgentResponse(
        status="ok",
        message="Watch this video",
        message_references_a_video=True,
    )
    retry_output = SummarizerAgentResponse(
        status="ok",
        message="No video mentioned",
        message_references_a_video=False,
    )

    guardrail_output = GuardrailFunctionOutput(
        output_info=REFERENCED_VIDEO_DOES_NOT_EXIST_GUARDRAIL_MESSAGE,
        tripwire_triggered=True,
    )
    guardrail_exception = OutputGuardrailTripwireTriggered(
        OutputGuardrailResult(
            guardrail=NO_VIDEO_WITHOUT_RECOMMENDATION_GUARDRAIL,
            agent=Agent(name="summarizer"),
            agent_output=initial_output,
            output=guardrail_output,
        )
    )

    run_agent_mock = AsyncMock(side_effect=[guardrail_exception, retry_output])
    ai = SimpleNamespace(run_agent=run_agent_mock)
    agent = SummarizerAgent(ai)
    context = BaseModelContext(
        context_id="ctx",
        data={"formatted_responses": [{"agent": "support_agent", "status": "completed"}]},
        user_type="alpha",
    )

    mocker.patch("utils.slack_util.send_slack_askdigbi_log")

    result = await agent.ask(context)

    assert result["status"] == retry_output.status
    assert result["message"] == retry_output.message
    assert result["meta"] == retry_output.meta.model_dump()
    assert "message_references_a_video" not in result
    assert run_agent_mock.await_count == 2
    retry_kwargs = run_agent_mock.await_args_list[1].kwargs
    assert retry_kwargs["additional_messages"] == [
        {"role": "assistant", "content": initial_output.message},
        {
            "role": "system",
            "content": "Video guidance: The recommendation failed. Remove any video references or actions before responding.",
        },
    ]
    assert "tools" not in retry_kwargs
    assert "tool_choice" not in retry_kwargs


@pytest.mark.asyncio
async def test_summarizer_agent_retries_after_duplicate_link_guardrail(mocker):
    initial_output = SummarizerAgentResponse(
        status="ok",
        message="Watch this video https://videos.example.com/intro",
        message_references_a_video=False,
    )
    retry_output = SummarizerAgentResponse(
        status="ok",
        message="Summary without links",
        message_references_a_video=False,
    )

    guardrail_output = GuardrailFunctionOutput(
        output_info=SUMMARIZER_DUPLICATE_LINK_GUARDRAIL_MESSAGE,
        tripwire_triggered=True,
    )
    guardrail_exception = OutputGuardrailTripwireTriggered(
        OutputGuardrailResult(
            guardrail=SUMMARIZER_NO_DUPLICATE_LINK_GUARDRAIL,
            agent=Agent(name="summarizer"),
            agent_output=initial_output,
            output=guardrail_output,
        )
    )

    run_agent_mock = AsyncMock(side_effect=[guardrail_exception, retry_output])
    ai = SimpleNamespace(run_agent=run_agent_mock)
    agent = SummarizerAgent(ai)
    context = BaseModelContext(
        context_id="ctx",
        data={"formatted_responses": [{"agent": "support_agent", "status": "completed"}]},
        user_type="alpha",
    )

    mocker.patch("utils.slack_util.send_slack_askdigbi_log")

    result = await agent.ask(context)

    assert result["status"] == retry_output.status
    assert result["message"] == retry_output.message
    assert result["meta"] == retry_output.meta.model_dump()
    assert run_agent_mock.await_count == 2

    retry_kwargs = run_agent_mock.await_args_list[1].kwargs
    assert retry_kwargs["additional_messages"] == [
        {"role": "assistant", "content": initial_output.message},
        {
            "role": "system",
            "content": "Hyperlink guidance: Remove hyperlinks already provided via the video recommendation component.",
        },
    ]


@pytest.mark.asyncio
async def test_summarizer_agent_returns_error_after_guardrail_twice(mocker):
    initial_output = SummarizerAgentResponse(
        status="ok",
        message="Watch this video",
        message_references_a_video=True,
    )
    guardrail_output = GuardrailFunctionOutput(
        output_info=REFERENCED_VIDEO_DOES_NOT_EXIST_GUARDRAIL_MESSAGE,
        tripwire_triggered=True,
    )
    guardrail_exception = OutputGuardrailTripwireTriggered(
        OutputGuardrailResult(
            guardrail=NO_VIDEO_WITHOUT_RECOMMENDATION_GUARDRAIL,
            agent=Agent(name="summarizer"),
            agent_output=initial_output,
            output=guardrail_output,
        )
    )

    run_agent_mock = AsyncMock(side_effect=[guardrail_exception, guardrail_exception])
    ai = SimpleNamespace(run_agent=run_agent_mock)
    agent = SummarizerAgent(ai)
    context = BaseModelContext(
        context_id="ctx",
        data={"formatted_responses": [{"agent": "support_agent", "status": "completed"}]},
        user_type="alpha",
    )

    mocker.patch("utils.slack_util.send_slack_askdigbi_log")

    result = await agent.ask(context)

    assert result["status"] == "error"
    assert result["message"] == REFERENCED_VIDEO_DOES_NOT_EXIST_GUARDRAIL_MESSAGE
    assert result["meta"] == {}
    assert "message_references_a_video" not in result
    assert run_agent_mock.await_count == 2
    retry_kwargs = run_agent_mock.await_args_list[1].kwargs
    assert retry_kwargs["additional_messages"] == [
        {"role": "assistant", "content": initial_output.message},
        {
            "role": "system",
            "content": "Video guidance: The recommendation failed. Remove any video references or actions before responding.",
        },
    ]
