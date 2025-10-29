from typing import Any, Dict, List, Optional, Type, TypeVar
import os

import asyncio
import openai
from agents import (
    Agent,
    Runner,
    FileSearchTool,
    AgentOutputSchema,
    ModelSettings,
    get_current_trace,
    trace,
)
from agents.lifecycle import AgentHooks, RunHooks
from agents.tool import function_tool
from agents.exceptions import (
    InputGuardrailTripwireTriggered,
    OutputGuardrailTripwireTriggered,
)

from agent_core.config.logging_config import logger
from agent_core.services.base_agent import BaseAgentAdapter
from agent_core.services.model_context import ModelContext
from tools import Tool

T = TypeVar("T")


class OpenAIService(BaseAgentAdapter):
    """
    OpenAIService provides a streamlined interface for diverse OpenAI workflows:
    - Standard chat completions
    - Custom assistant threads
    - Agent-driven processing with vector store integration

    Leverages modular abstractions to optimize maintainability and scalability.
    """

    DEFAULT_MODEL = "gpt-4o"

    def __init__(self, api_key: str) -> None:
        """Initialize service with authentication context."""
        if not api_key:
            raise ValueError("OpenAI API key is missing.")
        openai.api_key = api_key

    async def run(
        self,
        prompt: str,
        ctx: ModelContext,
        context_id: Optional[str] = None,
        user_query: Optional[str] = None,
        user_token: Optional[str] = None,
        user_type: Optional[str] = None,
        image_url: Optional[str] = None,
        max_tokens: int = 1000,
        feature_context: Optional[str] = None,
        model: Optional[str] = None,
        text_format: Optional[str] = None,
        assistant_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        instructions: Optional[str] = None,
        output_type: Type[T] = str,
        vector_store_ids: Optional[List[str]] = None,
        strict_json_schema: bool = True,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        tool_choice: Optional[str] = None,
        tools: Optional[List[Any]] = None,
        file_filters: Optional[Dict[str, Any]] = None,
        hooks: Optional[AgentHooks[Any]] = None,
        output_guardrails: Optional[List[Any]] = None,
        input_guardrails: Optional[List[Any]] = None,
        role_based_messages_as_input: Optional[bool] = None,
        additional_messages: Optional[List[Dict[str, str]]] = None,
        input_messages: Optional[List[Dict[str, Any]]] = None,
    ) -> T:
        """
        Entrypoint for generating model outputs across all supported workflows.
        """
        # Prefer a stable, meaningful workflow name for tracing.
        # Fall back to agent_id when feature_context is absent to keep traces visible.
        workflow_name = feature_context or agent_id or "Unknown"
        # Always ensure a valid current trace context for Observability.
        # In some environments, background tasks may inherit a stale/non-active current trace;
        # allow forcing a fresh trace via env to guarantee visibility.
        always_start_trace = (
            os.getenv("AGENTS_ALWAYS_START_TRACE", "false").lower() in ("1", "true", "yes")
        )
        # Per-call override via context data (set by async endpoints if desired)
        force_new_trace = False
        try:
            data_dict = getattr(ctx, "data", None)
            if isinstance(data_dict, dict):
                force_new_trace = bool(
                    data_dict.get("__force_new_trace") or data_dict.get("force_new_trace")
                )
        except Exception:
            force_new_trace = False
        trace_ctx = trace(
            workflow_name=workflow_name,
            group_id=context_id,
            metadata={
                "agent_id": agent_id,
                "user_query": user_query,
                "user_token": user_token,
                "user_type": user_type,
            },
        )
        started_trace = False
        if always_start_trace or force_new_trace or get_current_trace() is None:
            trace_ctx.start(mark_as_current=True)
            started_trace = True

        effective_model = model or self.DEFAULT_MODEL
        try:
            if agent_id:
                return await self._agent_flow(
                    prompt,
                    ctx,
                    image_url,
                    agent_id,
                    instructions,
                    effective_model,
                    output_type,
                    vector_store_ids,
                    strict_json_schema,
                    temperature,
                    top_p,
                    tool_choice,
                    tools,
                    file_filters,
                    hooks,
                    output_guardrails,
                    input_guardrails,
                    role_based_messages_as_input,
                    additional_messages,
                    input_messages,
                )

            if assistant_id:
                return await self._assistant_flow(
                    assistant_id,
                    prompt,
                    instructions,
                    text_format,
                    temperature=temperature,
                    top_p=top_p,
                )

            return await self._standard_flow(
                prompt,
                image_url,
                effective_model,
                max_tokens,
                text_format,
                temperature,
                top_p,
            )
        finally:
            if started_trace:
                trace_ctx.finish(reset_current=True)

    async def _agent_flow(
        self,
        prompt: str,
        context: Any,
        image_url: Optional[str],
        agent_id: str,
        instructions: Optional[str],
        model: str,
        output_type: Type[T],
        vector_store_ids: Optional[List[str]],
        strict_json_schema: bool,
        temperature: Optional[float],
        top_p: Optional[float],
        tool_choice: Optional[str],
        tools: Optional[List[Any]],
        file_filters: Optional[Dict[str, Any]],
        hooks: Optional[Any],
        output_guardrails: Optional[List[Any]],
        input_guardrails: Optional[List[Any]],
        role_based_messages_as_input: Optional[bool],
        additional_messages: Optional[List[Dict[str, str]]],
        input_messages: Optional[List[Dict[str, Any]]],
    ) -> T:
        """Configure and invoke an Agent instance for contextually enriched responses."""
        agent_hooks: Optional[AgentHooks[Any]] = None
        run_hooks: Optional[RunHooks[Any]] = None
        if isinstance(hooks, AgentHooks):
            agent_hooks = hooks
        if isinstance(hooks, RunHooks):
            run_hooks = hooks

        agent = self._create_agent(
            agent_id,
            instructions,
            model,
            output_type,
            vector_store_ids,
            strict_json_schema=strict_json_schema,
            temperature=temperature,
            top_p=top_p,
            tool_choice=tool_choice,
            tools=tools,
            file_filters=file_filters,
            hooks=agent_hooks,
            output_guardrails=output_guardrails,
            input_guardrails=input_guardrails,
        )

        if input_messages is not None:
            payload = list(input_messages)
            logger.info(
                "Agent payload (precomputed) used | agent_id=%s | messages=%d",
                agent_id,
                len(payload) if isinstance(payload, list) else -1,
            )
        elif role_based_messages_as_input:
            payload = self._build_agent_payload_v2(
                prompt,
                image_url,
                context,
                additional_messages,
            )
            try:
                msg_count = len(payload) if isinstance(payload, list) else -1
            except Exception:
                msg_count = -1
            logger.info(
                "Agent payload (role-based) constructed | agent_id=%s | messages=%s",
                agent_id,
                msg_count,
            )
        else:
            payload = self._build_agent_payload(
                prompt,
                image_url,
                additional_messages,
            )
            logger.info(
                "Agent payload (simple) constructed | agent_id=%s | messages=%d",
                agent_id,
                len(payload) if isinstance(payload, list) else -1,
            )
        try:
            return await self._invoke_agent(
                agent,
                payload,
                context,
                agent_identifier=agent_id,
                run_hooks=run_hooks,
            )  # type: ignore[arg-type]
        except (InputGuardrailTripwireTriggered, OutputGuardrailTripwireTriggered):
            raise
        except Exception as err:
            raise RuntimeError(f"Failed to run agent: {err}") from err

    @staticmethod
    def _create_agent(
        agent_id: str,
        instructions: Optional[str],
        model: str,
        output_type: Type[T],
        vector_store_ids: Optional[List[str]],
        strict_json_schema: bool,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        tool_choice: Optional[str] = None,
        tools: Optional[List[Any]] = None,
        file_filters: Optional[Dict[str, Any]] = None,
        hooks: Optional[AgentHooks[Any]] = None,
        output_guardrails: Optional[List[Any]] = None,
        input_guardrails: Optional[List[Any]] = None,
    ) -> Agent:
        final_tools: List[Any] = []
        for t in tools or []:
            if isinstance(t, Tool):
                final_tools.append(to_openai_function_tool(t))
            else:
                final_tools.append(t)
        if vector_store_ids:
            final_tools.append(
                FileSearchTool(
                    max_num_results=10,
                    vector_store_ids=vector_store_ids,
                    filters=file_filters,
                )
            )
        return Agent(
            name=agent_id,
            instructions=instructions,
            tools=final_tools,
            model=model,
            model_settings=ModelSettings(
                temperature=temperature, top_p=top_p, tool_choice=tool_choice
            ),
            output_type=AgentOutputSchema(
                output_type, strict_json_schema=strict_json_schema
            ),
            hooks=hooks,
            output_guardrails=list(output_guardrails or []),
            input_guardrails=list(input_guardrails or []),
        )

    @staticmethod
    def _build_agent_payload(
        prompt: str,
        image_url: Optional[str],
        additional_messages: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]]

        if image_url:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_image",
                            "image_url": image_url,
                            "detail": "auto",
                        },
                    ],
                },
                {"role": "user", "content": prompt},
            ]
        else:
            messages = [{"role": "user", "content": prompt}]

        if additional_messages:
            messages.extend(msg.copy() for msg in additional_messages)

        return messages

    def _build_agent_payload_v2(
        self,
        prompt: str,
        image_url: Optional[str],
        ctx: Any,
        additional_messages: Optional[List[Dict[str, str]]] = None,
    ) -> Any:
        """Construct multimodal payloads for agent consumption."""

        messages: List[Dict[str, Any]] = [{"role": "system", "content": prompt}]
        try:
            history = getattr(ctx, "conversation_history", None) or {}
            recent = (
                history.get("recent_messages", []) if isinstance(history, dict) else []
            )
            logger.info(
                "Building role-based payload: recent_messages_count=%d",
                len(recent) if isinstance(recent, list) else -1,
            )

            # Stable sort by timestamp if available
            def _timestamp_key(m):
                try:
                    ts = m.get("timestamp")
                    return int(ts) if ts is not None else float("inf")
                except Exception:
                    return float("inf")

            recent_sorted = sorted(recent, key=_timestamp_key)

            # If the latest message is from the user, remove it
            if recent_sorted:
                last_sender = str(recent_sorted[-1].get("sender", "")).lower()
                if last_sender == "user":
                    recent_sorted = recent_sorted[:-1]
                    logger.debug(
                        "Dropped latest user message from history, including it below"
                    )
            for msg in recent_sorted:
                sender = str(msg.get("sender", "user")).lower()
                role = "user" if sender == "user" else "assistant"
                content = msg.get("content", "")
                if content is None:
                    content = ""
                messages.append({"role": role, "content": content})

            user_query = getattr(ctx, "query", None)
            if user_query:
                messages.extend(self._build_agent_payload(user_query, image_url))
            else:
                logger.info("User query absent")

            if additional_messages:
                messages.extend(msg.copy() for msg in additional_messages)

            logger.info(
                "Role-based payload assembled%s | message_count=%d",
                " for retry" if additional_messages else "",
                len(messages),
            )
            return messages
        except Exception as ex:
            logger.warning(
                "Failed to build role-based payload; falling back to simple. error=%s",
                ex,
            )
            return self._build_agent_payload(
                prompt,
                image_url,
                additional_messages,
            )

    @staticmethod
    async def _invoke_agent(
        agent: Agent,
        payload: Any,
        context: Any,
        agent_identifier: str,
        run_hooks: Optional[RunHooks[Any]] = None,
    ) -> str:
        """Asynchronous execution loop for Agent-driven workflows."""
        try:
            OpenAIService._reset_run_data_entry(context, agent_identifier)

            result = await Runner.run(
                agent,
                payload,
                context=context,
                max_turns=20,
                hooks=run_hooks,
            )

            OpenAIService._store_run_input_list(context, agent_identifier, result)
        except (InputGuardrailTripwireTriggered, OutputGuardrailTripwireTriggered):
            raise
        except Exception as err:
            raise RuntimeError(f"Agent execution failed: {err}") from err
        return result.final_output

    @staticmethod
    def _reset_run_data_entry(context: Any, agent_identifier: Optional[str]) -> None:
        data = getattr(context, "data", None)
        if not isinstance(data, dict):
            return
        run_data = data.setdefault("run_data", {})
        run_key = OpenAIService._build_run_key(agent_identifier, context)
        run_data[run_key] = []
        data["run_data"] = run_data

    @staticmethod
    def _store_run_input_list(context: Any, agent_identifier: Optional[str], result: Any) -> None:
        data = getattr(context, "data", None)
        if not isinstance(data, dict):
            return
        try:
            input_list = result.to_input_list()
        except Exception:
            input_list = None
        run_data = data.setdefault("run_data", {})
        run_key = OpenAIService._build_run_key(agent_identifier, context)
        entries = run_data.setdefault(run_key, [])
        if not isinstance(entries, list):
            entries = [] if entries is None else [entries]
        entries.append({"input_list": input_list})
        run_data[run_key] = entries
        data["run_data"] = run_data

    @staticmethod
    def _build_run_key(agent_identifier: Optional[str], context: Any) -> str:
        agent_key = agent_identifier or "unknown_agent"
        context_id = getattr(context, "context_id", None) or "unknown_context"
        return f"{agent_key}::{context_id}"

    @staticmethod
    def _get_run_data_entry(
        context: Any, agent_identifier: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        data = getattr(context, "data", None)
        if not isinstance(data, dict):
            return None
        run_data = data.get("run_data")
        if not isinstance(run_data, dict):
            return None
        run_key = OpenAIService._build_run_key(agent_identifier, context)
        entry = run_data.get(run_key)
        if isinstance(entry, list) and entry:
            return entry[-1]
        if isinstance(entry, dict):
            return entry
        if run_data:
            try:
                last_key = next(reversed(run_data))
                last_entry = run_data[last_key]
                if isinstance(last_entry, list) and last_entry:
                    return last_entry[-1]
                return last_entry
            except Exception:
                last_entry = next(iter(run_data.values()))
                if isinstance(last_entry, list) and last_entry:
                    return last_entry[-1]
                return last_entry
        return None

    @staticmethod
    def get_run_input_list(context: Any, agent_identifier: Optional[str]) -> Optional[Any]:
        entry = OpenAIService._get_run_data_entry(context, agent_identifier)
        if not isinstance(entry, dict):
            return None
        return entry.get("input_list")

    @staticmethod
    def did_run_use_file_search(context: Any, agent_identifier: Optional[str]) -> bool:
        input_list = OpenAIService.get_run_input_list(context, agent_identifier)
        if not isinstance(input_list, list):
            return False
        return any(
            isinstance(item, dict)
            and item.get("type", "").lower() == "file_search_call"
            for item in input_list
        )


    async def _assistant_flow(
        self,
        assistant_id: str,
        user_query: str,
        instructions: Optional[str],
        text_format: Optional[str],
        max_retries: int = 10,
        retry_delay: int = 5,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
    ) -> str:
        """Execute and poll a custom assistant thread for completion feedback."""
        try:
            thread = openai.beta.threads.create()
        except Exception as err:
            raise RuntimeError(f"Failed to create assistant thread: {err}") from err

        try:
            openai.beta.threads.messages.create(
                thread_id=thread.id, role="user", content=user_query
            )
        except Exception as err:
            raise RuntimeError(f"Failed to send user message: {err}") from err

        run_params: Dict[str, Any] = {
            "thread_id": thread.id,
            "assistant_id": assistant_id,
        }
        if instructions:
            run_params["instructions"] = instructions
        if text_format == "json":
            run_params["response_format"] = {"type": "json_object"}
        if temperature is not None:
            run_params["temperature"] = temperature
        if top_p is not None:
            run_params["top_p"] = top_p

        try:
            run = openai.beta.threads.runs.create(**run_params)
        except Exception as err:
            raise RuntimeError(f"Failed to start assistant run: {err}") from err

        return await self._poll_assistant(thread.id, run.id, max_retries, retry_delay)

    async def _poll_assistant(
        self, thread_id: str, run_id: str, max_retries: int, retry_delay: int
    ) -> str:
        """Polling loop with exponential backoff for assistant runs."""
        for attempt in range(max_retries):
            try:
                status = openai.beta.threads.runs.retrieve(
                    thread_id=thread_id, run_id=run_id
                )
            except Exception as err:
                raise RuntimeError(f"Failed to retrieve run status: {err}") from err
            if status.status == "completed":
                return await self._extract_assistant_response(thread_id)
            if status.status == "failed":
                error = status.last_error or "Unknown error"
                raise RuntimeError(f"Assistant run failed: {error}")
            await asyncio.sleep(retry_delay)
        raise RuntimeError("Assistant response timed out.")

    @staticmethod
    async def _extract_assistant_response(thread_id: str) -> Any:
        """Retrieve the first assistant message from a completed thread."""
        try:
            messages = openai.beta.threads.messages.list(thread_id=thread_id)
        except Exception as err:
            raise RuntimeError(f"Failed to list thread messages: {err}") from err
        for msg in messages:
            if msg.role == "assistant":
                # Support nested content structures
                content = msg.content
                if isinstance(content, list) and content:
                    return content[0].get("text", {}).get("value", "")
                return msg.content
        return "No assistant response found."

    async def _standard_flow(
        self,
        prompt: str,
        image_url: Optional[str],
        model: str,
        max_tokens: int,
        text_format: Optional[str],
        temperature: Optional[float],
        top_p: Optional[float],
    ) -> str:
        """Baseline chat completion with optional multimodal support."""
        messages = self._build_standard_messages(prompt, image_url)
        api_params: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            api_params["temperature"] = temperature
        if top_p is not None:
            api_params["top_p"] = top_p
        if text_format == "json":
            api_params["response_format"] = {"type": "json_object"}

        try:
            response = openai.chat.completions.create(**api_params)
            return response.choices[0].message.content
        except Exception as err:
            raise RuntimeError(f"OpenAI API error: {err}") from err

    @staticmethod
    def _build_standard_messages(
        prompt: str, image_url: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Unified message payload builder for chat completions."""
        if image_url:
            return [
                {"role": "user", "content": prompt},
                {
                    "role": "user",
                    "content": {"type": "image_url", "image_url": {"url": image_url}},
                },
            ]
        return [{"role": "user", "content": prompt}]


def to_openai_function_tool(t: Tool):
    return function_tool(
        t.func,
        name_override=t.name,
        description_override=t.description,
        strict_mode=t.strict_schema,
    )
