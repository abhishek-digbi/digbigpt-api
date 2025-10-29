import pytest
from agent_core.services.prompt_management.langfuse_service import LangFuseService


def test_non_production_labels_not_cached(mocker):
    mock_langfuse_cls = mocker.patch(
        "agent_core.services.prompt_management.langfuse_service.Langfuse"
    )
    mock_langfuse = mock_langfuse_cls.return_value
    dummy_prompt = mocker.Mock()
    dummy_prompt.variables = {}
    mock_langfuse.get_prompt.return_value = dummy_prompt

    service = LangFuseService("STAGING", "secret", "public", "host")
    service.get_variables("KEY", "ANY")

    mock_langfuse.get_prompt.assert_called_with(
        "KEY", label="staging", cache_ttl_seconds=0
    )


def test_production_label_cached(mocker):
    mock_langfuse_cls = mocker.patch(
        "agent_core.services.prompt_management.langfuse_service.Langfuse"
    )
    mock_langfuse = mock_langfuse_cls.return_value
    dummy_prompt = mocker.Mock()
    dummy_prompt.variables = {}
    mock_langfuse.get_prompt.return_value = dummy_prompt

    service = LangFuseService("PRODUCTION", "secret", "public", "host")
    service.get_variables("KEY", "PRODUCTION")

    mock_langfuse.get_prompt.assert_called_with(
        "KEY", label="production", cache_ttl_seconds=600
    )
