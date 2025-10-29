from __future__ import annotations

from utils.db import DBClient
from .schema import AgentConfig

_db: DBClient | None = None


def _get_db() -> DBClient:
    global _db
    if _db is None:
        _db = DBClient()
    return _db

def _fetch_agent_row(agent_id: str) -> dict | None:
    conn = _get_db().get_conn()
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
        _get_db().release_conn(conn)

def get_agent_cfg(agent_id: str) -> AgentConfig:
    row = _fetch_agent_row(agent_id)
    if not row:
        raise KeyError(f"Agent '{agent_id}' not found")
    return AgentConfig(**row)
