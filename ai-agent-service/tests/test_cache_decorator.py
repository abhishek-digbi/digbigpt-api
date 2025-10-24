from utils.cache import cached, set_cache

class DummyCache:
    def __init__(self):
        self.store = {}
        self.ttls = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ttl):
        self.store[key] = value
        self.ttls[key] = ttl

def test_cached_decorator():
    cache = DummyCache()
    set_cache(cache)

    call_count = {"count": 0}

    @cached(ttl=5)
    def add(x, y):
        call_count["count"] += 1
        return x + y

    # First call triggers function execution
    assert add(1, 2) == 3
    # Second call with same params should use cache
    assert add(1, 2) == 3
    assert call_count["count"] == 1
    assert len(cache.store) == 1
    assert list(cache.ttls.values())[0] == 5

    # Different params should invoke function again
    assert add(2, 3) == 5
    assert call_count["count"] == 2
    assert len(cache.store) == 2


import pytest


@pytest.mark.asyncio
async def test_cached_decorator_async():
    cache = DummyCache()
    set_cache(cache)

    call_count = {"count": 0}

    @cached(ttl=5)
    async def multiply(x, y):
        call_count["count"] += 1
        return x * y

    assert await multiply(2, 4) == 8
    assert await multiply(2, 4) == 8
    assert call_count["count"] == 1
    assert len(cache.store) == 1
    assert list(cache.ttls.values())[0] == 5
