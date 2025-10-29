from unittest.mock import AsyncMock, Mock
import os

from tools.services import digbi_service
from tools import ToolService
from utils.cache import InMemoryCache, set_cache


def test_process_journey_events_variable(mocker):
    sample_response = {
        "message": None,
        "result": [
            {
                "event": "APP_DOWNLOAD",
                "status": "COMPLETED",
                "eventDate": "06-24-2025 09:56:49",
            },
            {
                "event": "FIRST_MEAL",
                "status": "COMPLETED",
                "eventDate": "2025-06-24 23:13:00.0",
            },
        ],
        "status": 200,
        "timestamp": 1756363578351,
        "code": None,
        "errorMessageList": None,
        "includes": None,
        "excludes": None,
    }

    mocker.patch.dict(
        os.environ,
        {
            "DIGBI_URL": "http://test",
            "JOURNEY_EVENTS_PATH": "/v1/journey/events/",
        },
    )
    mocker.patch.object(
        digbi_service,
        "make_digbi_api_call",
        new_callable=AsyncMock,
        return_value=sample_response["result"],
    )
    set_cache(InMemoryCache())
    svc = ToolService(Mock())
    result = svc.process_variables("user-token", ["journey_events"])
    assert result == {"journey_events": sample_response["result"]}
    digbi_service.make_digbi_api_call.assert_awaited_once_with(
        "GET",
        digbi_service.get_journey_events_url(),
        additional_headers={"user-id": "user-token"},
    )
