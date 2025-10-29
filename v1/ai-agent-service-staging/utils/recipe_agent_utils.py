from typing import Dict, Any, List
from agent_core.config.logging_config import logger


def build_exclusion_set(profile: Dict[str, Any]) -> set[str]:
    """Build a normalized exclusion set from the user profile."""

    def _normalize(value: Any) -> List[str]:
        if isinstance(value, list):
            return [v for v in value if v]
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        return []

    exclusions = set()
    exclusions.update(i.lower() for i in _normalize(profile.get("ingredients_to_avoid")))
    exclusions.update(i.lower() for i in _normalize(profile.get("coach_added_exclusions")))
    exclusions.update(i.lower() for i in _normalize(profile.get("allergies_and_intolerances")))
    exclusions.add("alcohol")
    return exclusions


def get_recipe_conflicts(info: Dict[str, Any], exclusion_set: set[str]) -> List[str]:
    recipe_title = info.get("title", "Unknown Recipe")
    conflicts = []
    # Check for excluded ingredients
    ingredients = [i.get("name", "").lower() for i in info.get("extendedIngredients", [])]
    excluded_ingredients = [ex for ex in exclusion_set if any(ex in ing for ing in ingredients)]
    if excluded_ingredients:
        conflict = f"Recipe conflict - Excluded ingredients. Title: {recipe_title}, Ingredients: {excluded_ingredients}"
        logger.info(conflict)
        conflicts.append(conflict)

    # Check for alcoholic dish types
    dish_types = info.get("dishTypes", [])
    alcoholic_dish = next((dt for dt in dish_types if dt in ["cocktail", "alcoholic beverage"]), None)
    if alcoholic_dish:
        conflict = f"Recipe conflict - Alcoholic dish type. Title: {recipe_title}, Dish type: {alcoholic_dish}"
        logger.info(conflict)
        conflicts.append(conflict)

    # Check for alcohol-related keywords in title or summary
    title = info.get("title", "").lower()
    summary = info.get("summary", "").lower()
    alcohol_keywords = ["cocktail", "alcohol", "beer", "wine", "vodka", "rum", "whiskey"]
    found_keywords = [kw for kw in alcohol_keywords if kw in title or kw in summary]
    if found_keywords:
        conflict = f"Recipe conflict - Contains alcohol-related terms. Title: {recipe_title}, Terms: {found_keywords}"
        conflicts.append(conflict)
        logger.info(conflict)

    return conflicts

