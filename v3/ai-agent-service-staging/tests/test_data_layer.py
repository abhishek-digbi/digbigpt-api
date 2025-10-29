from unittest.mock import Mock
from datetime import date, timedelta
import pytest
from tools import ToolService
from utils.cache import set_cache
from utils.db import DBClient


class DummyCache:
    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ttl):
        self.store[key] = value


def test_process_variables_single_fetch():
    calls = []

    def fake_fetch(token, from_date=None, to_date=None):
        calls.append((token, from_date, to_date))
        return {"foo": 1, "bar": 2}

    config = {
        "foo": {"fetch": fake_fetch, "process": lambda d: d["foo"], "cache_timeout": 10},
        "bar": {"fetch": fake_fetch, "process": lambda d: d["bar"], "cache_timeout": 10},
    }

    cache = DummyCache()
    set_cache(cache)
    mock_db_client = Mock(spec=DBClient)
    svc = ToolService(mock_db_client, config=config)

    result = svc.process_variables("u1", ["foo", "bar"])
    assert result == {"foo": 1, "bar": 2}
    expected_to = date.today()
    expected_from = expected_to - timedelta(days=7)
    assert calls == [("u1", expected_from, expected_to)]


def test_default_processor_key_path():
    calls = []

    def fake_fetch(token, from_date=None, to_date=None):
        calls.append((token, from_date, to_date))
        return {"solera_v2_program_id": "prog123"}

    config = {
        "solera_program_id": {
            "fetch": fake_fetch,
            "process": None,
            "cache_timeout": 10,
            "key_path": ["solera_v2_program_id"],
        },
    }

    cache = DummyCache()
    set_cache(cache)
    mock_db_client = Mock(spec=DBClient)
    svc = ToolService(mock_db_client, config=config)

    result = svc.process_variables("u1", ["solera_program_id"])
    assert result == {"solera_program_id": "prog123"}
    expected_to = date.today()
    expected_from = expected_to - timedelta(days=7)
    assert calls == [("u1", expected_from, expected_to)]


def test_default_processor_date_of_enrollment():
    calls = []

    def fake_fetch(token, from_date=None, to_date=None):
        calls.append((token, from_date, to_date))
        return {"date_of_enrollment": "2024-01-01"}

    config = {
        "date_of_enrollment": {
            "fetch": fake_fetch,
            "process": None,
            "cache_timeout": 10,
            "key_path": ["date_of_enrollment"],
        },
    }

    cache = DummyCache()
    set_cache(cache)
    mock_db_client = Mock(spec=DBClient)
    svc = ToolService(mock_db_client, config=config)

    result = svc.process_variables("u1", ["date_of_enrollment"])
    assert result == {"date_of_enrollment": "2024-01-01"}
    expected_to = date.today()
    expected_from = expected_to - timedelta(days=7)
    assert calls == [("u1", expected_from, expected_to)]


def test_default_processor_locale():
    calls = []

    def fake_fetch(token, from_date=None, to_date=None):
        calls.append((token, from_date, to_date))
        return {"preferred_locale": "en-US"}

    config = {
        "locale": {
            "fetch": fake_fetch,
            "process": None,
            "cache_timeout": 10,
            "key_path": ["preferred_locale"],
        },
    }

    cache = DummyCache()
    set_cache(cache)
    mock_db_client = Mock(spec=DBClient)
    svc = ToolService(mock_db_client, config=config)

    result = svc.process_variables("u1", ["locale"])
    assert result == {"locale": "en-US"}
    expected_to = date.today()
    expected_from = expected_to - timedelta(days=7)
    assert calls == [("u1", expected_from, expected_to)]


