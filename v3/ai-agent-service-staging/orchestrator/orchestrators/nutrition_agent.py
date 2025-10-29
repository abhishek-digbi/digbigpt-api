import json
import re

import asyncio
from agents import RunContextWrapper, Agent, TContext

import utils.env_loader
from agent_core.config.logging_config import logger
from agent_core.models.food_analysis import FoodAnalysisResult
from agent_core.services.ai_core_service import AiCoreService
from agent_core.services.model_context import ModelContext
from agent_core.services.prompt_management.langfuse_service import LangFuseService
from tools import ToolService
from tools.services.digbi_service import (
    get_nd_score_infractions,
    send_meal_rating_response,
    calculate_meal_score,
)
from orchestrator.api.services.response_generator import generate_meal_rating_response
from orchestrator.orchestrators.base_ask_digbi_agent import AskDigbiBaseAgent
from orchestrator.orchestrators.personalization_agent import PersonalizationAgent
from orchestrator.orchestrators.sensitivity_agent import SensitivityAgent
from orchestrator.orchestrators.kb_retry import maybe_retry_with_kb_guidance
from orchestrator.services.meal_rating_log_entry import (
    MealRatingLogEntry,
    MealRatingLogService,
)
from utils.cache import cache as global_cache
from utils.db import DBClient
from utils.slack_util import send_meal_rating_message
from utils.json_util import ensure_dict
import time
from tools.definitions.common import get_meal_feedback


CACHE_TIMEOUT_INFRACTIONS = 86400  # 1 day


def process_user_context(user_context):
    """
    Process the user context to extract key details like genetic traits, dietary restrictions, and sensitivities.

    :param user_context: Dictionary containing user-reported context data.
    :return: Tuple of extracted details: high_risk_traits, moderate_risk_traits, allergies_and_intolerances,
             exclusions, dietary_restrictions, ingredients_to_avoid
    """
    # Extract genetic traits
    genetic_traits = user_context.get("genetic_traits", {})
    high_risk_traits = genetic_traits.get("high_risk", [])
    moderate_risk_traits = genetic_traits.get("moderate_risk", [])

    # Extract dietary restrictions
    restrictions = user_context.get("user_reported_restrictions", {})
    allergies_and_intolerances = restrictions.get("allergies_and_intolerances", [])
    exclusions = restrictions.get("exclusions", [])
    dietary_restrictions = restrictions.get("dietary_restrictions", [])
    ingredients_to_avoid = restrictions.get("ingredients_to_avoid", [])

    return (
        high_risk_traits,
        moderate_risk_traits,
        allergies_and_intolerances,
        exclusions,
        dietary_restrictions,
        ingredients_to_avoid,
    )


def extract_meal_info(meal_desc):
    """
    Extract information about the meal from a structured meal description.

    :param meal_desc: JSON-like string containing meal information.
    :return: Tuple (food_type, ingredients, meal_desc_json)
    """
    # Ensure meal_desc is a string
    if not isinstance(meal_desc, str):
        raise TypeError("Input must be a string")

    # Remove markdown code block markers (e.g., ``` or ```json)
    # This regex removes any occurrence of triple backticks (with optional "json")
    meal_desc = re.sub(r"```(?:json)?", "", meal_desc, flags=re.IGNORECASE)

    # Remove inline comments.
    # This regex removes any content following a '#' that is not inside a JSON string.
    # Here we assume comments are placed after valid JSON content on the same line.
    meal_desc = re.sub(r"\s*#.*$", "", meal_desc, flags=re.MULTILINE)

    # Remove trailing commas before a closing bracket/brace to help JSON decoding
    meal_desc = re.sub(r",\s*([}\]])", r"\1", meal_desc)

    # Strip any extra whitespace
    meal_desc = meal_desc.strip()

    # Check if the string is now empty
    if not meal_desc:
        raise TypeError("Invalid meal description format: Empty string after cleaning.")

    # Parse JSON
    try:
        meal_dict = json.loads(meal_desc)
    except json.JSONDecodeError as e:
        raise TypeError(f"Invalid meal description format: {e}")

    # Extract fields
    food_type = meal_dict.get("foodType", None)
    meal_time = meal_dict.get("mealTime", None)
    ingredients = meal_dict.get("ingredients", [])
    food_categories = meal_dict.get("foodCategories", [])

    ultra_processed = meal_dict.get("ultraProcessed", False)

    # Gather any other top-level keys (e.g., threshold keys) into a dictionary
    # This way, we don't lose them if they're not part of the usual set.
    extra_keys = {}
    standard_keys = {
        "foodCategories",
        "foodType",
        "mealTime",
        "ingredients",
        "ultraProcessed",
    }
    for key, value in meal_dict.items():
        if key not in standard_keys:
            extra_keys[key] = value

    # Convert food categories into a list of dicts for processing
    meal_desc_json = [
        {"foodCategory": category.get("foodCategory")}
        for category in food_categories
        if "foodCategory" in category
    ]

    return (
        food_type,
        meal_time,
        ingredients,
        meal_desc_json,
        ultra_processed,
        extra_keys,
    )


