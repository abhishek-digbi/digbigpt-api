"""Common tools that can be used across different agents."""
import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional

from agent_core.config.logging_config import logger
from orchestrator.orchestrators.agent_models import InteractiveComponent, VideoRecommendationResult
from tools import tool
from utils.db import DBClient
from orchestrator.services.meal_rating_log_entry import MealRatingLogService
from agents import RunContextWrapper
from agents.exceptions import (
    InputGuardrailTripwireTriggered,
    OutputGuardrailTripwireTriggered,
)
from tools.services.spoonacular_service import (
    analyze_recipe_query as spoonacular_analyze_recipe_query,
)


@tool
async def recommend_videos(
        ctx: RunContextWrapper[Any]
) -> Any:
    """
    Recommend the best-matching video by invoking VIDEO_RECOMMENDER_AGENT.

    Args:
        ctx: Internal run context (provided automatically by the agent runtime).

    Returns:
        VideoRecommendationResult representing a single video recommendation.
    """
    model_ctx = getattr(ctx, "context", None)

    try:
        if model_ctx is None:
            raise ValueError("recommend_videos requires a valid model context.")

        ai_runner = getattr(model_ctx, "ai_runner", None)
        if not callable(ai_runner):
            raise ValueError("recommend_videos requires ctx.context.ai_runner (async callable).")

        data_dict = getattr(model_ctx, "data", None)
        if not isinstance(data_dict, dict):
            raise ValueError("recommend_videos requires ctx.context.data to be a dict.")

        result = await ai_runner(
            "VIDEO_RECOMMENDER_AGENT",
            model_ctx,
            output_type=VideoRecommendationResult,
            tool_choice="file_search",
            strict_json_schema=True
        )
        return result
    except (InputGuardrailTripwireTriggered, OutputGuardrailTripwireTriggered) as guardrail_exc:
        logger.info(
            "Blocked video recommendation due to guardrail: %s",
            getattr(guardrail_exc.guardrail_result.output, "output_info", guardrail_exc),
        )
        return None
    except Exception as e:
        logger.error(f"recommend_videos failed: {e}")
        return None


@tool
def cgm_score_report(tir: float) -> Tuple[int, str]:
    """
    Build a CGM Time-in-Range (TIR) report from a TIR percentage (0–100).
    Returns:
        score (int) - 1 (lowest) to 5 (highest)
        report (str) - formatted multi-paragraph report
    Categories & Scores:
      >85%   = Best range (score 5)
      71–85% = Slightly elevated risk (score 4)
      61–70% = Moderate risk (score 3)
      51–60% = Higher risk (score 2)
      ≤50%   = Highest risk (score 1)
    """
    if tir is None:
        raise ValueError("tir must be a float percentage between 0 and 100.")
    t = max(0.0, min(100.0, float(tir)))

    intro = (
        "CGM TIR score: how steady your glucose is\n"
        "Your TIR (Time in Range) score shows how often your glucose stays within a healthy range (3.9–10 mmol/L) over 72 hours. "
        "It’s a gentle, real-time way to understand how your body is handling blood sugar right now—not just in a lab test, but in everyday life.\n"
        "Why does it matter?\n"
        "When your glucose stays steady, it means your body’s under less stress. That can lower inflammation, protect your organs, and support a longer, healthier life—especially if you’re managing type 2 diabetes. "
        "But this isn’t about being perfect. It’s about noticing patterns, making small adjustments, and giving your body the care it needs. "
        "Every hour your glucose stays in range is a quiet win—and those wins add up.\n"
        "You're doing something powerful just by paying attention. We’re here to support you, step by step."
    )

    if t > 85:
        score = 5
        title = "Best range"
        what = "You’re in the sweet spot—your glucose is steady most of the time, which supports lower stress on your body and long-term health."
        next_steps = "Keep doing what works. Maintain consistent meal timing, regular activity, and sleep routines; continue checking patterns to catch early changes."
    elif 71 <= t <= 85:
        score = 4
        title = "Slightly elevated risk"
        what = "You’re mostly in range with occasional bumps—your system is handling things well, but small tweaks could lift your TIR further."
        next_steps = "Try moving 10–15 minutes after meals, front-load protein and veggies, and review any spikes tied to specific foods or late-night eating."
    elif 61 <= t <= 70:
        score = 3
        title = "Moderate risk"
        what = "Glucose is slipping out of range more often, which can increase metabolic stress over time."
        next_steps = "Focus on consistency: balance carbs with protein/fiber, add a daily walk, and consider adjusting meal timing or portion size to reduce post‑meal spikes."
    elif 51 <= t <= 60:
        score = 2
        title = "Higher risk"
        what = "Frequent swings likely contribute to fatigue, brain fog, or cravings and may raise long‑term risk if trends persist."
        next_steps = "Start with one or two anchors: a 15‑minute walk after the largest meal, swap sugary drinks for water/unsweetened tea, and aim for regular sleep/wake times."
    else:
        score = 1
        title = "Highest risk"
        what = "Glucose is often out of range, which can elevate long‑term complications risk—especially if lows (<3.9 mmol/L) or highs (>10 mmol/L) are common."
        next_steps = "Begin with small, steady changes: reduce refined carbs, add short post‑meal activity, and discuss targets or medication adjustments with a clinician. Even a 5–10% increase in TIR is a meaningful win."

    target = (
        "General target: aim for ≥70% of the day between 3.9–10.0 mmol/L, "
        "with <4% below 3.9 mmol/L and <25% above 10.0 mmol/L (and <5% above 13.9 mmol/L)."
    )

    report = (
        f"Your CGM TIR: {t:.0f}%\n\n"
        f"{intro}\n\n"
        f"What this means ({title}): {what}\n\n"
        f"Try this next: {next_steps}\n\n"
        f"{target}"
    )

    return score, report