def test_transit_audit_variables_key_path():
    calls = []

    def fake_fetch(token, from_date=None, to_date=None):
        calls.append((token, from_date, to_date))
        return {
            "eligibleKits": [{"kitId": "KIT-123"}],
            "firstYearReportStatus": {"status": "COMPLETED"},
            "allShipments": [{"shipmentId": "SHIP-1"}],
        }

    config = {
        "eligible_kits": {
            "fetch": fake_fetch,
            "process": None,
            "cache_timeout": 10,
            "key_path": ["eligibleKits"],
        },
        "first_year_report_status": {
            "fetch": fake_fetch,
            "process": None,
            "cache_timeout": 10,
            "key_path": ["firstYearReportStatus"],
        },
        "transit_audit_shipments": {
            "fetch": fake_fetch,
            "process": None,
            "cache_timeout": 10,
            "key_path": ["allShipments"],
        },
    }

    cache = DummyCache()
    set_cache(cache)
    mock_db_client = Mock(spec=DBClient)
    svc = ToolService(mock_db_client, config=config)

    result = svc.process_variables(
        "u1", ["eligible_kits", "first_year_report_status", "transit_audit_shipments"]
    )

    assert result == {
        "eligible_kits": [{"kitId": "KIT-123"}],
        "first_year_report_status": {"status": "COMPLETED"},
        "transit_audit_shipments": [{"shipmentId": "SHIP-1"}],
    }

    expected_to = date.today()
    expected_from = expected_to - timedelta(days=7)
    assert calls == [("u1", expected_from, expected_to)]


def test_generated_tool_last_num_days():
    calls = []

    def fake_fetch(token, from_date=None, to_date=None):
        calls.append((token, from_date, to_date))
        return {"foo": 1}

    config = {
        "foo": {
            "fetch": fake_fetch,
            "process": lambda d: d["foo"],
            "cache_timeout": 10,
            "allow_time_range": True,
        },
    }

    cache = DummyCache()
    set_cache(cache)
    mock_db_client = Mock(spec=DBClient)
    svc = ToolService(mock_db_client, config=config)

    tool = svc.get_tool("get_foo")
    result = tool.func("u1", last_num_days=3)
    assert result == 1
    expected_to = date.today()
    expected_from = expected_to - timedelta(days=3)
    assert calls == [("u1", expected_from, expected_to)]


def test_generated_tool_default_last_num_days():
    calls = []

    def fake_fetch(token, from_date=None, to_date=None):
        calls.append((token, from_date, to_date))
        return {"foo": 1}

    config = {
        "foo": {
            "fetch": fake_fetch,
            "process": lambda d: d["foo"],
            "cache_timeout": 10,
            "allow_time_range": True,
        },
    }
    cache = DummyCache()
    set_cache(cache)
    mock_db_client = Mock(spec=DBClient)
    svc = ToolService(mock_db_client, config=config)

    tool = svc.get_tool("get_foo")
    result = tool.func("u1")
    assert result == 1
    expected_to = date.today()
    expected_from = expected_to - timedelta(days=7)
    assert calls == [("u1", expected_from, expected_to)]


def test_generated_tool_no_last_num_days_arg():
    calls = []

    def fake_fetch(token, from_date=None, to_date=None):
        calls.append((token, from_date, to_date))
        return {"foo": 1}

    config = {
        "foo": {"fetch": fake_fetch, "process": lambda d: d["foo"], "cache_timeout": 10},
    }

    cache = DummyCache()
    set_cache(cache)
    mock_db_client = Mock(spec=DBClient)
    svc = ToolService(mock_db_client, config=config)

    tool = svc.get_tool("get_foo")
    result = tool.func("u1")
    assert result == 1
    expected_to = date.today()
    expected_from = expected_to - timedelta(days=7)
    assert calls == [("u1", expected_from, expected_to)]

    with pytest.raises(TypeError):
        tool.func("u1", last_num_days=3)


def test_time_range_cache_key_changes():
    calls = []

    def fake_fetch(token, from_date=None, to_date=None):
        calls.append((token, from_date, to_date))
        return {"foo": (to_date - from_date).days}

    config = {
        "foo": {
            "fetch": fake_fetch,
            "process": lambda d: d["foo"],
            "cache_timeout": 10,
            "allow_time_range": True,
        }
    }

    cache = DummyCache()
    set_cache(cache)
    mock_db_client = Mock(spec=DBClient)
    svc = ToolService(mock_db_client, config=config)

    to = date(2024, 1, 31)
    result1 = svc.process_variables(
        "u1", ["foo"], from_date=to - timedelta(days=30), to_date=to
    )
    result2 = svc.process_variables(
        "u1", ["foo"], from_date=to - timedelta(days=7), to_date=to
    )

    assert result1 == {"foo": 30}
    assert result2 == {"foo": 7}
    assert len(calls) == 2
