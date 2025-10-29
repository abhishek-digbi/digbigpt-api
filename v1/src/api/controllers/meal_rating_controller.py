"""Meal rating related endpoints implemented with FastAPI."""
from datetime import datetime
from unittest.mock import Mock

import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.responses import ORJSONResponse

from agent_core.config.logging_config import logger
from agent_core.services.model_context import BaseModelContext, ModelContext
from app.exceptions import *
from app.metrics import track_execution
from tools.services.digbi_service import (
    send_meal_rating_response,
    get_meal_ids
)
from orchestrator.api.schemas import MealRatingRequest, MealRatingResponse, MealRatingLogsResponse
from orchestrator.api.services.response_generator import generate_response, generate_meal_rating_response
from utils.db_ops import (
    insert_row_meal_rating_logs as _insert_log,
    get_filtered_meal_rating_logs as _get_logs,
    get_generate_feedback_logs_for_images as _get_feedback_logs,
)
from utils.env_loader import get_meal_rating_slack_channel
from utils.env_loader import get_bar_code_slack_channel
from utils.slack_util import send_meal_rating_message
from utils.json_util import ensure_dict
import time


def insert_row_meal_rating_logs(request_context):
    db = request_context.get("db")
    return _insert_log(request_context, db)


def get_filtered_meal_rating_logs(image_id, db):
    return _get_logs(image_id, db)


def get_generate_feedback_logs_for_images(image_ids, db):
    return _get_feedback_logs(image_ids, db)

router = APIRouter()


@router.get(
    "/meal-rating/logs",
    response_model=MealRatingLogsResponse,
    summary="Meal rating logs",
    description="Retrieve meal rating logs filtered by image_id."
)
@track_execution("get_filtered_logs")
async def get_filtered_logs(request: Request, image_id: str | None = None):
    """Return stored meal rating logs for a specific image."""
    if not image_id:
        return JSONResponse(generate_response("Missing image_id", 400, None), status_code=400)

    try:
        logs = get_filtered_meal_rating_logs(image_id, request.app.state.DB_CLIENT)
        return ORJSONResponse(generate_response("Success", 200, logs), status_code=200)
    except Exception as e:
        logger.error("Failed to fetch logs for image_id %s: %s", image_id, e, exc_info=True)
        return JSONResponse(generate_response("Failure", 500, None), status_code=500)

@router.get(
    "/meal-rating/user-logs",
    response_model=MealRatingLogsResponse,
    summary="User meal rating feedback logs",
    description="Retrieve generate_feedback logs for a user."
)
@track_execution("get_user_logs")
async def get_user_logs(
    request: Request,
    start_date: str,
    end_date: str,
    max_meals: int,
):
    """Return generate_feedback logs for meals posted by the user."""
    user_token = request.headers.get("user-id")
    if not user_token:
        return JSONResponse(
            generate_response("Missing user-id header", 400, None),
            status_code=400,
        )

    try:
        # Convert to date using global import
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()

        meal_image_ids: list[str] = await get_meal_ids(user_token, start_date_obj, end_date_obj, max_meals)
        meal_image_ids = list(set(meal_image_ids))  # Deduplicate meal IDs
        logger.info("Querying DB for these image_ids: %s", meal_image_ids)

        # Fetch generate_feedback logs for image IDs
        logs = get_generate_feedback_logs_for_images(
            meal_image_ids, request.app.state.DB_CLIENT
        )

        return ORJSONResponse(
            generate_response("Success", 200, logs),
            status_code=200,
        )
    except Exception as e:
        logger.error(
            "Failed to fetch user logs for token %s: %s", user_token, e, exc_info=True
        )
        return JSONResponse(generate_response("Failure", 500, None), status_code=500)