@tool
def vo2_score_report(vo2: float, gender: int, age: int) -> Tuple[int, str]:
    """
    Calculate a VO₂ max score (0–10) and provide a guidance report.

    Args:
        vo2: VO₂ max value in mL·kg⁻¹·min⁻¹.
        gender: ``1`` for male, ``2`` for female.
        age: Age in years.

    Returns:
        Tuple of ``(score, report)`` where ``score`` is an integer between
        0 and 10 and ``report`` is a multi‑paragraph string with guidance.
    """

    # FEMALE cutoffs (low to high → score increases)
    female_tables = {
        "<40": [40.35, 40.63, 40.90, 41.18, 41.45, 41.72, 41.99, 42.25, 42.53, 42.80],
        "40-59": [36.80, 37.05, 37.32, 37.58, 37.85, 38.10, 38.38, 38.64, 38.92, 39.20],
        "60-79": [36.25, 36.40, 36.55, 36.70, 36.85, 37.00, 37.15, 37.30, 37.45, 37.60],
        ">=80": [35.40, 35.72, 35.88, 36.04, 36.20, 36.36, 36.52, 36.68, 36.84, 37.00],
    }

    # MALE cutoffs (low to high → score increases)
    male_tables = {
        "<40": [42.38, 42.72, 42.98, 43.24, 43.54, 43.84, 44.15, 44.44, 44.76, 45.10],
        "40-59": [41.46, 41.72, 41.98, 42.24, 42.50, 42.74, 43.02, 43.28, 43.58, 43.90],
        "60-79": [39.95, 40.28, 40.60, 40.94, 41.30, 41.66, 42.02, 42.38, 42.74, 43.10],
        ">=80": [37.70, 38.42, 38.78, 39.13, 39.50, 39.86, 40.22, 40.58, 40.94, 41.30],
    }

    # Determine age band
    if age < 40:
        band = "<40"
    elif age <= 59:
        band = "40-59"
    elif age <= 79:
        band = "60-79"
    else:
        band = ">=80"

    tables = male_tables if gender == 1 else female_tables
    cutoffs = tables[band]

    # Calculate score
    score = sum(1 for cutoff in cutoffs if vo2 >= cutoff)

    guide = {
        0: {
            "zone": "fresh start",
            "means": (
                "Your oxygen use is low—this might be an early sign of stress on your "
                "heart or metabolism. But this is a fantastic place to begin your improvement journey!"
            ),
            "next": (
                "Begin with short, easy walks (5–10 min) every day. Add gentle movement like stretching or light chores. "
                "Slowly increase your walking time each week."
            ),
        },
        1: {
            "zone": "foundations",
            "means": (
                "You’ve got room to grow, and your body’s ready to respond. A little movement goes a long way."
            ),
            "next": (
                "Aim for 15–20 min of walking, cycling, or swimming 3–4 times a week. Keep it at a pace where you can still "
                "talk, but feel your breathing get a little faster."
            ),
        },
        2: {
            "zone": "warming up",
            "means": (
                "You’re starting to use oxygen more efficiently—a great sign for heart and lung health."
            ),
            "next": (
                "Try brisk walking or gentle cycling for 20–30 min, 3–4 days a week. Once or twice a week, add short 20–30 "
                "second bursts of faster movement."
            ),
        },
        3: {
            "zone": "momentum rising",
            "means": (
                "Your heart’s pumping stronger, and your body’s delivering oxygen more efficiently."
            ),
            "next": (
                "Keep your usual walks or rides, but add “intervals”—1–2 minutes at a faster pace, followed by 2–3 minutes "
                "easy. Do this 4–6 times per session."
            ),
        },
        4: {
            "zone": "building strength",
            "means": (
                "Your blood vessels and metabolism are adapting—you’re getting stronger on the inside."
            ),
            "next": (
                "Add moderate hikes, cycling, or swimming for 30–40 min, 3–5 days a week. Include one day of longer steady "
                "exercise to build stamina."
            ),
        },
        5: {
            "zone": "balanced zone",
            "means": (
                "Right on track for your age. Your heart, lungs, and daily movement are in sync."
            ),
            "next": (
                "Stay active most days of the week. Do at least 150 min of moderate exercise weekly—walking, cycling, "
                "swimming, or light jogging—and keep adding short faster bursts."
            ),
        },
        6: {
            "zone": "going strong",
            "means": (
                "Your VO₂ max is above average, which can mean lower inflammation and better energy."
            ),
            "next": (
                "Do a mix of cardio (walking, cycling, jogging) and strength training. Once or twice a week, push harder for "
                "3–5 minutes at a time, with recovery in between."
            ),
        },
        7: {
            "zone": "thriving",
            "means": (
                "Your heart and metabolism are working like a team—resilient and efficient."
            ),
            "next": (
                "Add variety: try hill walks, stair climbs, or group classes to challenge your heart and lungs in new ways. "
                "Keep 1–2 days for harder effort."
            ),
        },
        8: {
            "zone": "high performance",
            "means": (
                "You’ve got near-athlete-level oxygen capacity. Just a little more can move you up again."
            ),
            "next": (
                "Include short sprints or high-effort intervals (20–60 seconds) with longer rests. Keep 2–3 cardio sessions "
                "per week and balance with recovery days."
            ),
        },
        9: {
            "zone": "peak zone",
            "means": (
                "Excellent heart and lung power—your biological age may be younger than your actual age."
            ),
            "next": (
                "Maintain with structured training: alternate high-intensity days and easy recovery days. Use different "
                "activities that keep your heart rate up."
            ),
        },
        10: {
            "zone": "elite level",
            "means": (
                "You’re at the top! Typical of elite endurance athletes, this level is tied to the lowest disease risk."
            ),
            "next": (
                "Keep challenging yourself with smart training cycles—mix hard sessions with recovery, and don’t forget rest "
                "days to stay strong and injury-free."
            ),
        },
    }

    s = max(0, min(10, score))
    g = guide[s]

    static_para = (
        "VO₂ score – higher is better\n"
        "VO₂ max tells us how well your body uses oxygen—and it’s closely linked to how fast or slow you’re aging. "
        "Every point matters: just one point on the scale can mean gaining or losing a year of biological age.\n"
        "The good news? Small changes can go a long way. Boosting your VO₂ max by just 2–3 points may help you feel and "
        "function years younger—and lower your long-term health risks.\n"
        "Higher VO₂ max scores are tied to better fitness and longevity, while lower scores may signal faster aging. "
        "But here’s the best part: VO₂ max is trainable. With the right steps, you can improve it—and support your health for "
        "the long run."
    )

    report = (
        f"Your VO2 Lung score is — {s}\n\n"
        f"{static_para}\n\n"
        f"What it means ({g['zone']}): {g['means']}\n\n"
        f"Try this next: {g['next']}"
    )

    return s, report


