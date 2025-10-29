"""Global cache management and decorators."""
from __future__ import annotations

from typing import Any, Callable
import functools
import hashlib
import json
import inspect


class InMemoryCache:
    """Simple in-memory cache used as a fallback when no cache backend is
    configured."""

    def __init__(self) -> None:
        self.store: dict[str, Any] = {}

    def get(self, key: str) -> Any | None:
        return self.store.get(key)

    def set(self, key: str, value: Any, ttl: int | None = None, **kwargs: Any) -> None:
        self.store[key] = value


cache: Any = InMemoryCache()


def set_cache(c: Any) -> None:
    """Set the global cache instance used across the application."""
    global cache
    cache = c


def _make_cache_key(func: Callable, args: tuple, kwargs: dict) -> str:
    """Create a deterministic cache key for a function call."""
    key_payload = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    hashed = hashlib.md5(key_payload.encode()).hexdigest()
    return f"func_cache:{func.__module__}.{func.__name__}:{hashed}"


def cached(ttl: int) -> Callable[[Callable], Callable]:
    """Cache the result of a function for ``ttl`` seconds using the global cache."""

    def decorator(func: Callable) -> Callable:
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                if cache is None:
                    return await func(*args, **kwargs)

                key = _make_cache_key(func, args, kwargs)
                cached_value = cache.get(key)
                if cached_value is not None:
                    try:
                        return json.loads(cached_value)
                    except Exception:
                        return cached_value

                result = await func(*args, **kwargs)

                # Always store as JSON to ensure Redis compatibility (e.g., bools)
                payload = json.dumps(result, default=str)
                cache.set(key, payload, ttl)
                return result

            return wrapper
        else:
            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                if cache is None:
                    return func(*args, **kwargs)

                key = _make_cache_key(func, args, kwargs)
                cached_value = cache.get(key)
                if cached_value is not None:
                    try:
                        return json.loads(cached_value)
                    except Exception:
                        return cached_value

                result = func(*args, **kwargs)

                # Always store as JSON to ensure Redis compatibility (e.g., bools)
                payload = json.dumps(result, default=str)
                cache.set(key, payload, ttl)
                return result

            return wrapper

    return decorator