class NutritionAgent(AskDigbiBaseAgent):
    def __init__(
        self,
        aicore: AiCoreService,
        langfuse: LangFuseService,
        sensitivity_agent: SensitivityAgent,
        personalization_agent: PersonalizationAgent,
        data_core: ToolService,
        db_client: DBClient,
    ):
        self.sensitivity_agent = sensitivity_agent
        self.personalization_agent = personalization_agent
        self.langfuse_service = langfuse
        self.cache = global_cache
        self.ai = aicore
        self.data_core = data_core
        self.db = db_client

        meal_rating_assistant_id = utils.env_loader.get_meal_rating_assistant_id()
        if not meal_rating_assistant_id:
            raise ValueError(f"Meal Rating Assistant ID not found.")

        self.meal_rating_assistant_id = meal_rating_assistant_id

    async def calculate_nd_score(self, ctx: ModelContext, request_context):

        request_context["agent_interactions"]["calculate_nd_score"] = {
            "agent": self.__class__.__name__,
            "ctx.data": ctx.data,
        }

        score = 14
        components = []
        nd_titles = []
        suggestions = []

        # Define food categories with regex patterns
        food_categories = {
            "caffeine": r"(Beverage - Level 1|Tea|Coffee|Herbal Teas)",
            "gluten": r"Gluten Rich Grains",
            "alcohol": r"Alcohol",
            "high_glucose_carbs": r"Processed Carbs|High Glucose Carbs|^Milk - Grain based|^Starches - (Grains|Beans and Legumes)",
            "high_glucose_fruits": r"Fruits - Group 2",
            "low_glucose_fruits": r"Fruits - Group 1",
            "no_vegetables": r"Vegetables - Group 1|Vegetables - Group 2|Vegetables - Group 3",
            "processed_additives": r"^Condiment - Level 2|Processed with Additives|^Beverage - Level 2",
            "starch_rich": r"Vegetables - Group 3|^Starches - Vegetables",
            "sugar_substitutes": r"Sweeteners|Desserts|^Beverage - Level 2",
            "lactose_sensitive": r"Dairy|Probiotics - Soft Cheeses",
            "inflammatory_nuts_seeds": r"Fats - (Nuts|Seeds)|Milk - Nut based",
            "probiotics": r"Probiotics -|Fermented Foods",
        }

        try:
            infractions = await self.fetch_infractions()
            # Proceed with using 'infractions'
        except Exception as e:
            print(f"Error fetching infractions: {e}")
            raise

        # Function to check if any food category matches in the meal description
        def category_present(category):
            return any(
                re.search(
                    food_categories[category], item["foodCategory"], re.IGNORECASE
                )
                for item in ctx.data["meal_desc"]
            )

        # Set default empty lists if high_risk_traits or moderate_risk_traits is None
        high_risk_traits = ctx.data["high_risk_traits"] or []
        # moderate_risk_traits = moderate_risk_traits or []

        pattern_caffeine = re.compile(r"caffeine", re.IGNORECASE)
        pattern_gluten = re.compile(r"gluten", re.IGNORECASE)
        pattern_lactose = re.compile(r"lactose", re.IGNORECASE)

        # Deduct points for these sensitivities only if the user has high risk, not moderate risk
        has_caffeine_sensitivity = any(
            pattern_caffeine.search(trait) for trait in high_risk_traits
        )
        has_gluten_sensitivity = any(
            pattern_gluten.search(trait) for trait in high_risk_traits
        )
        has_lactose_sensitivity = any(
            pattern_lactose.search(trait) for trait in high_risk_traits
        )

        sensitivities_list = await self.sensitivity_agent.identify_sensitivities(
            ctx, request_context
        )
        request_context["agent_interactions"]["calculate_nd_score"][
            "sensitivities_list"
        ] = sensitivities_list
        logger.info(f"Sensitivities list: {sensitivities_list}")

        for key, value in ctx.data["threshold_data"].items():
            if value is True:
                match key:
                    case _ if "Vegetables - Group 3" in key:
                        score -= 1
                        components.append("GROUP_3_VEGGIES")
                        nd_titles.append(
                            next(
                                (
                                    item["title"]
                                    for category in infractions.values()
                                    for item in category
                                    if item["code"] == "GROUP_3_VEGGIES"
                                ),
                                "",
                            )
                        )
                        suggestions.append(
                            "Do not eat more than 1/8 cup.Occasionally have cooked and cooled starchy vegetables (such as potatoes, sweet potatoes, green peas, plantains, or yams) for resistant starch in place of other Group 3 vegetables."
                        )
                    case _ if "Fruits - Group 1" in key:
                        score -= 1
                        components.append("GROUP_1_FRUIT")
                        nd_titles.append(
                            next(
                                (
                                    item["title"]
                                    for category in infractions.values()
                                    for item in category
                                    if item["code"] == "GROUP_1_FRUIT"
                                ),
                                "",
                            )
                        )
                        suggestions.append("Do not eat more than 1/4 cup per day")
                    case _ if "Fruits - Group 2" in key:
                        score -= 1
                        components.append("GROUP_2_FRUIT")
                        nd_titles.append(
                            next(
                                (
                                    item["title"]
                                    for category in infractions.values()
                                    for item in category
                                    if item["code"] == "GROUP_2_FRUIT"
                                ),
                                "",
                            )
                        )
                        suggestions.append(
                            "Limit high glucose fruit to 1/4 cup per week. Opt for lower glucose Group 1 Fruits (described in knowledgebase)."
                        )
                    case _ if "Fats - Nuts" in key:
                        score -= 1
                        components.append("NUTS_SEEDS_DRIED_FRUIT")
                        nd_titles.append(
                            next(
                                (
                                    item["title"]
                                    for category in infractions.values()
                                    for item in category
                                    if item["code"] == "NUTS_SEEDS_DRIED_FRUIT"
                                ),
                                "",
                            )
                        )
                        suggestions.append(
                            "Limit the quantity of nuts to no more than 1 Tbsp per meal"
                        )
                    case _ if "Fats - Seeds" in key:
                        score -= 1
                        components.append("NUTS_SEEDS_DRIED_FRUIT")
                        nd_titles.append(
                            next(
                                (
                                    item["title"]
                                    for category in infractions.values()
                                    for item in category
                                    if item["code"] == "NUTS_SEEDS_DRIED_FRUIT"
                                ),
                                "",
                            )
                        )
                        suggestions.append(
                            "Limit the quantity of seeds to no more than 1 Tbsp per meal"
                        )

        # Insulin Resistance deductions
        if category_present("high_glucose_carbs"):
            score -= 2
            components.append("PROCESSED_CARBS")
            nd_titles.append(
                next(
                    (
                        item["title"]
                        for category in infractions.values()
                        for item in category
                        if item["code"] == "PROCESSED_CARBS"
                    ),
                    "",
                )
            )
            suggestions.append("Avoid High Glucose Carbohydrate food.")

        if category_present("processed_additives") or ctx.data["is_ultra_processed"]:
            score -= 2
            components.append("PROCESSED_CHEMICALS")
            nd_titles.append(
                next(
                    (
                        item["title"]
                        for category in infractions.values()
                        for item in category
                        if item["code"] == "PROCESSED_CHEMICALS"
                    ),
                    "",
                )
            )
            suggestions.append(
                "Ultra-processed food with additives, preservatives, and refined ingredients are hyperpalatable—they can intensify cravings. Try swapping to a whole-food option to feel your best!"
            )

        if category_present("sugar_substitutes"):
            score -= 1
            components.append("SUGARS_SUBSTITUTES")
            nd_titles.append(
                next(
                    (
                        item["title"]
                        for category in infractions.values()
                        for item in category
                        if item["code"] == "SUGARS_SUBSTITUTES"
                    ),
                    "",
                )
            )
            suggestions.append(
                "Avoid sugary items or synthetic sweeteners, opt for natural sweetness from fruits like berries."
            )

        # Lactose sensitivity check
        if "lactose" in sensitivities_list and has_lactose_sensitivity:
            score -= 1
            components.append("LACTOSE")
            nd_titles.append(
                next(
                    (
                        item["title"]
                        for category in infractions.values()
                        for item in category
                        if item["code"] == "LACTOSE"
                    ),
                    "",
                )
            )
            suggestions.append(
                "Avoid dairy products and use lactose-free or plant-based alternatives.Fermented dairy like yogurt and kefir are good too."
            )

        if not category_present("probiotics"):
            score -= 1
            components.append("NO_PROBIOTICS")
            nd_titles.append(
                next(
                    (
                        item["title"]
                        for category in infractions.values()
                        for item in category
                        if item["code"] == "NO_PROBIOTICS"
                    ),
                    "",
                )
            )
            suggestions.append(
                "Incorporate probiotics like yogurt, fermented vegetables, or hard cheeses for a healthier gut."
            )

        # Caffeine sensitivity check
        if "caffeine" in sensitivities_list and has_caffeine_sensitivity:
            score -= 1
            components.append("CAFFEINE")
            nd_titles.append(
                next(
                    (
                        item["title"]
                        for category in infractions.values()
                        for item in category
                        if item["code"] == "CAFFEINE"
                    ),
                    "",
                )
            )
            suggestions.append("Reduce caffeine intake due to your sensitivity.")

        # Gluten sensitivity check
        if "gluten" in sensitivities_list and has_gluten_sensitivity:
            score -= 1
            components.append("GLUTEN")
            nd_titles.append(
                next(
                    (
                        item["title"]
                        for category in infractions.values()
                        for item in category
                        if item["code"] == "GLUTEN"
                    ),
                    "",
                )
            )
            suggestions.append(
                "Avoid gluten-containing foods due to your sensitivity. Try gluten-free alternatives."
            )

        # Alcohol deduction
        if category_present("alcohol"):
            score -= 2
            components.append("ALCOHOL")
            nd_titles.append(
                next(
                    (
                        item["title"]
                        for category in infractions.values()
                        for item in category
                        if item["code"] == "ALCOHOL"
                    ),
                    "",
                )
            )
            suggestions.append(
                "Reduce or eliminate alcohol from your diet for better health outcomes."
            )

        # Adjust deductions based on the type of meal
        vegetables_count = sum(
            1
            for item in ctx.data["meal_desc"]
            if re.search(
                food_categories["no_vegetables"], item["foodCategory"], re.IGNORECASE
            )
        )
        if (
            vegetables_count < 2
            and ctx.data["food_type"] is not None
            and ctx.data["food_type"].lower() == "meal"
        ):
            score -= 1
            components.append("LESS_THAN_2_TYPES_OF_VEGGIES")
            nd_titles.append(
                next(
                    (
                        item["title"]
                        for category in infractions.values()
                        for item in category
                        if item["code"] == "LESS_THAN_2_TYPES_OF_VEGGIES"
                    ),
                    "",
                )
            )
            suggestions.append(
                "Add more variety of vegetables to your meal. Aim for at least two different types."
            )

        if ctx.data["cgm_bad_peak"]:
            score -= 1
            components.append("BAD_PEAK")
            nd_titles.append(
                next(
                    (
                        item["title"]
                        for category in infractions.values()
                        for item in category
                        if item["code"] == "BAD_PEAK"
                    ),
                    "",
                )
            )
            suggestions.append(
                "Avoid foods that cause a spike in your blood sugar levels."
            )

        if ctx.data["cgm_bad_recovery"]:
            score -= 1
            components.append("BAD_RECOVERY")
            nd_titles.append(
                next(
                    (
                        item["title"]
                        for category in infractions.values()
                        for item in category
                        if item["code"] == "BAD_RECOVERY"
                    ),
                    "",
                )
            )
            suggestions.append(
                "Avoid foods that cause a slow recovery in your blood sugar levels."
            )

        request_context["agent_interactions"]["calculate_nd_score"]["response"] = {
            "score": score,
            "components": components,
            "suggestions": suggestions,
            "nd_titles": nd_titles,
        }
        return score, components, suggestions, nd_titles

    async def update_wdesc_v2(self, ctx: ModelContext, request_context):
        """
        Update the food description with additional details.

        Args:
            ctx: The model context
            request_context: The request context

        Returns:
            FoodAnalysisResult: The updated analysis result
        """
        food_category_list = self.langfuse_service.generate_prompt(
            ctx.user_type, "food_category_list"
        )
        ctx.data["food_category_list"] = food_category_list

        request_context["agent_interactions"]["update_wdesc_v2"] = {
            "agent": self.__class__.__name__,
            "ctx.data": ctx.data,
        }

        try:
            if ctx.data.get("init_list"):
                result = await self.ai.run_agent(
                    "MEAL_DESCRIPTION_UPDATE_WITH_PHOTO_AGENT",
                    ctx,
                    output_type=FoodAnalysisResult,
                    strict_json_schema=False,
                )
            else:
                result = await self.ai.run_agent(
                    "MEAL_DESCRIPTION_UPDATE_WITHOUT_PHOTO_AGENT",
                    ctx,
                    output_type=FoodAnalysisResult,
                    strict_json_schema=False,
                )

            request_context["agent_interactions"]["update_wdesc_v2"]["response"] = (
                result.json() if result else None
            )
            return result.json()

        except Exception as e:
            logger.error(f"Error in update_wdesc_v2: {str(e)}")
            request_context["agent_interactions"]["update_wdesc_v2"]["error"] = str(e)
            raise

    async def ask(self, ctx: ModelContext):
        logger.info(f"Asking Nutrition Agent: user={ctx.user_token} qid={ctx.query_id}")
        # Ensure mutable data bag is present
        if getattr(ctx, "data", None) is None:
            ctx.data = {}

        agent_kwargs: dict[str, object] = {
            "agent_id": "ASK_DIGBI_NUTRITION_AGENT",
            "ctx": ctx,
        }

        result = await self.ai.run_agent(**agent_kwargs)

        result = await maybe_retry_with_kb_guidance(
            ai=self.ai,
            ctx=ctx,
            agent_kwargs=agent_kwargs,
            result=result,
            logger=logger,
            log_message="Retrying nutrition agent with knowledge base guidance | ctx=%s",
            log_args=(ctx.context_id,),
        )

        return result

    async def fetch_infractions(self):
        cache_key = "infractions_data"

        # Check if data is available in cache
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return json.loads(cached_data)

        # Fetch data if not in cache
        result_data = await get_nd_score_infractions()

        # Check if the response is None or missing the "result" key
        if result_data is None:
            raise Exception("No data received from get_nd_score_infractions().")

        # Store result in cache with an expiration time (e.g., 1 hour)
        self.cache.set(cache_key, json.dumps(result_data), ex=CACHE_TIMEOUT_INFRACTIONS)

        return result_data

    def access_user_health_card(self, request_context):
        data_needed = [
            "high_risk_traits",
            "allergies_and_intolerances",
            "coach_added_exclusions",
            "dietary_restrictions",
            "ingredients_to_avoid",
        ]
        snapshot_data = self.data_core.process_variables(
            request_context["payload"]["user_info"]["user_token"], data_needed
        )
        request_context["user_data_used"] = {"user_data_used": snapshot_data}
        return [snapshot_data.get(data, []) for data in data_needed]

    async def generate_feedback(
        self, ctx: ModelContext, request_context, askMealEvaluation: bool = False
    ):
        """
        Generate feedback for the user based on nutritional data and context.

        :param request_context:
        :param ctx:
        :return: Tuple containing assistant feedback, input tokens, and output tokens.
        """
        request_context["agent_interactions"]["generate_feedback"] = {
            "agent": self.__class__.__name__,
            "ctx.data": ctx.data,
        }
        # Directly await the async run_agent method

        agent_to_call = (
            "ASK_EVALUATION_AGENT" if askMealEvaluation else "MEAL_FEEDBACK_AGENT"
        )

        result = await self.ai.run_agent(agent_to_call, ctx)
        request_context["agent_interactions"]["generate_feedback"][
            "assistant_response"
        ] = result
        return result

    async def finalize_feedback_task(self, request_context, ctx: ModelContext):
        (
            image_id,
            image_url,
            description,
            user_type,
            user_token,
            cgm_meal_context,
            askMealEvaluation,
        ) = get_fields(request_context["payload"])
        cgm_bad_peak, cgm_bad_recovery = cgm_meal_context.get(
            "cgm_bad_peak", None
        ), cgm_meal_context.get("cgm_bad_recovery", None)
        meal_desc = request_context["updated_analysis_result"].strip()

        try:
            (
                high_risk_traits,
                allergies,
                exclusions,
                dietary_restrictions,
                ingredients_to_avoid,
            ) = self.access_user_health_card(request_context)
            (
                food_type,
                meal_time,
                item_list,
                meal_desc_json,
                is_ultra_processed,
                extra_keys,
            ) = extract_meal_info(meal_desc)
            # Filter extra_keys for the recognized threshold entries
            threshold_data = {}
            for k, v in extra_keys.items():
                # e.g. check if "Threshold" in k
                # Also verify it's a boolean
                if isinstance(v, bool) and "Threshold:" in k:
                    threshold_data[k] = v
            ctx.data.update(
                {
                    "meal_desc": meal_desc_json,
                    "user_description": description,
                    "item_list": item_list,
                    "high_risk_traits": high_risk_traits,
                    "food_type": food_type,
                    "is_ultra_processed": is_ultra_processed,
                    "cgm_bad_peak": cgm_bad_peak,
                    "cgm_bad_recovery": cgm_bad_recovery,
                    "threshold_data": threshold_data,
                }
            )
            if askMealEvaluation:
                desc = ensure_dict(description)
                ctx.data.update(
                    {
                        "category": desc.get("category"),
                        "upc": desc.get("upc"),
                        "title": desc.get("title"),
                        "ingredients": desc.get("ingredients"),
                        "brand": desc.get("brand"),
                        "ingredientList": desc.get("ingredientList"),
                        "ingredientCount": desc.get("ingredientCount"),
                        "badges": desc.get("badges"),
                        "importantBadges": desc.get("importantBadges"),
                        "nutrition": desc.get("nutrition"),
                    }
                )
            if food_type != "no_food":
                nd_score, components, suggestions, nd_titles = (
                    await self.calculate_nd_score(ctx, request_context)
                )

                meal_score_response = await calculate_meal_score(
                    {
                        "components": components,
                        "cgm_meal_context": cgm_meal_context,
                        "food_type": food_type,
                    },
                    user_token,
                )
                nd_score = meal_score_response["score"]
                request_context["calculate_nd_score_output"] = (
                    nd_score,
                    components,
                    suggestions,
                    nd_titles,
                )
            else:
                meal_score_response = None
                nd_score = None
                components = None
                nd_titles = None
                suggestions = None
            user_info = get_user_info(
                allergies,
                dietary_restrictions,
                exclusions,
                food_type,
                high_risk_traits,
                ingredients_to_avoid,
                item_list,
                meal_desc_json,
                nd_score,
                nd_titles,
                cgm_bad_peak,
                cgm_bad_recovery,
            )

            ctx.data.update({"user_information": user_info})
            # Await the async generate_feedback method
            assistant_response = await self.generate_feedback(
                ctx, request_context, askMealEvaluation
            )

            request_context["final_feedback"] = assistant_response

            send_meal_rating_message(
                channel=request_context["channel"],
                message=request_context["meal_id_msg"],
                attachment=f"Components: {components} \n Feedback: {assistant_response}",
                attachment_title=f"Final feedback with nd score {nd_score} ",
                image_url=image_url,
            )  # INSERT LOGS ONLY WHEN askMealEvaluation IS FALSE/NULL
            if not askMealEvaluation:
                insert_row_meal_rating_logs(request_context, self.db)
            logger.info(
                f"Successfully calculated ND score and generated feedback"
                f"\nND Score: {nd_score}"
                f"\ncomponents: {components}"
                f"\nFeedback: {assistant_response}"
            )

            # Ensure all coroutines are awaited before generating the response
            # Check if components and suggestions are coroutines and await them if needed
            components_value = (
                await components if asyncio.iscoroutine(components) else components
            )

            suggestions_value = (
                await suggestions if asyncio.iscoroutine(suggestions) else suggestions
            )  # @TODO: CHeck this fail
            total_response_time = elapsed_str(request_context)

            suggestions_value = (
                await suggestions if asyncio.iscoroutine(suggestions) else suggestions
            )
            meal_rating_response = generate_meal_rating_response(
                request_context["payload"],
                item_list,
                food_type,
                message="Success",
                status=200,
                meal_score_response=meal_score_response,
                components=components_value,
                suggestions=suggestions_value,
                final_feedback=assistant_response,
                askMealEvaluation=askMealEvaluation,
                totalResponseTime=total_response_time,
            )
            try:
                # Call the tool function directly (sync)
                feedback_map = get_meal_feedback.func([image_id], self.db)

                meal_rating_response["curated_meal_feedback"] = (
                    next(iter(feedback_map.values()), None) if feedback_map else None
                )

            except Exception as e:
                # Log the error but don’t stop the pipeline
                logger.error(
                    "Error fetching curated meal feedback for image_id=%s: %s",
                    image_id,
                    str(e),
                    exc_info=True,  # full traceback in logs
                )

            # Ensure we await the async send_meal_rating_response function
            await send_meal_rating_response(meal_rating_response, user_token)


        except TypeError as e:
            logger.error("Error getting final meal feedback: %s", str(e), exc_info=True)
            request_context["errors"].append(
                f"Error getting final meal feedback:: {str(e)}"
            )

            send_meal_rating_message(
                channel=request_context["channel"],
                message=request_context["meal_id_msg"],
                attachment=str(e),
                attachment_title=f"Error getting final meal feedback ",
                image_url=image_url,
            )
            # INSERT LOGS ONLY WHEN askMealEvaluation IS FALSE/NULL
            if not askMealEvaluation:
                insert_row_meal_rating_logs(request_context, self.db)

            total_response_time = elapsed_str(request_context)
            await send_meal_rating_response(
                generate_meal_rating_response(
                    request_context["payload"],
                    [],
                    "",
                    message="Error getting final meal feedback",
                    status=400,
                    askMealEvaluation=askMealEvaluation,
                    totalResponseTime=total_response_time,
                ),
                user_token,
            )

        except Exception as e:
            logger.error("Error getting final meal feedback: %s", str(e), exc_info=True)
            request_context["errors"].append(
                f"Unexpected error getting final meal feedback:: {str(e)}"
            )
            send_meal_rating_message(
                channel=request_context["channel"],
                message=request_context["meal_id_msg"],
                attachment=str(e),
                attachment_title=f"Unexpected error getting final meal feedback ",
                image_url=image_url,
            )
            # INSERT LOGS ONLY WHEN askMealEvaluation IS FALSE/NULL
            if not askMealEvaluation:
                insert_row_meal_rating_logs(request_context, self.db)

            total_response_time = elapsed_str(request_context)
            await send_meal_rating_response(
                generate_meal_rating_response(
                    request_context["payload"],
                    [],
                    "",
                    message="Error getting final meal feedback",
                    status=500,
                    askMealEvaluation=askMealEvaluation,
                    totalResponseTime=total_response_time,
                ),
                user_token,
            )