@tool
def get_meal_feedback(entity_ids: List[str], db_client: DBClient) -> Dict[str, Dict[str, Any]]:
    """
    Fetch meal feedback data for the given entity IDs.

    Args:
        entity_ids: entity ids / image ids to fetch feedback for
        db_client: Database client instance

    Returns:
        A dictionary where keys are entity IDs and values are dictionaries containing feedback data for that entity.
        Each value dictionary includes:
        - cgm_bad_peak: Boolean indicating if CGM showed a bad peak
        - cgm_bad_recovery: Boolean indicating if CGM showed bad recovery
        - food_type: Type of food
        - image_url: URL of the food image
        - ingredients: List of ingredients
        - is_ultra_processed: Boolean indicating if food is ultra-processed
        - meal_time: Time of the meal
        - meal_type: Type of meal (breakfast, lunch, dinner, etc.)
        - nd_components: Nutrition density components
        - nd_score: Nutrition density score
        - threshold_data: Data about nutritional thresholds
        - user_description: User's description of the meal
        - food_categories: Categories the food belongs to
    """
    logger.info(f"Fetching feedback for {entity_ids}")
    feedback_list = MealRatingLogService.fetch_feedback_for_images(entity_ids, db_client)
    meal_logs_sorted = sorted(
        [
            {"meal_id": log["image_id"], **log["ctx_data"]}
            for log in feedback_list
            if log.get("ctx_data", {}).get("meal_time")
        ],
        key=lambda x: datetime.strptime(x["meal_time"], "%B %d, %Y %H:%M %p"),
        reverse=True,
    )
    # Create a map with key as meal_time + ' ' + meal_type
    meal_map = {
        f"{meal['meal_type']} on {meal['meal_time']}": meal
        for meal in meal_logs_sorted
    }
    logger.info(f"{meal_map} {meal_logs_sorted} {feedback_list}")
    return meal_map


