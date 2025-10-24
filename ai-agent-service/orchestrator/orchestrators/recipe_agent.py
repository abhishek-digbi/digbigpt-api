from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional, Literal

import asyncio
from agents import (
    trace,
    custom_span,
    get_current_trace,
)
from pydantic import BaseModel
from pydantic import Field

from agent_core.config.logging_config import logger
from agent_core.models.food_analysis import FoodAnalysisResult
from agent_core.services.adapters.openai_service import OpenAIService
from agent_core.services.ai_core_service import AiCoreService
from agent_core.services.model_context import ModelContext, BaseModelContext
from agent_core.services.prompt_management import langfuse_service
from orchestrator.orchestrators.base_ask_digbi_agent import AskDigbiBaseAgent
from orchestrator.orchestrators.nutrition_agent import NutritionAgent, extract_meal_info
from orchestrator.orchestrators.sensitivity_agent import SensitivityAgent
from tools import ToolService
from tools.definitions.common import analyze_user_recipe_query
from tools.definitions.recipes import get_recipes_tool
from tools.services.digbi_service import calculate_meal_scores
from tools.services.recipe_search import (
    GetRecipesOutput,
    fetch_recipes_for_request,
    Recipe,
)
from utils.meal_rating_utils import get_components, MealDetails
from utils.spoonacular_complex_search_models import SpoonacularComplexSearchRequest

GUIDELINE_MESSAGE = (
    "Choose recipes with ND Scores of 13 or higher. If you want to see how to improve the ND Score,"
    " click on the recipe to find suggested improvements below the ingredients. If you want to see the shopping"
    " or ingredients list for a recipe, visit the recipe page by clicking the button shown"
)

_NO_RECIPE_RESULTS_GUIDANCE_MESSAGE = {
    "role": "system",
    "content": (
        "No recipes were found for the previous query, maybe broaden query scope "
        "to increase the chances of getting recipes from Spoonacular. For example "
        "you may simplify the natural language query by using some more common synonyms of the words used in the query."
        "Prefer single word natural language queries. Use other parameters like includeIngredients, "
        "excludeIngredients, cuisine, excludeCuisine, diet etc to compensate for the shortening "
        "of the natural language query"
    ),
}


