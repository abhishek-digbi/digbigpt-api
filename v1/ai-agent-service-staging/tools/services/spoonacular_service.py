import os
from typing import Any, Dict, Tuple
import httpx
from agent_core.config.logging_config import logger

BASE_URL = "https://api.spoonacular.com/"
API_KEY = os.getenv("SPOONACULAR_KEY", "c05079add851431bbf4a804d2cc45e9f")
HEADERS = {
    "x-api-key": API_KEY,
}


async def call_spoonacular(
    endpoint: str, params: Dict[str, Any], return_request_url: bool = False
) -> Any:
    """Make an async GET request to the Spoonacular API."""
    url = BASE_URL + endpoint
    # Log the request
    logger.info("Spoonacular API Request - %s: %s", endpoint, params)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                headers=HEADERS,
                params={k: v for k, v in params.items() if v is not None}
            )

            # Log the response status
            logger.info("Spoonacular API Response - %s: %d", endpoint, response.status_code)

            response.raise_for_status()
            response_data = response.json()

            # # Log the complete response
            # logger.info("Spoonacular API Response Data - %s: %s",
            #             endpoint,
            #             response_data)

            if return_request_url:
                return response_data, str(response.request.url)
            return response_data

    except Exception as e:
        logger.error("Spoonacular API Error - %s: %s", endpoint, str(e))
        raise


# https://spoonacular.com/food-api/docs#Search-Recipes-Complex
async def search_recipes_complex(params: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """Wrapper for the `recipes/complexSearch` endpoint."""
    return await call_spoonacular(
        "recipes/complexSearch", params, return_request_url=True
    )


async def analyze_recipe_query(query: str) -> Dict[str, Any]:
    """Wrapper for the `recipes/queries/analyze` endpoint."""
    if not query:
        return {}
    return await call_spoonacular("recipes/queries/analyze", {"q": query})
