import json

from agent_core.config.logging_config import logger
from agent_core.services.ai_core_service import AiCoreService
from orchestrator.orchestrators.base_ask_digbi_agent import AskDigbiBaseAgent
from agent_core.services.model_context import ModelContext
from agent_core.models.food_analysis import FoodAnalysisResult


class VisionAgent(AskDigbiBaseAgent):
    def __init__(self, ai_core: AiCoreService, langfuse):
        self.langfuse_service = langfuse
        self.ai = ai_core

    async def analyze_image_v2(self, ctx: ModelContext, request_context):
        """
        Analyze an image using the vision agent.

        Args:
            ctx: The model context
            request_context: The request context

        Returns:
            FoodAnalysisResult: The analysis result
        """
        food_category_list = self.langfuse_service.generate_prompt(ctx.user_type, "food_category_list")
        ctx.data["food_category_list"] = food_category_list
        request_context["agent_interactions"]["vision_agent"] = {"agent": self.__class__.__name__, "ctx.data": ctx.data}
        try:
            result = await self.ai.run_agent("MEAL_PHOTO_ANALYZER_AGENT", ctx, output_type=FoodAnalysisResult, strict_json_schema=False)
            request_context["agent_interactions"]["vision_agent"]["response"] = result.json() if result else None
            return result.json()
        except Exception as e:
            logger.error(f"Error in vision agent: {str(e)}")
            request_context["agent_interactions"]["vision_agent"]["error"] = str(e)
            raise

    async def ask(self, query: str, query_id="", user_type: str = "", user_token="", **kwargs):
        return
