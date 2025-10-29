import logging
from utils.db import DBClient
from agent_core.config.schema import AgentConfig

logger = logging.getLogger(__name__)

class AgentConfigService:
    INSERT_SQL = """
        INSERT INTO agents (
            id, name, provider, model, langfuse_prompt_key,
            text_format, assistant_id, instructions, vector_store_ids,
            tools, temperature, top_p
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    UPDATE_SQL = """
        UPDATE agents SET
            name=%s, provider=%s, model=%s, langfuse_prompt_key=%s,
            text_format=%s, assistant_id=%s, instructions=%s,
            vector_store_ids=%s, tools=%s, temperature=%s, top_p=%s
        WHERE id=%s
    """

    SELECT_ALL_SQL = """
        SELECT id, name, provider, model, langfuse_prompt_key,
               text_format, assistant_id, instructions, vector_store_ids,
               tools, temperature, top_p
        FROM agents
    """

    @classmethod
    def insert_agent(cls, cfg: AgentConfig, db: DBClient) -> None:
        conn = db.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    cls.INSERT_SQL,
                    (
                        cfg.id,
                        cfg.name,
                        cfg.provider,
                        cfg.model,
                        cfg.langfuse_prompt_key,
                        cfg.text_format,
                        cfg.assistant_id,
                        cfg.instructions,
                        cfg.vector_store_ids,
                        cfg.tools,
                        cfg.temperature,
                        cfg.top_p,
                    ),
                )
            conn.commit()
            logger.info("Inserted agent %s", cfg.name)
        except Exception:
            conn.rollback()
            logger.exception("Failed to insert agent %s", cfg.name)
            raise
        finally:
            db.release_conn(conn)

    @classmethod
    def update_agent(cls, cfg: AgentConfig, db: DBClient) -> None:
        conn = db.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    cls.UPDATE_SQL,
                    (
                        cfg.name,
                        cfg.provider,
                        cfg.model,
                        cfg.langfuse_prompt_key,
                        cfg.text_format,
                        cfg.assistant_id,
                        cfg.instructions,
                        cfg.vector_store_ids,
                        cfg.tools,
                        cfg.temperature,
                        cfg.top_p,
                        cfg.id,
                    ),
                )
                if cur.rowcount == 0:
                    raise KeyError(f"Agent '{cfg.id}' not found")
            conn.commit()
            logger.info("Updated agent %s", cfg.name)
        except Exception:
            conn.rollback()
            logger.exception("Failed to update agent %s", cfg.name)
            raise
        finally:
            db.release_conn(conn)

    @classmethod
    def fetch_all_agents(cls, db: DBClient) -> list[AgentConfig]:
        """Retrieve all agent configurations from the database."""
        conn = db.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(cls.SELECT_ALL_SQL)
                rows = cur.fetchall()
            agents = [
                AgentConfig(
                    id=row[0],
                    name=row[1],
                    provider=row[2],
                    model=row[3],
                    langfuse_prompt_key=row[4],
                    text_format=row[5],
                    assistant_id=row[6],
                    instructions=row[7],
                    vector_store_ids=row[8],
                    tools=row[9],
                    temperature=row[10],
                    top_p=row[11],
                )
                for row in rows
            ]
            return agents
        except Exception:
            logger.exception("Failed fetching agents")
            raise
        finally:
            db.release_conn(conn)
