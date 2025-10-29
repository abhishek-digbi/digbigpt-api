from typing import cast, List, Any, Optional

import asyncio
import copy
import json

import utils.env_loader
import utils.slack_util
from agent_core.config.logging_config import logger
from agent_core.services.ai_core_service import AiCoreService
from agent_core.services.model_context import ModelContext
from orchestrator.orchestrators.agent_models import AgentRequest, VideoRecommendationResult
from orchestrator.orchestrators.base_ask_digbi_agent import AskDigbiBaseAgent
from orchestrator.orchestrators.health_insights_agent import HealthInsightsAgent
from orchestrator.orchestrators.nutrition_agent import NutritionAgent
from orchestrator.orchestrators.personalization_agent import PersonalizationAgent
from orchestrator.orchestrators.recipe_agent import RecipeAgent
from orchestrator.orchestrators.support_agent import SupportAgent
from orchestrator.orchestrators.summarizer_agent import SummarizerAgent


class AskDigbiAgent(AskDigbiBaseAgent):
    def __init__(
        self,
        aicore: AiCoreService,
        health_insights_agent: HealthInsightsAgent,
        nutrition_agent: NutritionAgent,
        personalization_agent: PersonalizationAgent,
        support_agent: SupportAgent,
        summarizer_agent: SummarizerAgent,
        recipeAgent: RecipeAgent,
        terminal_agents: Optional[List[str]] = None
    ):
        self.support_agent = support_agent
        self.nutrition_agent = nutrition_agent
        self.health_insights_agent = health_insights_agent
        self.personalization_agent = personalization_agent
        self.summarizer_agent = summarizer_agent
        self.recipeAgent = recipeAgent
        self.ai = aicore
        self.terminal_agents = set(terminal_agents or [])

        therapy_assistant_id = utils.env_loader.get_ask_digbi_assistant_id()
        if not therapy_assistant_id:
            raise ValueError("Ask Digbi Assistant ID not found.")
        self.therapy_assistant_id = therapy_assistant_id

    async def ask(self, ctx: ModelContext) -> dict[str, object]:
        """
        Processes the user's query by preparing context and handling agent responses.
        """

        # Expose an async callable runner to tools to avoid serializing service objects
        async def _ai_runner(*args, **kwargs):
            return await self.ai.run_agent(*args, **kwargs)

        ctx.ai_runner = _ai_runner

        last_conversations = ctx.conversation_history.get("recent_messages", []) if ctx.conversation_history else []
        formatted_conversation = _format_conversation(last_conversations)

        # Get intent classifier response using the provided context and formatted conversation history
        response = await self.call_intent_classifier(ctx, formatted_conversation)
        # Handle the response and dispatch actions accordingly
        return await self.handle_intent_classifier_response(response, ctx)

    async def call_intent_classifier(self, ctx: ModelContext, formatted_conversation: str) -> AgentRequest:
        """
        Generates a prompt for the intent classifier and calls it.
        """
        logger.info(f"Asking Intent Classifier: user={ctx.user_token} qid={ctx.query_id}")
        ctx.data = {'query': ctx.query, 'recent_conversations': formatted_conversation}
        result = await self.ai.run_agent("ASK_DIGBI_INTENT_CLASSIFIER_AGENT", ctx, output_type=AgentRequest)
        if getattr(result, "language", None):
            ctx.language = result.language

        utils.slack_util.send_slack_askdigbi_log(
            f"*QUERY_ID:* {ctx.query_id} *[{ctx.user_type}] User_Token:* {ctx.user_token} ```QUERY: {ctx.query}\nINTENT CLASSIFIER: \n{result}```")
        logger.info(f"Response from intent classifier: {result}")
        return result

    async def handle_intent_classifier_response(self, agents_request: AgentRequest, ctx: ModelContext) -> dict[
        str, object]:
        """
        Processes the intent classifier's response and dispatches actions to the appropriate agent.
        Expected response JSON:
        {
          "actions": [
              {
                  "agent": "[agent_id or 'request_clarification' or 'reject']",
                  "message": "[A polite message to the user]"
              },
              ...
          ],
          "details": "[Any extra context]"
        }
        """

        actions = agents_request.actions
        details = agents_request.details
        if getattr(agents_request, "language", None):
            ctx.language = agents_request.language
        logger.info(f"Handling actions: {actions}, Details: {details}")

        if not actions:
            return {"status": "error", "message": "No actions provided in the response."}

        # If the action is a direct response or requires clarification
        first_action = actions[0]
        if first_action.action in ['request_clarification', 'reject', 'acknowledge', 'respond_directly']:
            return {
                "status": first_action.action,
                "message": first_action.message.strip(),
                "agent_statuses": ctx.agent_statuses,
            }

        # Process actions concurrently using asyncio.gather
        async def process_action(action):
            try:
                return await self._process_action(action, ctx)
            except Exception as e:
                logger.error(f"Error processing action: {e}")
                return {"status": "error", "message": f"Unhandled error: {str(e)}"}

        responses = await asyncio.gather(
            *[process_action(action) for action in actions]
        )

        action_response_pairs = list(zip(actions, responses))
        formatted_responses_for_summary: List[dict[str, Any]] = []
        for action, response in action_response_pairs:
            if isinstance(response, dict):
                response_copy = dict(response)
                response_copy.setdefault("agent", action.agent)
                response_copy.pop("meta", None)
                formatted_responses_for_summary.append(response_copy)
            else:
                formatted_responses_for_summary.append(
                    {"agent": action.agent, "response": response}
                )

        terminal_agent_involved = any(
            action.agent in self.terminal_agents for action in actions
        )

        combined_meta: dict[str, object] = {}

        def _merge_actions(value: object) -> None:
            if not value:
                return
            combined_actions = cast(List[Any], combined_meta.setdefault("actions", []))
            if isinstance(value, list):
                combined_actions.extend(value)
            else:
                combined_actions.append(value)

        def _coerce_meta(value: object) -> dict[str, object]:
            if not value:
                return {}
            if isinstance(value, dict):
                return dict(value)
            model_dump = getattr(value, "model_dump", None)
            if callable(model_dump):
                dumped = model_dump()
                if isinstance(dumped, dict):
                    return dumped
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                except json.JSONDecodeError:
                    logger.warning("Could not decode meta JSON string: %s", value)
                else:
                    if isinstance(parsed, dict):
                        return parsed
            return {}

        for response in responses:
            if isinstance(response, dict) and "meta" in response:
                meta = _coerce_meta(response.pop("meta"))
                _merge_actions(meta.pop("actions", None))
                combined_meta.update(meta)

        if terminal_agent_involved:
            summary_result = self._compose_terminal_agent_summary(action_response_pairs)
        else:
            summary_result = await self.summarize_response(
                formatted_responses_for_summary, ctx, details
            )
        summary_meta = summary_result.get("meta")
        if summary_meta:
            meta_copy = _coerce_meta(summary_meta)
            _merge_actions(meta_copy.pop("actions", None))
            combined_meta.update(meta_copy)

        return {
            "status": summary_result.get("status"),
            "message": summary_result.get("message"),
            "meta": combined_meta,
            "agent_statuses": ctx.agent_statuses,
        }

    async def _process_action(self, action, ctx: ModelContext) -> dict:
        """
        Processes an individual action and returns a response dictionary.
        For known agents, dispatches the action to the agent's 'ask' method.
        """
        agent_id = action.agent

        # Map agent names to their corresponding instances
        agent_registry = {
            "health_insights_agent": self.health_insights_agent,
            "personalization_agent": self.personalization_agent,
            "nutrition_agent": self.nutrition_agent,
            "support_agent": self.support_agent,
            "nora_recipe_agent": self.recipeAgent
        }
        # Create a shallow copy of ctx to avoid clobbering shared data when
        # multiple actions are processed concurrently.
        agent_ctx = copy.copy(ctx)

        # Ensure each action has its own data dictionary and user query.
        agent_ctx.data = dict(ctx.data or {})
        agent_ctx.query = action.revised_query if getattr(action, "revised_query", None) else ctx.query
        agent_ctx.data["user_query"] = agent_ctx.query

        agent = agent_registry.get(agent_id)
        if agent:
            agent_response = await agent.ask(agent_ctx)
            logger.info(f"Response from {agent_id}: {agent_response}")
            return agent_response
        else:
            return {"status": "rejected", "message": f"Error: Agent '{agent_id}' not found."}

    def _compose_terminal_agent_summary(self, action_response_pairs):
        """Return the first terminal agent response, otherwise fall back to a combined message."""
        for action, response in action_response_pairs:
            if action.agent in self.terminal_agents and isinstance(response, dict):
                return dict(response)

        messages = [
            response.get("message")
            for _, response in action_response_pairs
            if isinstance(response, dict) and response.get("message")
        ]
        status = next(
            (
                response.get("status")
                for _, response in action_response_pairs
                if isinstance(response, dict) and response.get("status")
            ),
            "success",
        )
        combined_message = "\n\n".join(messages).strip()
        return {"status": status, "message": combined_message}

    async def summarize_response(
        self,
        responses,
        ctx: ModelContext,
        details: str,
    ) -> dict[str, object]:
        """Summarize agent responses and return the summarizer payload."""
        if not isinstance(getattr(ctx, "data", None), dict):
            ctx.data = {}
        ctx.data["details"] = details
        ctx.data["formatted_responses"] = responses
        summary = await self.summarizer_agent.ask(ctx)

        if isinstance(summary, str):
            return {"status": "completed", "message": summary, "meta": {}}

        return summary


def _format_conversation(conversation_history: list) -> str:
    """
    Formats a conversation history list into a readable string.
    """
    sorted_history = sorted(conversation_history, key=lambda x: int(x['timestamp']))
    conversation_str = ""
    for msg in sorted_history:
        sender = msg.get('sender', 'Unknown').capitalize()
        conversation_str += f"{sender}: {msg.get('content', '')}\n"
    return conversation_str
