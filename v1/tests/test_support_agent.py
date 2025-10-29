import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from agents.agent import Agent
from agents.exceptions import OutputGuardrailTripwireTriggered
from agents.guardrail import GuardrailFunctionOutput, OutputGuardrailResult

from agent_core.services.adapters.openai_service import OpenAIService
from agent_core.guardrails import (
    SUPPORT_AGENT_NO_KIT_REGISTRATION_GUARDRAIL,
    SUPPORT_AGENT_KIT_REGISTRATION_MESSAGE,
    NO_VIDEO_WITHOUT_RECOMMENDATION_GUARDRAIL,
    REFERENCED_VIDEO_DOES_NOT_EXIST_GUARDRAIL_MESSAGE,
)
from agent_core.services.model_context import BaseModelContext
from orchestrator.orchestrators.agent_models import (
    Action,
    AgentRequestV2,
    InteractiveComponent,
    Meta,
    SummarizerAgentResponse,
    SupportAgentResponse,
    VideoButton,
    VideoMeta,
)
from agent_core.models.support_intents import (
    InviteDependentIntent,
    KitRegistrationIntent,
)
from orchestrator.orchestrators.support_agent import SupportAgent


INVITE_DEPENDENT_ACTION = InteractiveComponent(
    screen_name="InviteDependent",
    type="SLIDEUP",
    icon="ask-digbi-invite-family",
    color="blue",
    display_text="Share Digbi for free!",
).model_dump()


def _normalize_meta(value):
    if isinstance(value, str):
        return json.loads(value)
    return value


def test_support_agent_response_invite_dependent_intent_defaults_false():
    response = SupportAgentResponse(status="ok", message="All set", meta=Meta())

    assert response.invite_dependent_intent is InviteDependentIntent.FALSE

@pytest.mark.asyncio
async def test_support_agent_does_not_attach_guardrail_on_primary_run():
    agent_request = AgentRequestV2(
        actions=[
            Action(
                action="respond_directly",
                agent="noop",
                message="No links here",
            )
        ],
        details="",
    )

    run_agent_mock = AsyncMock(return_value=agent_request)
    mock_ai = SimpleNamespace(run_agent=run_agent_mock)
    agent = SupportAgent(mock_ai)
    context = BaseModelContext(context_id="ctx", data={}, user_type="production")

    await agent.ask(context)

    kwargs = run_agent_mock.await_args.kwargs
    assert "output_guardrails" not in kwargs or kwargs["output_guardrails"] in (None, [])


@pytest.mark.asyncio
async def test_support_agent_runs_delegate_without_guardrails(mocker):
    agent_request = AgentRequestV2(
        actions=[Action(action="delegate", agent="mock_agent", message="")],
        details="",
    )
    first_response = SupportAgentResponse(status="ok", message="Draft", meta=Meta())
    final_response = SupportAgentResponse(status="ok", message="All good", meta=Meta())

    def _set_run_data(ctx_obj, agent_name, messages):
        run_key = f"{agent_name}::{ctx_obj.context_id}"
        run_data = ctx_obj.data.setdefault("run_data", {})
        run_data.setdefault(run_key, []).append({"input_list": messages})
        ctx_obj.data["run_data"] = run_data

    async def run_agent_side_effect(*args, **kwargs):
        call_index = run_agent_side_effect.calls
        run_agent_side_effect.calls += 1

        ctx = kwargs.get("ctx")
        if call_index == 0:
            return agent_request
        if call_index == 1:
            if ctx:
                _set_run_data(
                    ctx,
                    "mock_agent",
                    [{"role": "assistant", "content": "Draft"}],
                )
            return first_response
        if call_index == 2:
            if ctx:
                _set_run_data(
                    ctx,
                    "mock_agent",
                    [
                        {"role": "assistant", "content": "All good"},
                        {"type": "file_search_call", "queries": ["orientation"]},
                    ],
                )
            return final_response
        raise AssertionError("Unexpected additional run_agent invocation")

    run_agent_side_effect.calls = 0

    run_agent_mock = AsyncMock(side_effect=run_agent_side_effect)
    mock_ai = SimpleNamespace(run_agent=run_agent_mock)
    agent = SupportAgent(mock_ai)
    context = BaseModelContext(context_id="ctx", data={}, user_type="production")

    mocker.patch("utils.slack_util.send_slack_askdigbi_log")

    result = await agent.ask(context)

    assert result["message"] == "All good"
    assert run_agent_mock.await_count == 3

    first_call_kwargs = run_agent_mock.await_args_list[0].kwargs
    second_call_kwargs = run_agent_mock.await_args_list[1].kwargs
    third_call_kwargs = run_agent_mock.await_args_list[2].kwargs

    assert OpenAIService.did_run_use_file_search(context, "mock_agent")

    assert "input_messages" not in second_call_kwargs
    assert third_call_kwargs["input_messages"] == [
        {"role": "assistant", "content": "Draft"},
        {
            "role": "system",
            "content": (
                "Before finalizing your answer, perform a knowledge-base file search "
                "using the file_search tool so your response reflects the latest KB context."
            ),
        },
    ]


