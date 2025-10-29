import importlib
import pytest

from agent_core.services.model_context import BaseModelContext
from agent_core.config.schema import AgentConfig
from agent_core.interfaces.agent_logger import IAgentLogger


class DummyLangFuse:
    def get_variables(self, key, user_type):
        return []

    def generate_prompt(self, user_type, prompt_key, data_vars):
        return "prompt"


class DummyRegistry:
    pass


class DummyDataCore:
    def process_variables(self, user_token, vars):
        return {}


class DummyLogger(IAgentLogger):
    def log_interaction(self, ctx, prompt, response, metadata=None, duration=None):
        pass


# @pytest.mark.asyncio
# async def test_run_agent_starts_trace(mocker):
#     mocker.patch("app.agent_metrics.track_agent_metrics", lambda *args, **kwargs: (lambda f: f))
#     ai_core_module = importlib.import_module("agent_core.services.ai_core_service")
#     AiCoreService = ai_core_module.AiCoreService
#     service = AiCoreService(DummyLangFuse(), DummyRegistry(), DummyDataCore(), DummyLogger())
#
#     mocker.patch.object(
#         service,
#         "_load_config",
#         return_value=AgentConfig(
#             id="A",
#             name="A",
#             provider="openai",
#             model="gpt-4o",
#             langfuse_prompt_key="key",
#         ),
#     )
#     mocker.patch.object(service, "_resolve_prompt_key", return_value="key")
#     mocker.patch.object(service, "_execute_adapter", new_callable=mocker.AsyncMock, return_value="ok")
#
#     trace_mock = mocker.patch("agent_core.services.ai_core_service.trace")
#     mocker.patch("agent_core.services.ai_core_service.get_current_trace", return_value=None)
#
#     ctx = BaseModelContext(context_id="ctx1")
#     await service.run_agent("A", ctx)
#
#     trace_mock.assert_called_once_with(
#         workflow_name="A_workflow",
#         group_id="ctx1",
#         metadata={"agent_id": "A", "user_type": None},
#     )
#     trace_mock.return_value.start.assert_called_once_with(mark_as_current=True)
#     trace_mock.return_value.finish.assert_called_once_with(reset_current=True)

