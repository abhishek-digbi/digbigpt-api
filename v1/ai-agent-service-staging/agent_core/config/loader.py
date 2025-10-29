from __future__ import annotations
import logging

from utils.db import DBClient
from .schema import AgentConfig

logger = logging.getLogger(__name__)

_db: DBClient | None = None


def _get_db() -> DBClient | None:
    global _db
    if _db is None:
        try:
            _db = DBClient()
        except Exception as e:
            logger.warning(f"Could not connect to PostgreSQL for agent config (using YAML fallback): {e}")
            _db = None
    return _db

def _fetch_agent_row(agent_id: str) -> dict | None:
    db = _get_db()
    if db is None:
        # PostgreSQL not available - agents will load from YAML via ai_core_service
        logger.debug(f"PostgreSQL not available, agents will load from YAML for {agent_id}")
        return None
    
    conn = db.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM agents WHERE id = %s",
                (agent_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            columns = [desc[0] for desc in cur.description]
            return dict(zip(columns, row))
    finally:
        db.release_conn(conn)

def get_agent_cfg(agent_id: str) -> AgentConfig:
    row = _fetch_agent_row(agent_id)
    if not row:
        raise KeyError(f"Agent '{agent_id}' not found")
    return AgentConfig(**row)