@pytest.mark.asyncio
async def test_support_agent_delegate_exception_returns_error_response(mocker):
    agent_request = AgentRequestV2(
        actions=[Action(action="delegate", agent="mock_agent", message="")],
        details="",
    )

    error = RuntimeError("delegate boom")

    run_agent_mock = AsyncMock(side_effect=[agent_request, error])
    mock_ai = SimpleNamespace(run_agent=run_agent_mock)
    agent = SupportAgent(mock_ai)
    context = BaseModelContext(context_id="ctx", data={}, user_type="production")

    mocker.patch("utils.slack_util.send_slack_askdigbi_log")

    result = await agent.ask(context)

    assert result["status"] == "error"
    assert "delegate boom" in result["message"]
    assert _normalize_meta(result["meta"]) == {"actions": []}
    assert run_agent_mock.await_count == 2


@pytest.mark.asyncio
async def test_support_agent_primary_run_exception_returns_string():
    guardrail_exception = OutputGuardrailTripwireTriggered(
        OutputGuardrailResult(
            guardrail=SUPPORT_AGENT_NO_KIT_REGISTRATION_GUARDRAIL,
            agent=Agent(name="support"),
            agent_output=None,
            output=GuardrailFunctionOutput(output_info=None, tripwire_triggered=True),
        )
    )

    mock_ai = SimpleNamespace(run_agent=AsyncMock(side_effect=guardrail_exception))
    agent = SupportAgent(mock_ai)
    context = BaseModelContext(context_id="ctx", data={}, user_type="production")

    result = await agent.ask(context)

    assert result == "Support agent erred out"
    mock_ai.run_agent.assert_awaited_once()


def test_openai_service_attaches_support_guardrail():
    guardrail = SUPPORT_AGENT_NO_KIT_REGISTRATION_GUARDRAIL
    input_guardrail = object()

    agent = OpenAIService._create_agent(
        agent_id="SUPPORT_AGENT",
        instructions=None,
        model="gpt-4o",
        output_type=AgentRequestV2,
        vector_store_ids=None,
        strict_json_schema=True,
        temperature=None,
        top_p=None,
        tool_choice=None,
        tools=None,
        file_filters=None,
        hooks=None,
        output_guardrails=[guardrail],
        input_guardrails=[input_guardrail],
    )

    assert agent.output_guardrails == [guardrail]
    assert agent.input_guardrails == [input_guardrail]


def test_support_agent_no_video_guardrail_allows_with_recommendation():
    model_ctx = SimpleNamespace(
        data={
            "video_agent_attempted": True,
            "recommended_video": {"id": "vid-123"},
        }
    )
    guardrail_context = SimpleNamespace(context=model_ctx)
    agent_output = SummarizerAgentResponse(
        status="ok",
        message="Here is a helpful video for you.",
        message_references_a_video=False,
    )

    result = NO_VIDEO_WITHOUT_RECOMMENDATION_GUARDRAIL.guardrail_function(
        guardrail_context,
        Agent(name="support"),
        agent_output,
    )

    assert result.tripwire_triggered is False
    assert result.output_info is None


def test_support_agent_no_video_guardrail_triggers_when_flag_true_without_actions():
    model_ctx = SimpleNamespace(
        data={
            "video_agent_attempted": True,
            "recommended_video": None,
        }
    )
    guardrail_context = SimpleNamespace(context=model_ctx)
    agent_output = SummarizerAgentResponse(
        status="ok",
        message="Here is a helpful video for you.",
        message_references_a_video=True,
    )

    result = NO_VIDEO_WITHOUT_RECOMMENDATION_GUARDRAIL.guardrail_function(
        guardrail_context,
        Agent(name="support"),
        agent_output,
    )

    assert result.tripwire_triggered is True
    assert result.output_info == REFERENCED_VIDEO_DOES_NOT_EXIST_GUARDRAIL_MESSAGE


def test_support_agent_no_video_guardrail_triggers_on_video_message():
    model_ctx = SimpleNamespace(
        data={
            "video_agent_attempted": True,
            "recommended_video": None,
        }
    )
    guardrail_context = SimpleNamespace(context=model_ctx)
    agent_output = SummarizerAgentResponse(
        status="ok",
        message="Please watch this video to learn more.",
        message_references_a_video=True,
    )

    result = NO_VIDEO_WITHOUT_RECOMMENDATION_GUARDRAIL.guardrail_function(
        guardrail_context,
        Agent(name="support"),
        agent_output,
    )

    assert result.tripwire_triggered is True
    assert result.output_info == REFERENCED_VIDEO_DOES_NOT_EXIST_GUARDRAIL_MESSAGE


def test_support_agent_no_video_guardrail_triggers_on_video_action():
    model_ctx = SimpleNamespace(
        data={
            "video_agent_attempted": True,
            "recommended_video": None,
        }
    )
    guardrail_context = SimpleNamespace(context=model_ctx)
    video_button = VideoButton(
        id="vid-1",
        display_text="Watch",
        screen_name="VideoPopUpScreen",
        type="ROUTE",
        data=[],
    )
    agent_output = SummarizerAgentResponse(
        status="ok",
        message="Thanks for reaching out!",
        meta=VideoMeta(actions=[video_button]),
        message_references_a_video=True,
    )

    result = NO_VIDEO_WITHOUT_RECOMMENDATION_GUARDRAIL.guardrail_function(
        guardrail_context,
        Agent(name="support"),
        agent_output,
    )

    assert result.tripwire_triggered is False
    assert result.output_info is None
