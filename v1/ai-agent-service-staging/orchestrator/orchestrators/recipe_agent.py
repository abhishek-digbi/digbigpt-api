from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Literal

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
from agent_core.services.ai_core_service import AiCoreService
from agent_core.services.model_context import ModelContext, BaseModelContext
from agent_core.services.prompt_management import langfuse_service
from tools import ToolService
from tools.services.digbi_service import calculate_meal_scores
from tools.services.spoonacular_service import (
    search_recipes_complex,
)
from orchestrator.orchestrators.base_ask_digbi_agent import AskDigbiBaseAgent
from orchestrator.orchestrators.nutrition_agent import NutritionAgent, extract_meal_info
from orchestrator.orchestrators.sensitivity_agent import SensitivityAgent
from orchestrator.orchestrators.recipe_agent_enhanced import RecipeAgentEnhanced
from utils.meal_rating_utils import get_components, MealDetails
from utils.recipe_agent_utils import get_recipe_conflicts, build_exclusion_set

SHOPPING_LIST_DIRECTION_MESSAGE = (
    "For shopping list or ingredients list visit the corresponding recipe details page by "
    "clicking on the buttons shown previously"
)

NO_RECIPE_AVAILABLE_MESSAGE = (
    "Sorry, we could not find any recipes that match your request and dietary needs. Try rephrasing your query,"
    " using different ingredients, or simplifying dietary restrictions if possible."
)

GUIDELINE_MESSAGE = (
    "Choose recipes with ND Scores of 13 or higher. If you want to see how to improve the ND Score,"
    " click on the recipe to find suggested improvements below the ingredients. If you want to see the shopping"
    " or ingredients list for a recipe, visit the recipe page by clicking the button shown"
)


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
    REJECTED = "rejected"
    REQUEST_CLARIFICATION = "request_clarification"


class RecipeQueryType(str, Enum):
    SHOW_RECIPES = "show_recipes"
    SHOPPING_LIST = "shopping_list_for_recipe"


