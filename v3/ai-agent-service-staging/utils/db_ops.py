import logging
from typing import Any, Dict, List

from orchestrator.services.meal_rating_log_entry import MealRatingLogEntry, MealRatingLogService
from orchestrator.services.agent_config_service import AgentConfigService
from agent_core.config.schema import AgentConfig
from utils.db import DBClient
import json

logger = logging.getLogger(__name__)


def insert_row_meal_rating_logs(request_context: Dict[str, Any], db: DBClient) -> None:
    """Persist a meal rating log entry."""
    log_entry = MealRatingLogEntry.from_request_context(request_context)
    inserted_id = MealRatingLogService.insert_log(log_entry, db)
    if inserted_id is None:
        logger.error("Could not log meal rating for context %s", request_context)
    else:
        logger.info("Logged meal rating entry %s", inserted_id)


def get_filtered_meal_rating_logs(image_id: str, db: DBClient) -> List[Dict[str, Any]]:
    """Return all logs for a given image."""
    return MealRatingLogService.fetch_logs(image_id, db)


def get_generate_feedback_logs_for_images(
    image_ids: List[str], db: DBClient
) -> List[Dict[str, Any]]:
    """Return generate_feedback logs for provided image IDs."""
    return MealRatingLogService.fetch_feedback_for_images(image_ids, db)


def get_agent_logs_for_context_ids(
    context_ids: List[str], agent_id: str, db: DBClient
) -> List[Dict[str, Any]]:
    """Return agent_logs rows filtered by context_id list and agent_id.

    Parses JSON fields where appropriate (response, model_context, metadata).
    """
    if not context_ids:
        return []

    sql = (
        """
        SELECT id, agent_id, prompt, response, timestamp, context_id, user_token,
               model_context, metadata, duration, created_at
        FROM agent_logs
        WHERE agent_id = %s AND context_id = ANY(%s)
        ORDER BY timestamp DESC
        """
    )

    conn = db.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (agent_id, context_ids))
            columns = [d[0] for d in cur.description]
            rows = cur.fetchall()

            results: List[Dict[str, Any]] = []
            for row in rows:
                d = dict(zip(columns, row))

                # Best-effort parse for JSON string fields
                for key in ("response", "model_context", "metadata"):
                    val = d.get(key)
                    if isinstance(val, str):
                        try:
                            d[key] = json.loads(val)
                        except Exception:
                            # keep original string if not JSON
                            pass
                results.append(d)

            return results
    except Exception:
        logger.error(
            "Failed to fetch agent_logs for context_ids %s and agent_id %s",
            context_ids,
            agent_id,
            exc_info=True,
        )
        return []
    finally:
        db.release_conn(conn)


def insert_agent_config(cfg: AgentConfig, db: DBClient) -> None:
    """Insert a new agent configuration."""
    AgentConfigService.insert_agent(cfg, db)


def update_agent_config(cfg: AgentConfig, db: DBClient) -> None:
    """Update an existing agent configuration."""
    AgentConfigService.update_agent(cfg, db)
