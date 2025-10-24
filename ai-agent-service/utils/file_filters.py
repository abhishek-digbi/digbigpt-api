from typing import Any, Dict, List, Optional

import app  # noqa: F401  # ensure app is initialized for DI in FastAPI


def _coerce_list(value: Any) -> List[Any]:
    """Helper: turn value into a flat list of non-empty items."""
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = [value]
    # Normalize and drop empties
    out: List[Any] = []
    for v in items:
        if v is None:
            continue
        if isinstance(v, str):
            vv = v.strip()
            if vv:
                out.append(vv)
        else:
            out.append(v)
    return out


def _one_filter(key: str, value: Any) -> Optional[Dict[str, Any]]:
    """Build a filter for a single key.

    - Scalar -> equality filter
    - List   -> OR of equality filters across values
    """
    values = _coerce_list(value)
    if not values:
        return None
    if len(values) == 1:
        return {"type": "eq", "key": key, "value": values[0]}
    # For arrays: OR over boolean flag keys <key>_<value> == 1
    return {
        "type": "or",
        "filters": [
            {"type": "eq", "key": f"{key}_{v}", "value": 1} for v in values
        ],
    }


def build_file_filters(filters: Dict[str, Any] | None) -> Dict[str, Any] | None:
    """Return filters in OpenAI FileSearch format from arbitrary key/value pairs.

    Behavior
    - Accepts multiple keys, default top-level operator is AND across keys.
    - For each key, a list value becomes an OR of equality filters; a scalar becomes an equality.
    - Empty/None values are ignored. If nothing valid remains, returns None (no filter applied).
    """
    if not filters or not isinstance(filters, dict):
        return None

    built: List[Dict[str, Any]] = []
    for key, value in filters.items():
        f = _one_filter(key, value)
        if f:
            built.append(f)

    if not built:
        return None
    if len(built) == 1:
        return built[0]
    return {"type": "and", "filters": built}