class MealType(str, Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"
    OTHER = "other"


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


class RecipeIngredients(BaseModel):
    name: str
    amount: str
    unit: str


class RecipeNutritionData(BaseModel):
    nd_score: int = Field(
        ...,
        description="A number between 1 to 14 representing the nutritional density score of "
        "the recipe",
    )
    improvement_suggestions: Optional[str] = None


class RecipeClassifierOutput(BaseModel):
    status: AgentStatus = Field(
        ...,
        description="if the request was success or erred or rejected or requires "
        "clarification",
    )
    message: Optional[str] = Field(
        default=None,
        description="message prompting user if some further clarification or information "
        "is required",
    )
    query_type: RecipeQueryType = Field(
        ...,
        description="show_recipes or shopping_list_for_recipe",
    )
    meal_type: Optional[MealType] = Field(
        default=None, description="breakfast or lunch or dinner or snack or other"
    )
    max_carbs: Optional[int]
    dish_to_search: Optional[str] = Field(
        default="",
        description="dish name(s) or type(s)",
    )
    include_ingredients: Optional[str] = Field(
        default="",
        description="comma separated string of ingredients to be included if any such information is available",
    )
    exclude_ingredients: Optional[str] = Field(
        default="",
        description="list of ingredients to be excluded if any such information is available",
    )


class Recipe(BaseModel):
    id: str
    title: str
    description: str
    cook_time: int
    calories: float
    protein: float
    fat: float
    net_carbs: float
    ingredients: List[RecipeIngredients]


class GetRecipesOutput(BaseModel):
    conflicting_recipes: Dict[str, List[str]]
    filtered_recipes: Dict[str, Recipe]
    # Indicates a retry without meal type filter returned results
    fallback_no_meal_type: bool = False


class RecipeAgent(AskDigbiBaseAgent):
    agent_id = "NORA_RECIPE_AGENT"

    def __init__(
        self,
        langfuse_service: langfuse_service,
        ai_core: AiCoreService,
        data_core: ToolService,
        nutrition_agent: NutritionAgent,
        sensitivity_agent: SensitivityAgent,
        recipe_agent_enhanced: Optional[RecipeAgentEnhanced] = None,
    ):
        self.langfuse_service = langfuse_service
        self.data_core = data_core
        self.ai_core = ai_core
        self.nutrition_agent = nutrition_agent
        self.sensitivity_agent = sensitivity_agent
        self._recipe_agent_enhanced = recipe_agent_enhanced or RecipeAgentEnhanced(
            langfuse_service,
            ai_core,
            data_core,
            nutrition_agent,
            sensitivity_agent,
        )

    def _get_user_profile(self, vars_needed, user_token: str) -> Dict[str, Any]:
        return self.data_core.process_variables(user_token, vars_needed)

    @staticmethod
    async def _search_recipe_infos(
        search_term: str, base_params: Dict[str, Any], num_recipes: int = 3
    ) -> List[Dict[str, Any]]:
        params = {
            **{k: v for k, v in base_params.items() if v is not None},
            "query": search_term,
            "addRecipeNutrition": "true",
            "number": num_recipes,
        }

        res, _ = await search_recipes_complex(params)
        return res.get("results", [])

    async def get_recipes(
        self,
        max_carbs: int,
        exclusion_set,
        base_params,
        num_recipes: int,
        query: str | None = None,
    ) -> GetRecipesOutput:
        output = GetRecipesOutput(filtered_recipes={}, conflicting_recipes={})
        logger.info("Max carbs " + str(max_carbs))
        try:

            infos: List[Dict[str, Any]] = await self._search_recipe_infos(
                query, base_params, num_recipes
            )

            # Basic fallback: if nothing is found, retry without the meal type filter
            if not infos:
                logger.info("No recipes found; retrying without meal type filter")
                base_params_no_type = {**base_params, "type": None}
                infos = await self._search_recipe_infos(
                    query, base_params_no_type, num_recipes
                )
                if infos:
                    output.fallback_no_meal_type = True

            if not infos:
                logger.info("No recipes found even without meal type filter")
                return output

            for recipe in infos:
                conflicts = get_recipe_conflicts(recipe, exclusion_set)

                if conflicts:
                    output.conflicting_recipes[str(recipe.get("id"))] = conflicts
                    continue
                nutrients = {
                    n["name"]: n
                    for n in recipe.get("nutrition", {}).get("nutrients", [])
                }
                ingredients = [
                    RecipeIngredients(
                        name=ingredient_info.get("name"),
                        amount=f"{ingredient_info.get('amount')}",
                        unit=f"{ingredient_info.get('unit')}",
                    )
                    for ingredient_info in recipe.get("nutrition", {}).get(
                        "ingredients", []
                    )
                ]

                output.filtered_recipes[str(recipe.get("id"))] = Recipe(
                    **{
                        "id": str(recipe.get("id")),
                        "title": recipe.get("title"),
                        "description": recipe.get("summary"),
                        "cook_time": recipe.get("readyInMinutes"),
                        "calories": nutrients.get("Calories", {}).get("amount"),
                        "protein": nutrients.get("Protein", {}).get("amount"),
                        "fat": nutrients.get("Fat", {}).get("amount"),
                        "net_carbs": nutrients.get("Net Carbohydrates", {}).get(
                            "amount"
                        )
                        or nutrients.get("Carbohydrates", {}).get("amount"),
                        "ingredients": ingredients,
                    }
                )

        except Exception as e:
            logger.error("Exception during get recipes method call", e)

        logger.info(
            f"returning {len(output.filtered_recipes)} filtered recipes and "
            f"{len(output.conflicting_recipes)} conflicting recipes"
        )
        return output

    async def ask(self, ctx: ModelContext) -> dict[str, str]:

        logger.info("Asking Recipe Agent: user=%s qid=%s", ctx.user_token, ctx.query_id)

        if getattr(ctx, "data", None) is None:
            ctx.data = {}

        user_type = (getattr(ctx, "user_type", "") or "").strip().lower()
        if user_type == "alpha":
            logger.info("Routing alpha user to recipe agent enhanced")
            return await self._recipe_agent_enhanced.ask(ctx)

        trace_ctx = None
        if get_current_trace() is None:
            trace_ctx = trace("ASK_DIGBI", group_id=ctx.query_id)
            trace_ctx.start(mark_as_current=True)

        with custom_span("RECIPE_CLASSIFIER_STEP") as span:
            recipe_classifier_output: RecipeClassifierOutput = await self.ai_core.run_agent(
                "NORA_RECIPE_AGENT",
                ctx,
                output_type=RecipeClassifierOutput,
                strict_json_schema=False
            )

        if recipe_classifier_output.status != AgentStatus.SUCCESS:
            return {
                "status": recipe_classifier_output.status,
                "message": recipe_classifier_output.message,
                "meta": {},
            }

        if recipe_classifier_output.query_type == RecipeQueryType.SHOPPING_LIST:
            return {
                "status": AgentStatus.SUCCESS,
                "message": SHOPPING_LIST_DIRECTION_MESSAGE,
                "meta": {},
            }

        profile = self._get_user_profile(
            [
                "dietary_restrictions",
                "allergies_and_intolerances",
                "ingredients_to_avoid",
                "coach_added_exclusions",
            ],
            ctx.user_token,
        )
        exclusion_set = build_exclusion_set(profile)
        exclude_ingredients = ",".join(sorted(exclusion_set)) or ""
        base_params = {
            "type": recipe_classifier_output.meal_type,
            "diet": ",".join(profile.get("dietary_restrictions", [])) or "",
            "intolerances": ",".join(profile.get("allergies_and_intolerances", []))
            or None,
            "excludeIngredients": f"{exclude_ingredients},{recipe_classifier_output.exclude_ingredients}".strip(
                ","
            ),
            "includeIngredients": recipe_classifier_output.include_ingredients or "",
            "maxCarbs": recipe_classifier_output.max_carbs,
        }

        meta = {"actions": []}

        with custom_span("get_recipes") as span:
            span.span_data.data["input"] = _serialize_for_trace({"base_params": base_params,
                                                                 "num_recipes": 3,
                                                                 "query": recipe_classifier_output.dish_to_search})
            recipes_fetched = await self.get_recipes(
                recipe_classifier_output.max_carbs,
                exclusion_set,
                base_params,
                3,
                recipe_classifier_output.dish_to_search,
            )
            span.span_data.data["output"] = _serialize_for_trace(recipes_fetched)
            # Trace explicit fallback usage information for observability
            if getattr(recipes_fetched, "fallback_no_meal_type", False):
                span.span_data.data["fallback"] = {
                    "used": True,
                    "strategy": "drop_meal_type",
                    "initial_meal_type": getattr(
                        recipe_classifier_output.meal_type, "value", recipe_classifier_output.meal_type
                    ),
                    "reason": "no_results_with_meal_type",
                }

        with custom_span("nutrition_info") as span:
            nutrition_info = await self.get_nutrition_data(
                ctx.user_token,
                ctx.context_id,
                ctx.user_type,
                recipe_classifier_output.meal_type,
                recipes_fetched.filtered_recipes,
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
            if recipes_fetched.filtered_recipes and nutrition_info:

                for id, recipe_nutrition_data in nutrition_info.items():
                    nd_score = recipe_nutrition_data.nd_score
                    improvement_suggestions = (
                        recipe_nutrition_data.improvement_suggestions
                    )
                    rs = recipes_fetched.filtered_recipes[id]
                    rs.title = f"{rs.title} (ND score: {nd_score})"
                    action = RecipeAction(
                        title=rs.title,
                        id=rs.id,
                        nd_score=nd_score,
                        improvement_suggestions=improvement_suggestions,
                    )
                    meta["actions"].append(action.model_dump())

                message = await self.ai_core.run_agent(
                    "NORA_RECIPE_FORMATTER_AGENT",
                    BaseModelContext(
                        context_id=ctx.context_id,
                        data={"recipe_list": recipes_fetched.filtered_recipes.values()},
                        user_type=ctx.user_type
                    ),
                    output_type=str,
                )
                if message:
                    # Prepend a brief note if results came from fallback (no meal type filter)
                    fallback_note = None
                    if recipes_fetched.fallback_no_meal_type:
                        mt = recipe_classifier_output.meal_type
                        meal_label = getattr(mt, "value", mt) if mt else None
                        if meal_label:
                            fallback_note = (
                                f"Couldn't find {meal_label}-specific recipes. Showing general recipes instead."
                            )
                        else:
                            fallback_note = (
                                "Couldn't find meal-type-specific recipes. Showing general recipes instead."
                            )

                    final_message = ""
                    if fallback_note:
                        final_message += fallback_note + "\n\n"
                    final_message += message
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
            "message": NO_RECIPE_AVAILABLE_MESSAGE,
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
                tasks.append(
                    asyncio.create_task(self.sensitivity_agent.ask(sensitivity_ctx))
                )
                task_tracker.append((id, "sensitivity"))

                # ND Score Improvement Suggestion Task
                nutrition_ctx = BaseModelContext(
                    context_id=context_id, user_type=user_type, user_token=user_token
                )
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
