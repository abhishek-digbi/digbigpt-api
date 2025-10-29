import time
from typing import Optional

def generate_response(message, status, result=None):
    return {
        "message": message,
        "status": status,
        "timestamp": int(time.time() * 1000),
        "result": result,
    }


def generate_meal_rating_response(data, ingredients, food_type, message, status, meal_score_response=None, components=None,
                                  suggestions=None,
                                  final_feedback="", askMealEvaluation=False, totalResponseTime: Optional[str] = None,
                                  curated_meal_feedback: Optional[dict] = None):
    if suggestions is None:
        suggestions = []
    if components is None:
        components = []
    return {
        "image_id": data["meal_info"]["image_id"],
        "food_post_id": data["meal_info"]["food_post_id"],
        "ingredients": ingredients,
        "food_type": food_type,
        "message": message,
        "status": status,
        "timestamp": int(time.time() * 1000),
        "meal_score": meal_score_response,
        "components": components,
        "suggestions": suggestions,
        "final_feedback": final_feedback,
        "cgm_meal_context": data["meal_info"]["cgm_meal_context"],
        "askMealEvaluation": askMealEvaluation,
        "product_name": data.get("product_name",''),
        "product_upc_code": data.get("product_upc_code",''),
        "totalResponseTime": totalResponseTime,
        "curated_meal_feedback": curated_meal_feedback,
        "is_spoonacular_product_details": data.get("meal_info", {}).get("is_spoonacular_product_details", ''),
    }