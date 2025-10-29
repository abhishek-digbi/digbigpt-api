from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from agent_core.config.logging_config import logger
from tools.services.spoonacular_service import search_recipes_complex
from utils.spoonacular_complex_search_models import SpoonacularComplexSearchRequest


class RecipeIngredients(BaseModel):
    name: str
    amount: str
    unit: str


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
    health_score: Optional[float] = None


class GetRecipesOutput(BaseModel):
    recipes: Dict[str, Recipe]
    request_url: Optional[str] = None


async def fetch_recipes_for_request(
    request: SpoonacularComplexSearchRequest,
) -> GetRecipesOutput:
    """
    Fetch recipes from Spoonacular based on the provided complex search request.
    """
    output = GetRecipesOutput(recipes={})
    logger.info("Max carbs " + str(request.max_carbs))
    try:
        params = {
            **request.to_query_params(),
            "addRecipeNutrition": "true",
        }
        filtered_params = {k: v for k, v in params.items() if v is not None}

        complex_search_response, request_url = await search_recipes_complex(
            filtered_params
        )
        output.request_url = request_url
        infos: List[Dict[str, Any]] = complex_search_response.get("results", [])

        if not infos:
            logger.info(f"No recipes found even with request {request}")
            return output

        for recipe in infos:
            nutrients = {
                n["name"]: n for n in recipe.get("nutrition", {}).get("nutrients", [])
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

            output.recipes[str(recipe.get("id"))] = Recipe(
                **{
                    "id": str(recipe.get("id")),
                    "title": recipe.get("title"),
                    "description": recipe.get("summary"),
                    "cook_time": recipe.get("readyInMinutes"),
                    "calories": nutrients.get("Calories", {}).get("amount"),
                    "protein": nutrients.get("Protein", {}).get("amount"),
                    "fat": nutrients.get("Fat", {}).get("amount"),
                    "net_carbs": nutrients.get("Net Carbohydrates", {}).get("amount")
                    or nutrients.get("Carbohydrates", {}).get("amount"),
                    "ingredients": ingredients,
                    "health_score": recipe.get("healthScore"),
                }
            )

    except Exception as e:
        logger.error("Exception during get recipes method call", e)

    recipes_returned = [recipe.title for recipe in output.recipes.values()]
    logger.info(f"returning these recipes {recipes_returned}")
    return output
