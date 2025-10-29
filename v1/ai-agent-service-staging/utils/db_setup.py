import yaml
import logging
from pathlib import Path

from agent_core.config.schema import AgentConfig
from orchestrator.services.agent_config_service import AgentConfigService
from utils.db import DBClient

logger = logging.getLogger(__name__)

CREATE_AGENTS_SQL = """
CREATE TABLE IF NOT EXISTS agents (
        id text NOT NULL,
        "name" text NOT NULL,
        provider text NOT NULL,
        model text NOT NULL,
        langfuse_prompt_key text NOT NULL,
        text_format text NULL,
        assistant_id text NULL,
        instructions text NULL,
        vector_store_ids _text NULL,
        tools _text NULL,
        temperature numeric NULL,
        top_p numeric NULL,
        CONSTRAINT agents_pkey PRIMARY KEY (id)
);
"""

CREATE_MEAL_RATING_LOGS_SQL = """
CREATE TABLE  IF NOT EXISTS meal_rating_logs (
	id serial4 NOT NULL,
	image_id int8 NOT NULL,
	user_token text NOT NULL,
	created_at timestamptz NOT NULL DEFAULT now(),
	updated_at timestamptz NOT NULL DEFAULT now(),
	request jsonb NULL,
	errors jsonb NULL,
	food_post_id int8 NULL,
	user_data_used jsonb NULL,
	agent_interactions jsonb NULL,
	miscellaneous jsonb NULL,
	CONSTRAINT meal_rating_logs_pkey PRIMARY KEY (id)
);
CREATE INDEX  IF NOT EXISTS idx_meal_rating_logs_image_id ON public.meal_rating_logs USING btree (image_id);
"""

CREATE_AGENT_LOGS_SQL = """
CREATE TABLE IF NOT EXISTS agent_logs (
    id SERIAL PRIMARY KEY,
    agent_id TEXT,
    prompt TEXT,
    response TEXT,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    context_id TEXT,
    user_token TEXT,
    model_context JSONB,
    metadata JSONB,
    duration NUMERIC,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_AGENT_LOGS_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_agent_logs_context_id ON agent_logs(context_id);
"""

ALTER_AGENT_LOGS_DURATION_SQL = """
ALTER TABLE agent_logs
ADD COLUMN IF NOT EXISTS duration NUMERIC;
"""


def create_tables(db: DBClient) -> None:
    """Create required tables if they do not exist."""
    conn = db.get_conn()
    try:
        with conn.cursor() as cur:
            # Create tables
            cur.execute(CREATE_AGENTS_SQL)
            cur.execute(CREATE_MEAL_RATING_LOGS_SQL)
            cur.execute(CREATE_AGENT_LOGS_SQL)

            # Ensure duration column exists
            cur.execute(ALTER_AGENT_LOGS_DURATION_SQL)

            # Create indexes
            cur.execute(CREATE_AGENT_LOGS_INDEX_SQL)
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Failed creating tables")
        raise
    finally:
        db.release_conn(conn)


def seed_agents_from_yaml(db: DBClient, yaml_path: str) -> None:
    """Seed the agents table with data from a YAML file."""
    path = Path(yaml_path)
    if not path.exists():
        logger.warning("Agents YAML file not found: %s", yaml_path)
        return

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    for agent_id, cfg in data.items():
        try:
            agent_cfg = AgentConfig(
                id=agent_id,
                name=cfg.get("name", agent_id),
                provider=cfg.get("provider", "openai"),
                model=cfg.get("model", "gpt-4o"),
                langfuse_prompt_key=cfg.get("langfuse_prompt_key"),
                text_format=cfg.get("text_format"),
                assistant_id=cfg.get("assistant_id"),
                instructions=cfg.get("instructions"),
                vector_store_ids=cfg.get("vector_store_ids"),
                tools=cfg.get("tools"),
                temperature=cfg.get("temperature"),
                top_p=cfg.get("top_p"),
            )
            AgentConfigService.insert_agent(agent_cfg, db)
        except Exception:
            logger.exception("Failed to insert agent %s", agent_id)


def initialize_database(db: DBClient) -> None:
    """Ensure tables exist and seed the agents table if empty."""
    create_tables(db)
    conn = db.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM agents")
            row = cur.fetchone()
            count = row[0] if row else 0
    except Exception:
        conn.rollback()
        logger.exception("Failed checking agents table")
        raise
    finally:
        db.release_conn(conn)

    if count == 0:
        yaml_file = Path(__file__).resolve().parent.parent / "agent_core" / "agents_seed.yaml"
        seed_agents_from_yaml(db, str(yaml_file))