def get_user_info(
    allergies,
    dietary_restrictions,
    exclusions,
    food_type,
    high_risk_traits,
    ingredients_to_avoid,
    item_list,
    meal_desc_json,
    nd_score,
    nd_titles,
    cgm_bad_peak,
    cgm_bad_recovery,
):
    user_info = {
        "nd_score": nd_score,
        "item_list": item_list,
        "meal_desc_json": meal_desc_json,
        "high_risk_traits": high_risk_traits,
        "allergies": allergies,
        "exclusions": exclusions,
        "dietary_restrictions": dietary_restrictions,
        "ingredients_to_avoid": ingredients_to_avoid,
        "nd_deduction_components": nd_titles,
        "food_type": food_type,
    }
    if cgm_bad_peak is not None:
        user_info["cgm_poor_peak"] = cgm_bad_peak
    if cgm_bad_recovery is not None:
        user_info["cgm_bad_recovery"] = cgm_bad_recovery
    return user_info


def get_fields(data):
    return (
        data["meal_info"]["image_id"],
        data["meal_info"]["image_url"],
        data["meal_info"]["meal_description"],
        data["meta_data"]["feature_tag"],
        data["user_info"]["user_token"],
        data["meal_info"]["cgm_meal_context"],
        data.get("askMealEvaluation", False),
    )


def insert_row_meal_rating_logs(request_context, db: DBClient):
    log_entry = MealRatingLogEntry.from_request_context(request_context)
    inserted_id = MealRatingLogService.insert_log(log_entry, db)
    if inserted_id is None:
        logger.error("Could not log meal rating for context %s", request_context)
    else:
        logger.info("Logged meal rating entry %s", inserted_id)

    return inserted_id


def elapsed_str(request_context: dict, key: str = "start_time") -> str:
    start = request_context.get(key, time.perf_counter())
    return f"{time.perf_counter() - start:.2f}"