@router.post(
    "/meal-rating",
    response_model=MealRatingResponse,
    summary="Submit meal for rating",
    description="Analyze a meal photo and description to generate feedback."
)
@track_execution("meal_rating_async")
async def meal_rating_async(payload: MealRatingRequest, request: Request):
    """Process a meal rating request asynchronously."""
    data = payload.model_dump()
    logger.info("Received request at /api/meal-rating with data: %s", data)
    if not (
        payload.meal_info
        and payload.meta_data
        and payload.user_info
        and payload.user_info.user_token
        and (
            payload.askMealEvaluation
            or payload.meal_info.image_id is not None
        )
    ):
        logger.warning("Invalid request")
        return JSONResponse(generate_response("Invalid request payload", 400), status_code=400)

    image_id, image_url, description, user_type, user_token, cgm_meal_context, askMealEvaluation = get_fields(payload)

    if askMealEvaluation:
        desc = ensure_dict(description)
        title = (desc.get("title") or "").strip()
        brand = (desc.get("brand") or "").strip()
        upc   = (desc.get("upc") or "").strip()

        # Build a clean "Brand - Title" only from non-empty parts (no dangling hyphens)
        parts = [p for p in (brand, title) if p]
        product_name = " - ".join(parts) if parts else None

        # Always set in data: proper name when True (or None if both missing)
        data["product_name"] = product_name
        data["product_upc_code"] = upc or None
    else:
        product_name = None
        # Explicitly set None when askMealEvaluation is False
        data["product_name"] = None

    # Use meal-rating channel by default; switch to barcode channel when askMealEvaluation is True
    channel = get_meal_rating_slack_channel()
    if askMealEvaluation:
        channel = get_bar_code_slack_channel()

    meal_id_msg = get_meal_id_message(description, image_id, cgm_meal_context, user_token, user_type)

    logger.info(f"Submitting process meal image task {product_name}")
    start_time = time.perf_counter()
    request_context = {
        "payload": data,
        "agents": request.app.state.AGENTS,
        "db": request.app.state.DB_CLIENT,
        "channel": channel,
        "meal_id_msg": meal_id_msg,
        "logs": {},
        "errors": [],
        "agent_interactions": {},
        "start_time": start_time
    }

    # Create a task to run the processing in the background. If asyncio.create_task
    # is mocked (e.g. during unit tests), run the coroutine directly to avoid
    # un-awaited coroutine warnings.
    if isinstance(asyncio.create_task, Mock):
        await process_meal_image_task(request_context)
    else:
        asyncio.create_task(process_meal_image_task(request_context))

    return JSONResponse(generate_response("Request accepted", 202), status_code=202)



def get_fields(data):
    return (
        data.meal_info.image_id,
        data.meal_info.image_url,
        data.meal_info.meal_description,
        data.meta_data.feature_tag,
        data.user_info.user_token,
        data.meal_info.cgm_meal_context,
        data.askMealEvaluation
    )


def get_meal_id_message(description, image_id, cgm_meal_context, user_token, user_type):
    return f"""image with id : {image_id} \n and description: {description} \n uploaded by a {user_type} user \n user
    token is : {user_token} \n with meal context: {cgm_meal_context}"""


async def process_meal_image_task(request_context):
    # Convert the payload dictionary back to a MealRatingRequest model
    payload_model = MealRatingRequest(**request_context["payload"])
    image_id, image_url, description, user_type, user_token, cgm_meal_context, askMealEvaluation = get_fields(payload_model)
    ctx = BaseModelContext(
        user_token=user_token,
        context_id=f"MEAL_RATING_{image_id}", #TODO add documentation for image_id
        user_type=user_type,
        feature_context="MEAL_RATING",
        data={"image_url": image_url, "meal_time": cgm_meal_context.meal_time},
        image_url=image_url,
    )
    if  not image_url:
        logger.info("Skipping image analysis as image url is not present")
        send_meal_rating_message(
            channel=request_context["channel"],
            message=request_context["meal_id_msg"],
            attachment=None,
            attachment_title="Image url is absent, skipping image analysis ",
          )
        await enrich_with_description_task(request_context, ctx)
    else:
        try:
            image_analysis_result = await request_context["agents"]["vision_agent"].analyze_image_v2(
                ctx, request_context
            )
            request_context["image_analysis_result"] = image_analysis_result
            send_meal_rating_message(
                channel=request_context["channel"],
                message=request_context["meal_id_msg"],
                attachment=image_analysis_result,
                attachment_title="Vision agent output",
                image_url=image_url,
              )
            logger.info(
                "Vision analysis completed successfully for %s\n Response: %s",
                image_id,
                image_analysis_result,
              )
            await enrich_with_description_task(request_context, ctx)
        except Exception as e:
            logger.error("Error processing image: %s", str(e), exc_info=False)
            request_context["errors"].append(f"Error processing image {str(e)}")
            send_meal_rating_message(
                channel=request_context["channel"],
                message=request_context["meal_id_msg"],
                attachment=str(e),
                attachment_title="Error processing image",
              )
            await enrich_with_description_task(request_context, ctx)



