from agents import Agent, Tool
from agents.lifecycle import RunHooks
from agents.run_context import RunContextWrapper

from agent_core.config.logging_config import logger
from agent_core.services.model_context import ModelContext


class LocalToolLoggingHook(RunHooks[ModelContext]):
    async def on_tool_start(
        self,
        context: RunContextWrapper[ModelContext],
        agent: Agent[ModelContext],
        tool: Tool,
    ) -> None:
        agent_name = getattr(agent, "name", agent.__class__.__name__)
        tool_name = getattr(tool, "name", tool.__class__.__name__)
        logger.info(
            "Local tool started: agent=%s tool=%s qual_name=%s namespace=%s type=%s",
            agent_name,
            tool_name,
            getattr(tool, "qualified_name", None),
            getattr(tool, "namespace", None),
            type(tool).__name__,
        )

    async def on_tool_end(
        self,
        context: RunContextWrapper[ModelContext],
        agent: Agent[ModelContext],
        tool: Tool,
        result: str,
    ) -> None:
        agent_name = getattr(agent, "name", agent.__class__.__name__)
        tool_name = getattr(tool, "name", tool.__class__.__name__)
        logger.info(
            "Local tool finished: agent=%s tool=%s qual_name=%s namespace=%s type=%s",
            agent_name,
            tool_name,
            getattr(tool, "qualified_name", None),
            getattr(tool, "namespace", None),
            type(tool).__name__,
        )
