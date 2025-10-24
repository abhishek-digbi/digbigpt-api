import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Callable
from datetime import date, timedelta

from tools.definitions.common import get_meal_feedback
from tools.definitions.cgm_service import *
from tools import Tool, list_registered_tools, tool, with_db_client
import asyncio
import inspect

from tools.config.api_data_config import API_DATA_CONFIG
from tools.services.api_data_processors import default_processor
from agent_core.config.logging_config import logger
from utils import cache
from utils.db import DBClient


class ToolService:
    """Simple data layer wrapper around API data fetching and processing."""

    def __init__(
            self,
            db_client: DBClient,
            config: Dict[str, Dict[str, Any]] | None = None,
            max_workers: int = 3,
            default_ttl: int = 60,
    ) -> None:
        self.cache = cache.cache
        self.config = config or API_DATA_CONFIG
        self.max_workers = max_workers
        self.default_ttl = default_ttl
        self.db_client = db_client
        self.tools = self._generate_all_tools(db_client)
        self.tool_map = {t.name: t for t in self.tools}

    def process_variables(
        self,
        user_token: str,
        variables: List[str],
        from_date: date | None = None,
        to_date: date | None = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """Fetch and process variables using the configured API map."""
        to_date = to_date or date.today()
        from_date = from_date or (to_date - timedelta(days=7))

        aggregated: Dict[str, Any] = {}
        to_fetch: List[str] = []

        # 1) Attempt to resolve from cache if enabled
        for var in variables:
            config = self.config.get(var)
            if not config:
                logger.warning(f"No mapping for '{var}'")
                continue

            if use_cache:
                key = (
                    self._cache_key(user_token, var, from_date, to_date)
                    if config.get("allow_time_range")
                    else self._cache_key(user_token, var)
                )
                raw = self.cache.get(key)
                if raw is not None:
                    try:
                        aggregated[var] = json.loads(raw)
                    except Exception:
                        aggregated[var] = raw
                    continue
            to_fetch.append(var)

        # 2) Group variables by their fetch function
        api_map: Dict[Callable, List[str]] = {}
        for var in to_fetch:
            cfg = self.config[var]
            fetch_config = cfg["fetch"]
            fetch_callable = fetch_config.func if isinstance(fetch_config, Tool) else fetch_config
            api_map.setdefault(fetch_callable, []).append(var)

        # 3) Fetch concurrently
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_vars = {
                executor.submit(
                    self._run_fetch, fetch_fn, user_token, from_date, to_date
                ): vars_list
                for fetch_fn, vars_list in api_map.items()
            }

            for future in as_completed(future_to_vars):
                var_list = future_to_vars[future]
                try:
                    api_response = future.result()
                    if api_response is None:
                        logger.error(f"API call returned None for {var_list}")
                        continue
                except Exception as exc:
                    logger.error(f"API call failed for {var_list}: {exc}")
                    continue

                # 4) Process and cache each variable
                for var in var_list:
                    cfg = self.config[var]
                    processor = cfg.get("process") or default_processor

                    value = (
                        processor(api_response, cfg, var)
                        if processor is default_processor
                        else processor(api_response)
                    )

                    ttl = cfg.get("cache_timeout", self.default_ttl)

                    if value is None:
                        logger.warning(f"Processor returned None for '{var}'")
                        if use_cache:
                            self.cache.set(
                                self._cache_key(user_token, var, from_date, to_date)
                                if cfg.get("allow_time_range")
                                else self._cache_key(user_token, var),
                                "",
                                ttl,
                            )
                        continue

                    aggregated[var] = value
                    if use_cache:
                        # Always JSON-encode to avoid Redis type errors (e.g., bools)
                        payload = json.dumps(value, default=str)
                        self.cache.set(
                            self._cache_key(user_token, var, from_date, to_date)
                            if cfg.get("allow_time_range")
                            else self._cache_key(user_token, var),
                            payload,
                            ttl,
                        )

        return aggregated

    @staticmethod
    def _run_fetch(
        fetch_fn: Callable, user_token: str, from_date: date, to_date: date
    ):
        """Execute fetch functions that may be coroutine functions."""
        kwargs = {}
        sig = inspect.signature(fetch_fn)
        if "from_date" in sig.parameters:
            kwargs["from_date"] = from_date
        if "to_date" in sig.parameters:
            kwargs["to_date"] = to_date

        if inspect.iscoroutinefunction(fetch_fn):
            return asyncio.run(fetch_fn(user_token, **kwargs))
        return fetch_fn(user_token, **kwargs)

    @staticmethod
    def _cache_key(
        user_token: str,
        var: str,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> str:
        base = f"user_report:{var}:{user_token}"
        if from_date and to_date:
            return f"{base}:{from_date.isoformat()}:{to_date.isoformat()}"
        return base

    def get_tool(self, name: str) -> Tool | None:
        """Return a configured tool by name."""
        return self.tool_map.get(name)

    def _generate_all_tools(self, db_client) -> List[Tool]:
        variable_tools = self._generate_variable_tools()
        db_tools = self.register_db_tools(db_client=db_client)

        # Merge with globally registered tools to ensure side-effect registrations
        # (such as CGM summaries) are discoverable via ``get_tool``.
        merged: dict[str, Tool] = {}
        for t in list_registered_tools():
            merged[t.name] = t
        for t in [*variable_tools, *db_tools]:
            merged[t.name] = t

        return list(merged.values())

    def _generate_variable_tools(self) -> List[Tool]:
        """Create :class:`Tool` objects for each configured variable."""
        tools: List[Tool] = []

        for var, cfg in self.config.items():
            if cfg.get("allow_time_range"):
                def _func(
                    user_token: str,
                    last_num_days: int = 7,
                    var_name: str = var,
                    use_cache: bool | None = None,
                ) -> Any:
                    """Return the requested variable for the user."""
                    to_date = date.today()
                    from_date = to_date - timedelta(days=last_num_days)
                    result = self.process_variables(
                        user_token, [var_name], from_date, to_date, use_cache=True if use_cache is None else bool(use_cache)
                    )
                    return result.get(var_name)

                description = (
                    f"Fetch {var} value for a user token over the last N days"
                )
            else:
                def _func(
                    user_token: str,
                    var_name: str = var,
                    use_cache: bool | None = None,
                ) -> Any:
                    """Return the requested variable for the user."""
                    result = self.process_variables(user_token, [var_name], use_cache=True if use_cache is None else bool(use_cache))
                    return result.get(var_name)

                description = f"Fetch {var} value for a user token"

            tools.append(
                tool(
                    _func,
                    name=f"get_{var}",
                    description=description,
                )
            )

        return tools

    @staticmethod
    def register_db_tools(db_client) -> List[Tool]:
        return [with_db_client(get_meal_feedback, db_client)]