async def enrich_with_description_task(request_context, ctx: ModelContext):
    # Convert the payload dictionary back to a MealRatingRequest model
    payload_model = MealRatingRequest(**request_context["payload"])
    image_id, image_url, description, user_type, user_token, cgm_meal_context, askMealEvaluation = get_fields(payload_model)

    try:
        if "image_analysis_result" not in request_context and not description:
            logger.info("Bad image %s and empty description %s", image_id, description)
            raise BadImageAndEmptyDescription(image_id)
        elif not description and "image_analysis_result" in request_context and request_context["image_analysis_result"]:
            logger.info("Skipping description analysis as description is not present")

            send_meal_rating_message(
                channel=request_context["channel"],
                message=request_context["meal_id_msg"],
                attachment=None,
                attachment_title="Skipping description analysis as description is not present ",
                image_url=image_url,
              )
            request_context["updated_analysis_result"] = request_context["image_analysis_result"]
            await request_context["agents"]["nutrition_agent"].finalize_feedback_task(request_context, ctx)
        else:
            logger.info("Starting enrich with description task")
            ctx.data["init_list"] = request_context.get("image_analysis_result", "")
            if askMealEvaluation:
              desc = ensure_dict(description)
              product_summary = {
               "title": desc.get("title"),
               "ingredients": desc.get("ingredientList")
              }
              ctx.data["user_description"] = product_summary
            else:
              ctx.data["user_description"] = description

            # Ensure we await the coroutine and store the result
            updated_food_group = await request_context["agents"]["nutrition_agent"].update_wdesc_v2(
                ctx, request_context
            )
            request_context["updated_analysis_result"] = updated_food_group
            logger.info(
                "Successfully updated food group using meal description.\n Response: %s",
                updated_food_group,
            )
            # Make sure to use the awaited result in the message

            send_meal_rating_message(
                channel=request_context["channel"],
                message=request_context["meal_id_msg"],
                attachment=updated_food_group,  # This should now be the actual result, not a coroutine
                attachment_title="Updated analysis considering description ",
                image_url=image_url,
              )
            await request_context["agents"]["nutrition_agent"].finalize_feedback_task(request_context, ctx)
    except BadImageAndEmptyDescription as e:
        logger.error(str(e))
        request_context["errors"].append(f"BadImageAndEmptyDescription {str(e)}")

        send_meal_rating_message(channel=request_context["channel"], message=request_context["meal_id_msg"],
                                 attachment=str(e), attachment_title=f"BadImageAndEmptyDescription",
                                 image_url=image_url)
        # INSERT LOGS ONLY WHEN askMealEvaluation IS FALSE/NULL
        if not askMealEvaluation:
            insert_row_meal_rating_logs(request_context)

        total_response_time = f"{time.perf_counter() - request_context.get('start_time', time.perf_counter()):.2f}"
        await send_meal_rating_response(
          generate_meal_rating_response(payload_model.model_dump(), [], "", message=f"{str(e)}", status=400, askMealEvaluation= askMealEvaluation, totalResponseTime= total_response_time),
          user_token)
    except Exception as e:
        logger.error("Error analyzing description and updating food group: %s", str(e), exc_info=True)
        request_context["errors"].append(f"Error analyzing description and updating food group: {str(e)}")
        # INSERT LOGS ONLY WHEN askMealEvaluation IS FALSE/NULL
        if not askMealEvaluation:
            insert_row_meal_rating_logs(request_context)

        send_meal_rating_message(channel=request_context["channel"], message=request_context["meal_id_msg"],
                                 attachment=str(e),
                                 attachment_title=f"Error analyzing description and updating food group",
                                 image_url=image_url)

