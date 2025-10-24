import json
import re
from collections.abc import Mapping


def extract_json_from_content(content):
    """
    Extracts JSON string from a content string that may be wrapped in markdown code fences.
    For example, if the content is:
      ```json
      { "key": "value" }
      ```
    this function returns the inner JSON string.
    """
    # Use regex to capture content between triple backticks optionally labeled with 'json'
    pattern = r"```(?:json)?\s*(.*?)\s*```"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1)
    else:
        # If no code fence is detected, return the original content.
        return content


def text_to_dict(text):
    if isinstance(text, str):
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Error parsing JSON from Response: {e}")

    raise ValueError("Unsupported type for response_data")

def prune_empty(data):
    """Recursively remove keys with None, empty strings, lists, or dicts."""
    is_empty = lambda x: x is None or x == "" or (isinstance(x, (list, dict)) and not x)
    if isinstance(data, dict):
        return {k: v for k, v in ((k, prune_empty(v)) for k, v in data.items()) if not is_empty(v)}
    if isinstance(data, list):
        return [item for item in (prune_empty(x) for x in data) if not is_empty(item)]
    return data


def ensure_dict(data):
    """Return a dictionary for input data.

    If ``data`` is already a dict it is returned as-is. If it's a string,
    the function tries to parse it as JSON and returns the resulting dict when
    the parsed value is a mapping. For any other type, on JSON parsing failure,
    or when the parsed JSON is not a mapping, an empty dict is returned.
    """
    if isinstance(data, dict):
        return data
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, Mapping) else {}
    return {}