"""Recipe-related tool definitions."""

from typing import Any, Dict, List, Union

import asyncio
import random
from agents import custom_span
from pydantic import BaseModel

from tools import tool
from tools.services.recipe_search import (
    GetRecipesOutput,
    Recipe,
    fetch_recipes_for_request,
)
from utils.spoonacular_complex_search_models import SpoonacularComplexSearchRequest


def _serialize_for_trace(data: Any) -> Any:
    if isinstance(data, BaseModel):
        return data.model_dump()
    if isinstance(data, dict):
        return {k: _serialize_for_trace(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_serialize_for_trace(v) for v in data]
    if isinstance(data, set):
        return sorted(list(data))
    return data


@tool(
    name="get_recipes_tool",
    description=(
        "Fetch recipes from Spoonacular using multiple complex search requests and return the combined "
        "recipe information. Always provide at least three different requests "
        "to maximize coverage."
    ),
)
async def get_recipes_tool(
    requests: List[Union[Dict[str, Any], SpoonacularComplexSearchRequest]],
) -> Dict[str, Any]:
    """
    Tool wrapper over RecipeAgent recipe fetching logic supporting multiple request variations.
    """
    if not isinstance(requests, list) or not requests:
        raise ValueError(
            "requests must be a non-empty list of SpoonacularComplexSearchRequest inputs"
        )

    normalized_requests: List[SpoonacularComplexSearchRequest] = []
    for idx, request in enumerate(requests):
        if isinstance(request, SpoonacularComplexSearchRequest):
            normalized_requests.append(request)
        elif isinstance(request, dict):
            normalized_requests.append(SpoonacularComplexSearchRequest(**request))
        else:
            raise ValueError(
                f"requests[{idx}] must be either a dict or SpoonacularComplexSearchRequest instance"
            )

    if len(normalized_requests) < 2:
        raise ValueError(
            "Provide at least two request variations to maximize recipe retrieval."
        )

    async def _fetch_with_trace(
        request: SpoonacularComplexSearchRequest,
    ) -> GetRecipesOutput:
        with custom_span(
            "spoonacular_complex_search",
            data={"input": _serialize_for_trace(request)},
        ) as span:
            response = await fetch_recipes_for_request(request)
            span.span_data.data["output"] = _serialize_for_trace(response)
            return response

    responses = await asyncio.gather(
        *(_fetch_with_trace(request) for request in normalized_requests)
    )

    combined = GetRecipesOutput(recipes={})
    aggregated_recipes: Dict[str, Recipe] = {}
    for response in responses:
        for recipe_id, recipe in response.recipes.items():
            aggregated_recipes[recipe_id] = recipe

    if aggregated_recipes:
        recipes_items = list(aggregated_recipes.items())
        sample_size = min(len(recipes_items), 3)
        selected_items = random.sample(recipes_items, sample_size)
        combined.recipes = {recipe_id: recipe for recipe_id, recipe in selected_items}

    return combined.model_dump()
