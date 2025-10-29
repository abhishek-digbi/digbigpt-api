import re
from typing import List
from pydantic import BaseModel


class MealDetails(BaseModel):
    food_type: str
    meal_time: str
    item_list: list[str]
    food_categories: list[dict]
    is_ultra_processed: bool
    extra_keys: dict
    threshold_data: dict


def get_components(meal_info: MealDetails, sensitivities, high_risk_traits: []) -> List[str]:
    components = []

    # Define food categories with regex patterns
    food_categories = {
        'caffeine': r'(Beverage - Level 1|Tea|Coffee|Herbal Teas)',
        'gluten': r'Gluten Rich Grains',
        'alcohol': r'Alcohol',
        'high_glucose_carbs': r'Processed Carbs|High Glucose Carbs|^Milk - Grain based|^Starches - (Grains|Beans and Legumes)',
        'high_glucose_fruits': r'Fruits - Group 2',
        'low_glucose_fruits': r'Fruits - Group 1',
        'no_vegetables': r'Vegetables - Group 1|Vegetables - Group 2|Vegetables - Group 3',
        'processed_additives': r'^Condiment - Level 2|Processed with Additives|^Beverage - Level 2',
        'starch_rich': r'Vegetables - Group 3|^Starches - Vegetables',
        'sugar_substitutes': r'Sweeteners|Desserts|^Beverage - Level 2',
        'lactose_sensitive': r'Dairy|Probiotics - Soft Cheeses',
        'inflammatory_nuts_seeds': r'Fats - (Nuts|Seeds)|Milk - Nut based',
        'probiotics': r'Probiotics -|Fermented Foods'
    }

    # Function to check if any food category matches in the meal description
    def category_present(category):
        return any(re.search(food_categories[category], item['foodCategory'], re.IGNORECASE) for item in
                   meal_info.food_categories)

    pattern_caffeine = re.compile(r'caffeine', re.IGNORECASE)
    pattern_gluten = re.compile(r'gluten', re.IGNORECASE)
    pattern_lactose = re.compile(r'lactose', re.IGNORECASE)

    # Deduct points for these sensitivities only if the user has high risk, not moderate risk
    has_caffeine_sensitivity = any(pattern_caffeine.search(
        trait) for trait in high_risk_traits)
    has_gluten_sensitivity = any(pattern_gluten.search(
        trait) for trait in high_risk_traits)
    has_lactose_sensitivity = any(pattern_lactose.search(
        trait) for trait in high_risk_traits)

    for key, value in meal_info.threshold_data.items():
        if value is True:
            match key:
                case _ if "Vegetables - Group 3" in key:
                    components.append("GROUP_3_VEGGIES")
                case _ if "Fruits - Group 1" in key:
                    components.append("GROUP_1_FRUIT")
                case _ if "Fruits - Group 2" in key:
                    components.append("GROUP_2_FRUIT")
                case _ if "Fats - Nuts" in key:
                    components.append("NUTS_SEEDS_DRIED_FRUIT")
                case _ if "Fats - Seeds" in key:
                    components.append("NUTS_SEEDS_DRIED_FRUIT")

    # Insulin Resistance deductions
    if category_present('high_glucose_carbs'):
        components.append("PROCESSED_CARBS")

    if category_present('processed_additives') or meal_info.is_ultra_processed:
        components.append("PROCESSED_CHEMICALS")

    if category_present('sugar_substitutes'):
        components.append("SUGARS_SUBSTITUTES")

    # Lactose sensitivity check
    if 'lactose' in sensitivities and has_lactose_sensitivity:
        components.append("LACTOSE")

    if not category_present('probiotics'):
        components.append("NO_PROBIOTICS")

    # Caffeine sensitivity check
    if 'caffeine' in sensitivities and has_caffeine_sensitivity:
        components.append("CAFFEINE")

    # Gluten sensitivity check
    if 'gluten' in sensitivities and has_gluten_sensitivity:
        components.append("GLUTEN")

    # Alcohol deduction
    if category_present('alcohol'):
        components.append("ALCOHOL")

    # Adjust deductions based on the type of meal

    vegetables_count = sum(1 for item in meal_info.food_categories if re.search(
        food_categories['no_vegetables'], item['foodCategory'], re.IGNORECASE))

    if vegetables_count < 2 and meal_info.food_type is not None and meal_info.food_type.lower() == 'meal':
        components.append("LESS_THAN_2_TYPES_OF_VEGGIES")
    return components