def _serialize_for_trace(data):
    if isinstance(data, BaseModel):
        return data.model_dump()
    if isinstance(data, dict):
        return {k: _serialize_for_trace(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_serialize_for_trace(v) for v in data]
    if isinstance(data, set):
        return sorted(list(data))
    return data


class AgentStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"


class RecipeAction(BaseModel):
    id: str
    title: str = Field(
        ..., description="The recipe title, title should be properly capitalized"
    )
    type: Literal["ROUTE"] = Field("ROUTE", description="This is a constant value")
    screen_name: Literal["Recipe"] = Field(
        "Recipe", description="This is a constant value"
    )
    improvement_suggestions: Optional[str] = Field(
        ..., description="suggestions to improve the nd score of the recipe, "
    )
    nd_score: int = Field(
        ...,
        description="A number between 1 to 14 representing the nutritional density score of "
        "the recipe",
    )


class RecipeNutritionData(BaseModel):
    nd_score: int = Field(
        ...,
        description="A number between 1 to 14 representing the nutritional density score of "
        "the recipe",
    )
    improvement_suggestions: Optional[str] = None


class RecipeAgentOutput(BaseModel):
    status: str
    message: str
    recipes: GetRecipesOutput


class RecipeAgent(AskDigbiBaseAgent):
    agent_id = "NORA_RECIPE_AGENT"

    def __init__(
        self,
        langfuse_service: langfuse_service,
        ai_core: AiCoreService,
        data_core: ToolService,
        nutrition_agent: NutritionAgent,
        sensitivity_agent: SensitivityAgent,
    ):
        self.langfuse_service = langfuse_service
        self.data_core = data_core
        self.ai_core = ai_core
        self.nutrition_agent = nutrition_agent
        self.sensitivity_agent = sensitivity_agent

    async def _retry_recipe_query_with_no_results_guidance(
        self,
        *,
        ctx: ModelContext,
        agent_kwargs: dict[str, object],
    ) -> Optional[RecipeAgentOutput]:
        run_input = OpenAIService.get_run_input_list(ctx, agent_kwargs.get("agent_id"))
        if not isinstance(run_input, list):
            logger.info(
                "Unable to retry recipe query analyzer; missing run input list | ctx=%s",
                ctx.context_id,
            )
            return None

        retry_messages = list(run_input)
        retry_messages.append(_NO_RECIPE_RESULTS_GUIDANCE_MESSAGE.copy())

        retry_kwargs = dict(agent_kwargs)
        retry_kwargs["input_messages"] = retry_messages

        logger.info(
            "Retrying recipe query analyzer with broaden-query guidance | ctx=%s",
            ctx.context_id,
        )
        return await self.ai_core.run_agent(**retry_kwargs)

    def _get_user_profile(self, vars_needed, user_token: str) -> Dict[str, Any]:
        return self.data_core.process_variables(user_token, vars_needed)

    async def get_recipes(
        self, request: SpoonacularComplexSearchRequest
    ) -> GetRecipesOutput:
        return await fetch_recipes_for_request(request)

    async def ask(self, ctx: ModelContext) -> dict[str, str]:

        logger.info("Asking Recipe Agent: user=%s qid=%s", ctx.user_token, ctx.query_id)

        if getattr(ctx, "data", None) is None:
            ctx.data = {}

        trace_ctx = None
        if get_current_trace() is None:
            trace_ctx = trace("ASK_DIGBI", group_id=ctx.query_id)
            trace_ctx.start(mark_as_current=True)

        meta = {"actions": []}

        query_agent_kwargs: dict[str, object] = {
            "agent_id": "RECIPE_AGENT",
            "ctx": ctx,
            "output_type": RecipeAgentOutput,
            "strict_json_schema": False,
            "tools": [analyze_user_recipe_query, get_recipes_tool],
            "tool_choice": "get_recipes_tool",
        }

        recipe_agent_output: RecipeAgentOutput = await self.ai_core.run_agent(
            **query_agent_kwargs
        )

        recipes_fetched = recipe_agent_output.recipes.recipes

        for attempt in range(2):
            if recipes_fetched:
                break
            recipe_agent_output = (
                await self._retry_recipe_query_with_no_results_guidance(
                    ctx=ctx,
                    agent_kwargs=query_agent_kwargs,
                )
            )
            recipes_fetched = recipe_agent_output.recipes.recipes

        with custom_span("nutrition_info") as span:
            nutrition_info = await self.get_nutrition_data(
                ctx.user_token,
                ctx.context_id,
                ctx.user_type,
                "",
                recipes_fetched,
                ctx
            )
            span.span_data.data["output"] = _serialize_for_trace(nutrition_info)

        with custom_span(
            "final_processing",
            data={
                "input": _serialize_for_trace(
                    {"recipes": recipes_fetched, "nutrition_info": nutrition_info}
                )
            },
        ) as span:
            if recipes_fetched and nutrition_info:

                for id, recipe_nutrition_data in nutrition_info.items():
                    nd_score = recipe_nutrition_data.nd_score
                    improvement_suggestions = (
                        recipe_nutrition_data.improvement_suggestions
                    )
                    rs = recipes_fetched[id]
                    rs.title = f"{rs.title} (ND score: {nd_score})"
                    action = RecipeAction(
                        title=rs.title,
                        id=rs.id,
                        nd_score=nd_score,
                        improvement_suggestions=improvement_suggestions,
                    )
                    meta["actions"].append(action.model_dump())

                formatter_ctx = BaseModelContext(
                    context_id=ctx.context_id,
                    data={"recipe_list": recipes_fetched.values()},
                    user_type=ctx.user_type
                )
                formatter_ctx.agent_statuses = ctx.agent_statuses
                formatted_recipes = await self.ai_core.run_agent(
                    "NORA_RECIPE_FORMATTER_AGENT",
                    formatter_ctx,
                    output_type=str,
                )
                final_message = recipe_agent_output.message
                if formatted_recipes:
                    final_message += f"\n {formatted_recipes}"
                    final_message += f"\n {GUIDELINE_MESSAGE}"
                    return {
                        "status": AgentStatus.SUCCESS,
                        "message": final_message,
                        "meta": meta,
                    }
            else:
                span.span_data.data["error"] = "Either recipes or nutrition data absent"

        if trace_ctx:
            trace_ctx.finish(reset_current=True)

        return {
            "status": AgentStatus.ERROR,
            "message": recipe_agent_output.message,
            "meta": meta,
        }

    @staticmethod
    def get_meal_details_from_analysis_json(meal_analysis_json) -> MealDetails:
        (
            food_type,
            meal_time,
            item_list,
            food_categories_dict_list,
            is_ultra_processed,
            extra_keys,
        ) = extract_meal_info(meal_analysis_json)
        threshold_data = {
            k: v
            for k, v in extra_keys.items()
            if isinstance(v, bool) and "Threshold:" in k
        }
        return MealDetails(
            food_type=food_type,
            meal_time=meal_time,
            item_list=item_list,
            food_categories=food_categories_dict_list,
            is_ultra_processed=is_ultra_processed,
            extra_keys=extra_keys,
            threshold_data=threshold_data,
        )

    async def get_nutrition_data(
        self,
        user_token: str,
        context_id: str,
        user_type: str,
        meal_type: str,
        recipes: Dict[str, Recipe],
            ctx
    ) -> dict[str, RecipeNutritionData]:

        logger.debug(f"{user_type}, {meal_type}, {context_id}, {user_token}")
        food_category_list = self.langfuse_service.generate_prompt(
            user_type, "food_category_list"
        )
        high_risk_traits = self._get_user_profile(["high_risk_traits"], user_token)

        tasks = []
        task_tracker = []

        for id, recipe in recipes.items():
            try:

                # Meal Description Analysis Task
                meal_ctx = BaseModelContext(
                    context_id=context_id,
                    user_type=user_type,
                    user_token=user_token,
                    data={
                        "user_description": recipe.description,
                        "meal_time": meal_type,
                        "food_category_list": food_category_list,
                    },
                )
                meal_ctx.agent_statuses = ctx.agent_statuses

                tasks.append(
                    asyncio.create_task(
                        self.ai_core.run_agent(
                            "MEAL_DESCRIPTION_UPDATE_WITHOUT_PHOTO_AGENT",
                            meal_ctx,
                            output_type=FoodAnalysisResult,
                            strict_json_schema=False,
                        )
                    )
                )
                task_tracker.append((id, "meal"))

                # Sensitivity Detection Task
                sensitivity_ctx = BaseModelContext(
                    context_id=context_id,
                    user_type=user_type,
                    user_token=user_token,
                    data={
                        "item_list": recipe.ingredients,
                        "user_description": recipe.description,
                    },
                )
                sensitivity_ctx.agent_statuses = ctx.agent_statuses
                tasks.append(
                    asyncio.create_task(self.sensitivity_agent.ask(sensitivity_ctx))
                )
                task_tracker.append((id, "sensitivity"))

                # ND Score Improvement Suggestion Task
                nutrition_ctx = BaseModelContext(
                    context_id=context_id, user_type=user_type, user_token=user_token
                )
                nutrition_ctx.agent_statuses = ctx.agent_statuses

                nutrition_ctx.query = (
                    "Suggest improvements for this recipe to improve its ND Score. "
                    "Provide alternative ingredients if need be.\n\n"
                    f"Title: {recipe.title}\n"
                    f"Summary: {recipe.description}\n"
                    f"Ingredients: {recipe.ingredients}"
                )
                tasks.append(
                    asyncio.create_task(self.nutrition_agent.ask(nutrition_ctx))
                )
                task_tracker.append((id, "improvement"))

            except Exception as e:
                logger.exception(f"Error creating tasks for recipe {id}: {e}")

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Organize results
        grouped_results = {key: {} for key in recipes.keys()}

        for (idx, task_type), result in zip(task_tracker, results):
            grouped_results[idx][task_type] = result

        try:
            nutrition_data = await self.process_task_results(
                user_token, grouped_results, high_risk_traits, recipes
            )
        except Exception as e:
            logger.error("Error processing recipe task results", e)
            nutrition_data = {}

        return nutrition_data

    async def process_task_results(
        self, user_token, grouped_results, high_risk_traits, recipes
    ):
        nd_scores_request: Dict[str, Any] = {}
        improvement_map: Dict[str, Optional[str]] = {}

        for id, recipe in recipes.items():

            results = grouped_results[id]

            # Handle meal analysis result
            meal_result = results["meal"]
            if isinstance(meal_result, Exception):
                logger.error(
                    f"Error processing meal analysis for recipe {id}: {meal_result}"
                )
                continue
            try:
                meal_json = meal_result.json()
                extracted_details = self.get_meal_details_from_analysis_json(meal_json)
            except Exception as e:
                logger.exception(f"Failed to parse meal analysis for recipe {id}: {e}")
                continue

            # Handle sensitivities
            sensitivities = []
            sensitivity_result = results["sensitivity"]
            if isinstance(sensitivity_result, Exception):
                logger.error(
                    f"Error processing sensitivity for recipe {id}: {sensitivity_result}"
                )
            else:
                sensitivities = sensitivity_result.get("sensitivities", [])

            # Handle improvement suggestions
            improvement_result = results["improvement"]
            if isinstance(improvement_result, Exception):
                logger.error(
                    f"Error processing improvement suggestions for recipe {id}: {improvement_result}"
                )
                improvement_map[id] = None
            else:
                improvement_map[id] = improvement_result

            # Build ND score request
            components = get_components(
                extracted_details, sensitivities, high_risk_traits
            )
            nd_scores_request[id] = {
                "components": components,
                "food_type": extracted_details.food_type,
                "cgm_meal_context": None,
            }

        nd_scores_result = await calculate_meal_scores(nd_scores_request, user_token)

        nutrition_data: Dict[str, RecipeNutritionData] = {}
        for id, recipe in recipes.items():
            nutrition_data[id] = RecipeNutritionData(
                nd_score=nd_scores_result[id]["score"],
                improvement_suggestions=improvement_map.get(id),
            )

        return nutrition_data
