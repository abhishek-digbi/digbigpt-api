from agent_core.config.logging_config import logger
from typing import Any, Dict, Optional, Type, Callable, Sequence
from agents.lifecycle import AgentHooks

from agent_core.config.loader import get_agent_cfg
from agent_core.config.schema import AgentConfig
from agent_core.interfaces.agent_logger import IAgentLogger
import time
import json
from agent_core.services.prompt_management.langfuse_service import LangFuseService
import utils.env_loader as env_loader
from agent_core.services.adapters.adapter_registry import AdapterRegistry
from utils.slack_util import send_prompt_variables_log
from tools import ToolService, with_user_token, Tool, get_registered_tool
from agent_core.services.model_context import ModelContext
from utils.file_filters import build_file_filters
from app.agent_metrics import track_agent_metrics


class AiCoreService:
    """
    AiCoreService orchestrates end-to-end AI workflows:
      1. Configuration validation
      2. Prompt resolution and hydration
      3. Prompt generation via LangFuse
      4. Dispatch to appropriate adapter
    Provides clear logging and error handling for observability and tracing.
    """

    def __init__(
        self,
        langfuse: LangFuseService,
        registry: AdapterRegistry,
        data_core: ToolService,
        agent_logger: IAgentLogger,
    ) -> None:
        self.langfuse = langfuse
        self.registry = registry
        self.data_core = data_core
        self.agent_logger = agent_logger
        logger.info(
            "AiCoreService initialized with LangFuseService=%s, AdapterRegistry=%s, ToolService=%s, AgentLogger=%s",
            type(langfuse).__name__,
            type(registry).__name__,
            type(data_core).__name__,
            type(agent_logger).__name__,
        )

    @track_agent_metrics(agent_id_arg="agent_id")
    async def run_agent(
        self,
        agent_id: str,
        ctx: ModelContext,
        output_type: Type[Any] = str,
        strict_json_schema: bool = True,
        hooks: Optional[AgentHooks[Any]] = None,
        output_guardrails: Optional[Sequence[Any]] = None,
        input_guardrails: Optional[Sequence[Any]] = None,
        file_filters: Optional[Dict[str, Any]] = None,
        **agent_kwargs: Any,
    ) -> Any:
        """
        Execute the full agent workflow.
        Args:
            agent_id: Unique identifier for the AI agent configuration.
            ctx: Context containing user data and query.
            output_type: Expected output type.
            image_url: Optional image input URL.
            tools: Additional tools to pass to the agent. These are merged with
                tools listed in the configuration and any built-ins provided by
                :class:`ToolService`.
            hooks: lifecycle hooks
            file_filters: Optional dictionary of file filter hints
            agent_kwargs: Additional adapter-specific options.
        Returns:
            Adapter output cast to the specified type.
        Raises:
            ValueError: If configuration is invalid or missing required fields.
            :param tools:
            :param output_type:
            :param ctx:
            :param agent_id:
            :param strict_json_schema:
        """
        logger.info(
            "run_agent started for agent_id=%s and context_id=%s",
            agent_id,
            ctx.context_id,
        )

        start_time = time.perf_counter()

        try:
            cfg = self._load_config(agent_id)
            prompt_key = self._resolve_prompt_key(cfg, agent_id)
            prompt_vars = self.langfuse.get_variables(prompt_key, ctx.user_type)

            data_vars = self._hydrate_data(ctx, prompt_vars)
            send_prompt_variables_log(
                data_vars, getattr(ctx, "feature_context", None), agent_id
            )
            final_prompt = self._generate_prompt(prompt_key, ctx, data_vars)
            # MCP implementation: wrap prompt with protocol context
            wrapped_prompt = self._wrap_prompt_mcp(final_prompt, ctx)

            provided_tools = agent_kwargs.pop("tools", [])

            cfg_tools = []
            for name in cfg.tools or []:
                t = getattr(self.data_core, "get_tool", lambda n: None)(name)
                if t is None:
                    t = get_registered_tool(name)
                if t is not None:
                    cfg_tools.append(t)

            all_tools = (
                cfg_tools
                # + list(getattr(self.data_core, "tools", []))
                + list(provided_tools)
            )

            bound_tools = [
                with_user_token(t, ctx.user_token) if isinstance(t, Tool) else t
                for t in all_tools
            ]

            normalized_filters = build_file_filters(file_filters)

            result = await self._execute_adapter(
                ctx,
                cfg,
                wrapped_prompt,
                agent_id,
                ctx.image_url,
                output_type,
                strict_json_schema,
                tools=bound_tools or None,
                file_filters=normalized_filters,
                hooks=hooks,
                output_guardrails=output_guardrails,
                input_guardrails=input_guardrails,
                **agent_kwargs,
            )

            duration = time.perf_counter() - start_time

            self.record_agent_status_and_duration(agent_id, ctx, duration, result)

            # Log the interaction using the agent logger interface
            self.agent_logger.log_interaction(
                ctx=ctx,
                prompt=final_prompt,
                response=result,
                metadata={
                    "agent_id": agent_id,
                    "provider": cfg.provider,
                    "model": cfg.model,
                    "image_url": ctx.image_url,
                    **data_vars,
                    **agent_kwargs,
                },
                duration=duration,
            )
            # ctx.agent_durations[agent_id] = duration
            logger.info("run_agent completed for agent_id=%s", agent_id)
            return result
        except Exception:
            logger.exception("run_agent failed for agent_id=%s", agent_id)
            raise

    @staticmethod
    def record_agent_status_and_duration(agent_id, ctx, duration, result):
        try:
            status_value = None
            if result is not None:
                try:
                    if isinstance(result, dict):
                        status_value = result.get("status")
                    elif hasattr(result, "status"):
                        status_value = getattr(result, "status")
                except (TypeError, AttributeError):
                    # Handle case where result is a string or other type that doesn't support these operations
                    status_value = None
            if hasattr(ctx, "agent_statuses"):
                entry = {"agent": agent_id, "duration": f"{duration:.2f}"}
                if status_value is not None:
                    entry["status"] = status_value
                ctx.agent_statuses.append(entry)
        except Exception as e:
            logger.error("Error recording agent status and duration", e)

        # Record the agent execution details on the context

    @staticmethod
    def _load_config(agent_id: str) -> AgentConfig:
        """Fetch and validate the agent configuration."""
        try:
            cfg = get_agent_cfg(agent_id)
            logger.debug(
                "Loaded config for agent_id=%s: provider=%s, model=%s",
                agent_id,
                cfg.provider,
                cfg.model,
            )
            return cfg
        except Exception as ex:
            logger.error(
                "Failed to load config for agent_id=%s: %s", agent_id, ex, exc_info=True
            )
            raise

    @staticmethod
    def _resolve_prompt_key(cfg: AgentConfig, agent_id: str) -> str:
        """Ensure a LangFuse prompt key is configured."""
        key = cfg.langfuse_prompt_key
        if not key:
            logger.error("Prompt key missing for agent_id=%s", agent_id)
            raise ValueError(f"No prompt key configured for {agent_id}")
        logger.debug("Resolved prompt_key=%s for agent_id=%s", key, agent_id)
        return key

    def _hydrate_data(
        self, ctx: ModelContext, prompt_vars: list[str]
    ) -> Dict[str, Any]:
        """Merge context data with fetched data for missing variables."""
        logger.debug(
            "Hydrating data for user_type=%s, prompt_vars=%s",
            ctx.user_type,
            prompt_vars,
        )
        provided = {
            var: (
                ctx.data[var]
                if ctx.data and var in ctx.data
                else getattr(ctx, var, None)
            )
            for var in prompt_vars
            if (ctx.data and var in ctx.data) or hasattr(ctx, var)
        }
        provided["query"] = ctx.query

        missing = [var for var in prompt_vars if var not in provided]

        fetched = {}
        if missing:
            try:
                fetched = self.data_core.process_variables(ctx.user_token, missing)
                logger.info("Fetched missing vars=%s for user_token", missing)
            except Exception as ex:
                logger.error(
                    "Data fetch failed for vars=%s: %s", missing, ex, exc_info=True
                )
                raise

        data_vars = {**provided, **fetched}
        logger.debug("Final data_vars keys=%s", list(data_vars.keys()))
        return data_vars

    def _generate_prompt(
        self, prompt_key: str, ctx: ModelContext, data_vars: Dict[str, Any]
    ) -> str:
        """Render the final prompt via LangFuse templating."""
        prompt = self.langfuse.generate_prompt(ctx.user_type, prompt_key, data_vars)
        logger.debug("Generated prompt of length=%d", len(prompt))
        return prompt

    @staticmethod
    def _wrap_prompt_mcp(prompt: str, ctx: ModelContext) -> str:
        """Wrap prompt within Model Context Protocol envelope."""
        if hasattr(ctx, "to_mcp_payload"):
            return ctx.to_mcp_payload(prompt)
        envelope = {
            "mcp_version": getattr(ctx, "mcp_version", "1.0"),
            "metadata": getattr(ctx, "metadata", {}),
            "state": getattr(ctx, "state", {}),
            "prompt": prompt,
        }
        # MCP implementation: convert to JSON string
        return json.dumps(envelope)

    async def _execute_adapter(
        self,
        ctx: ModelContext,
        cfg: AgentConfig,
        prompt: str,
        agent_id: str,
        image_url: Optional[str],
        output_type: Type[Any],
        strict_json_schema: bool,
        tools: Optional[list[Any]] = None,
        file_filters: Optional[Dict[str, Any]] = None,
        hooks: Optional[AgentHooks[Any]] = None,
        output_guardrails: Optional[Sequence[Any]] = None,
        input_guardrails: Optional[Sequence[Any]] = None,
        **agent_kwargs: Any,
    ) -> Any:
        """Dispatch prompt and parameters to the configured adapter."""
        provider = cfg.provider or "openai"
        model = agent_kwargs.get("model") or cfg.model

        logger.debug(
            "Dispatching to adapter provider=%s, model=%s, agent_id=%s",
            provider,
            model,
            agent_id,
        )
        adapter = self.registry.get(provider)

        # Determine if this agent should send messages array input from env var
        user_type = (getattr(ctx, "user_type", None) or "").strip().lower()
        agents_env = (
            env_loader.get_env_var("AGENTS_USING_ROLE_BASED_MESSAGES_INPUT", "") or ""
        )
        enabled_agents = {a.strip() for a in agents_env.split(",") if a.strip()}
        role_based_messages_as_input = agent_id in enabled_agents
        logger.info(
            "Role-based messages decision: enabled=%s | agent_id=%s | enabled_agents_count=%d | user_type=%s",
            role_based_messages_as_input,
            agent_id,
            len(enabled_agents),
            user_type,
        )

        # MCP implementation: prompt already wrapped with context metadata
        dynamic_instructions = agent_kwargs.pop("dynamic_instructions", None)

        additional_messages = agent_kwargs.pop("additional_messages", None)
        input_messages = agent_kwargs.pop("input_messages", None)

        result = await adapter.run(
            prompt=prompt,
            ctx=ctx,
            agent_id=agent_id,
            context_id=ctx.context_id,
            user_token=ctx.user_token,
            user_type=ctx.user_type,
            user_query=ctx.query,
            feature_context=ctx.feature_context,
            model=model,
            assistant_id=cfg.assistant_id,
            text_format=cfg.text_format,
            output_type=output_type,
            instructions=dynamic_instructions or cfg.instructions,
            vector_store_ids=cfg.vector_store_ids,
            temperature=cfg.temperature,
            top_p=cfg.top_p,
            image_url=image_url,
            strict_json_schema=strict_json_schema,
            tool_choice=agent_kwargs.pop("tool_choice", None),
            tools=tools,
            file_filters=file_filters,
            hooks=hooks,
            output_guardrails=output_guardrails,
            input_guardrails=input_guardrails,
            role_based_messages_as_input=role_based_messages_as_input,
            additional_messages=additional_messages,
            input_messages=input_messages,
            **agent_kwargs,
        )
        logger.info("Adapter execution complete for agent_id=%s", agent_id)
        return result
