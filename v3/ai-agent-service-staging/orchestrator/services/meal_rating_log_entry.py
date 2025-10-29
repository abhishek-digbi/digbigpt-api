from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import json
import logging
import ast
from psycopg2.extras import Json

from utils.db import DBClient

from agent_core.config.logging_config import logger

def sanitize(obj: Any, _seen: Optional[set] = None) -> Any:
    """
    Recursively deep-copies `obj` into JSON-serializable primitives,
    breaking circular references by replacing them with strings.
    """
    if _seen is None:
        _seen = set()
    obj_id = id(obj)
    if obj_id in _seen:
        return str(obj)
    _seen.add(obj_id)

    if isinstance(obj, dict):
        return {str(k): sanitize(v, _seen) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize(v, _seen) for v in obj]
    if isinstance(obj, tuple):
        return tuple(sanitize(v, _seen) for v in obj)
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    # fallback: convert any other object to string
    return str(obj)


@dataclass
class MealRatingLogEntry:
    image_id: str
    food_post_id: str
    user_token: str
    request: Dict[str, Any]
    user_data_used: Dict[str, Any]
    agent_interactions: Dict[str, Any]
    errors: List[Any]
    miscellaneous: Dict[str, Any]

    @staticmethod
    def from_request_context(ctx: Dict[str, Any]) -> "MealRatingLogEntry":
        payload = ctx.get("payload", {})
        meal_info = payload.get("meal_info", {})
        return MealRatingLogEntry(
            image_id=meal_info.get("image_id", ""),
            food_post_id=meal_info.get("food_post_id", ""),
            user_token=payload.get("user_info", {}).get("user_token", ""),
            request=payload,
            user_data_used=ctx.get("user_data_used", {}),
            agent_interactions=ctx.get("agent_interactions", {}),
            errors=ctx.get("errors", []),
            miscellaneous=ctx.get("miscellaneous", {}),
        )

    def to_db_params(self) -> tuple:
        # sanitize ensures no circular references
        req = sanitize(self.request)
        used = sanitize(self.user_data_used)
        inter = sanitize(self.agent_interactions)
        errs = sanitize(self.errors)
        misc = sanitize(self.miscellaneous)

        return (
            self.image_id,
            self.food_post_id,
            self.user_token,
            Json(req),
            Json(used),
            Json(inter),
            Json(errs),
            Json(misc),
        )