def _dedup_key(value: Any) -> str:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return json.dumps(value, sort_keys=True)
    try:
        return json.dumps(value, sort_keys=True)
    except (TypeError, ValueError):
        return repr(value)


def _merge_values(existing: Any, new_value: Any) -> Any:
    if isinstance(new_value, dict):
        merged: Dict[str, Any] = {} if not isinstance(existing, dict) else dict(existing)
        for nested_key, nested_value in new_value.items():
            merged[nested_key] = _merge_values(merged.get(nested_key), nested_value)
        return merged

    if isinstance(new_value, list):
        base_list: List[Any] = [] if not isinstance(existing, list) else list(existing)
        seen = {_dedup_key(item) for item in base_list}
        for item in new_value:
            key = _dedup_key(item)
            if key not in seen:
                base_list.append(item)
                seen.add(key)
        return base_list

    return new_value if new_value is not None else existing


@tool(
    name="analyze_user_recipe_query",
    description="Analyze multiple variations of a user recipe search query using the Spoonacular analyze "
                "recipe query API and return combined dishes, ingredients, cuisines, and modifiers. "
                "Always pass at least two query variations to maximize coverage.",
)
async def analyze_user_recipe_query(queries: List[str]) -> Dict[str, Any]:
    if not isinstance(queries, list) or not queries:
        raise ValueError("queries must be a non-empty list of strings")

    normalized_queries: List[str] = []
    for idx, query in enumerate(queries):
        if not isinstance(query, str):
            raise ValueError(f"queries[{idx}] must be a string")
        stripped = query.strip()
        if not stripped:
            raise ValueError(f"queries[{idx}] must be a non-empty string")
        normalized_queries.append(stripped)

    if len(normalized_queries) < 2:
        raise ValueError("Provide at least two query variations to analyze the recipe request.")

    responses = await asyncio.gather(
        *(spoonacular_analyze_recipe_query(query) for query in normalized_queries)
    )

    combined_result: Dict[str, Any] = {}
    for response in responses:
        if not isinstance(response, dict):
            continue
        for key, value in response.items():
            combined_result[key] = _merge_values(combined_result.get(key), value)

    return combined_result
