from utils.json_util import ensure_dict


def test_ensure_dict_from_json_string_dict():
    assert ensure_dict('{"key": "value"}') == {"key": "value"}


def test_ensure_dict_non_mapping_json_returns_empty_dict():
    assert ensure_dict("[]") == {}
    assert ensure_dict("123") == {}
    assert ensure_dict("null") == {}