class MealRatingLogService:
    """Handles persistence of meal rating logs."""

    INSERT_SQL = """
        INSERT INTO meal_rating_logs (
            image_id, food_post_id, user_token,
            request, user_data_used,
            agent_interactions, errors, miscellaneous
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """

    FETCH_SQL = """
        SELECT * FROM meal_rating_logs
        WHERE image_id = %s
        ORDER BY created_at DESC
    """

    FETCH_FEEDBACK_SQL = """
        SELECT DISTINCT ON (image_id)
            image_id,
            agent_interactions ->> 'generate_feedback' AS generate_feedback,
            agent_interactions ->> 'update_wdesc_v2' AS update_wdesc_v2,
            agent_interactions ->> 'vision_agent' AS vision_agent
        FROM meal_rating_logs
        WHERE image_id = ANY(%s)
          AND (
              BTRIM(agent_interactions ->> 'generate_feedback') IS NOT NULL
              AND BTRIM(agent_interactions ->> 'generate_feedback') != ''
              OR agent_interactions -> 'update_wdesc_v2' IS NOT NULL
              OR agent_interactions -> 'vision_agent' IS NOT NULL
          )
        ORDER BY image_id, created_at DESC
    """

    @classmethod
    def insert_log(cls, entry: MealRatingLogEntry, db: DBClient) -> Optional[int]:
        conn = db.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(cls.INSERT_SQL, entry.to_db_params())
                row_id = cur.fetchone()[0]
            conn.commit()
            logger.info("Inserted meal_rating_logs id=%s", row_id)
            return row_id
        except Exception:
            conn.rollback()
            logger.exception("Failed to insert meal rating log")
            return None
        finally:
            db.release_conn(conn)

    @classmethod
    def fetch_logs(cls, image_id: str, db: DBClient) -> List[Dict[str, Any]]:
        conn = db.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(cls.FETCH_SQL, (image_id,))
                columns = [d[0] for d in cur.description]
                rows = cur.fetchall()
                logger.info("Fetched %s logs for image_id %s", len(rows), image_id)
                return [dict(zip(columns, row)) for row in rows]
        except Exception:
            logger.error("Failed to fetch logs for image_id %s", image_id)
            return []
        finally:
            db.release_conn(conn)

    @classmethod
    def fetch_feedback_for_images(
        cls, image_ids: list[str], db: DBClient
    ) -> list[dict[str, Any]]:
        """Fetch ctx.data from generate_feedback JSON for provided image IDs, using update_wdesc_v2 or vision_agent response."""
        if not image_ids:
            return []

        allowed_keys = {
            "cgm_bad_peak",
            "cgm_bad_recovery",
            "food_type",
            "image_url",
            "ingredients",
            "is_ultra_processed",
            "meal_time",
            "meal_type",
            "nd_components",
            "nd_score",
            "threshold_data",
            "user_description",
            "food_categories"
        }

        conn = db.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(cls.FETCH_FEEDBACK_SQL, (list(map(int, image_ids)),))
                columns = [d[0] for d in cur.description]
                rows = cur.fetchall()
                logger.info("Fetched %s feedback logs for %s images", len(rows), len(image_ids))

                results = []
                for row in rows:
                    row_dict = dict(zip(columns, row))
                    feedback = row_dict.get("generate_feedback")
                    update_wdesc = row_dict.get("update_wdesc_v2")
                    vision_agent = row_dict.get("vision_agent")
                    ctx_data = None
                    update_response_data = None
                    vision_response_data = None

                    # Parse update_wdesc_v2 response
                    if update_wdesc:
                        try:
                            if isinstance(update_wdesc, dict):
                                update_wdesc_obj = update_wdesc
                            else:
                                update_wdesc_obj = json.loads(update_wdesc)
                            response_raw = update_wdesc_obj.get("response")
                            if response_raw:
                                update_response_data = json.loads(response_raw)
                        except Exception as e:
                            logger.warning(
                                f"Could not parse update_wdesc_v2 for image_id {row_dict['image_id']}: {e}"
                            )

                    # Parse vision_agent response
                    if vision_agent:
                        try:
                            if isinstance(vision_agent, dict):
                                vision_agent_obj = vision_agent
                            else:
                                vision_agent_obj = json.loads(vision_agent)
                            response_raw = vision_agent_obj.get("response")
                            if response_raw:
                                vision_response_data = json.loads(response_raw)
                        except Exception as e:
                            logger.warning(
                                f"Could not parse vision_agent for image_id {row_dict['image_id']}: {e}"
                            )

                    if feedback:
                        try:
                            feedback_obj = json.loads(feedback)
                            ctx_data_raw = feedback_obj.get("ctx.data")

                            if isinstance(ctx_data_raw, str):
                                try:
                                    ctx_data = json.loads(ctx_data_raw.replace("'", '"'))
                                except json.JSONDecodeError:
                                    try:
                                        ctx_data = ast.literal_eval(ctx_data_raw)
                                    except Exception as inner_e:
                                        logger.warning(
                                            f"Could not eval ctx_data string for image_id {row_dict['image_id']}: {inner_e}"
                                        )
                                        ctx_data = None
                            else:
                                ctx_data = ctx_data_raw

                            if ctx_data and isinstance(ctx_data, dict):
                                new_ctx = {}

                                # Rename item_list to ingredients
                                if "item_list" in ctx_data:
                                    new_ctx["ingredients"] = ctx_data["item_list"]

                                # Copy allowed top-level fields
                                for key in [
                                    "cgm_bad_peak", "cgm_bad_recovery", "food_type", "image_url",
                                    "is_ultra_processed", "meal_time", "threshold_data", "user_description"
                                ]:
                                    if key in ctx_data:
                                        new_ctx[key] = ctx_data[key]

                                # Assign food_categories (no init_list)
                                food_categories = []
                                if update_response_data and update_response_data.get("foodCategories"):
                                    food_categories = update_response_data["foodCategories"]
                                elif vision_response_data and vision_response_data.get("foodCategories"):
                                    food_categories = vision_response_data["foodCategories"]
                                elif ctx_data.get("meal_desc"):
                                    food_categories = ctx_data["meal_desc"]

                                new_ctx["food_categories"] = food_categories

                                # Assign meal_type (no init_list)
                                new_ctx["meal_type"] = (
                                    update_response_data.get("mealTime")
                                    if update_response_data and update_response_data.get("mealTime")
                                    else vision_response_data.get("mealTime")
                                    if vision_response_data and vision_response_data.get("mealTime")
                                    else "Unknown"
                                )

                                # user_information extras
                                user_info = ctx_data.get("user_information", {})
                                if isinstance(user_info, dict):
                                    if "nd_score" in user_info:
                                        new_ctx["nd_score"] = user_info["nd_score"]
                                    if "nd_deduction_components" in user_info:
                                        new_ctx["nd_components"] = user_info["nd_deduction_components"]

                                # Filter allowed keys and sort alphabetically
                                ctx_data = dict(sorted(
                                    {k: v for k, v in new_ctx.items() if k in allowed_keys}.items()
                                ))

                        except Exception as e:
                            logger.warning(
                                f"Could not parse generate_feedback JSON for image_id {row_dict['image_id']}: {e}"
                            )
                            ctx_data = None

                    if ctx_data and isinstance(ctx_data, dict) and len(ctx_data) > 0:
                        results.append({
                            "image_id": row_dict.get("image_id"),
                            "ctx_data": ctx_data
                        })

                return results

        except Exception as e:
            logger.error("Failed to fetch feedback logs for images %s: %s", image_ids, e)
            return []
        finally:
            db.release_conn(conn)