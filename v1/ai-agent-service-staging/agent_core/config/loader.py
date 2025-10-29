from __future__ import annotations
import logging
import yaml
from pathlib import Path

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

def _load_from_yaml(agent_id: str) -> AgentConfig:
    """Load agent configuration from YAML file as fallback when database unavailable."""
    yaml_file = Path(__file__).parent / "agents_seed.yaml"
    if not yaml_file.exists():
        raise FileNotFoundError(f"Agents YAML file not found: {yaml_file}")
    
    with yaml_file.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    
    cfg_data = data.get(agent_id)
    if not cfg_data:
        raise KeyError(f"Agent '{agent_id}' not found in YAML")
    
    # Convert YAML format to AgentConfig
    return AgentConfig(
        id=agent_id,
        name=cfg_data.get("name", agent_id),
        provider=cfg_data.get("provider", "openai"),
        model=cfg_data.get("model", "gpt-4o"),
        langfuse_prompt_key=cfg_data.get("langfuse_prompt_key"),
        text_format=cfg_data.get("text_format"),
        assistant_id=cfg_data.get("assistant_id"),
        instructions=cfg_data.get("instructions"),
        vector_store_ids=cfg_data.get("vector_store_ids"),
        tools=cfg_data.get("tools", []),
        temperature=cfg_data.get("temperature"),
        top_p=cfg_data.get("top_p"),
    )

def get_agent_cfg(agent_id: str) -> AgentConfig:
    row = _fetch_agent_row(agent_id)
    if not row:
        # Database not available or agent not found - fallback to YAML
        logger.info(f"Loading agent {agent_id} from YAML fallback")
        return _load_from_yaml(agent_id)
    return AgentConfig(**row)
