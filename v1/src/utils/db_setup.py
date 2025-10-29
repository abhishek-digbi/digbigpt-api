"""
Database setup and initialization for DigbiGPT.
"""

import logging
from src.utils.db import DBClient

logger = logging.getLogger(__name__)

def initialize_database(db_client: DBClient) -> None:
    """
    Initialize database tables and seed default agents if necessary.
    
    Args:
        db_client: Database client instance
    """
    try:
        conn = db_client.get_conn()
        with conn.cursor() as cur:
            # Create agents table if it doesn't exist
            cur.execute("""
                CREATE TABLE IF NOT EXISTS agents (
                    id VARCHAR(255) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    provider VARCHAR(100) DEFAULT 'openai',
                    model VARCHAR(100) DEFAULT 'gpt-4o',
                    langfuse_prompt_key VARCHAR(255),
                    text_format VARCHAR(50),
                    assistant_id VARCHAR(255),
                    instructions TEXT,
                    vector_store_ids TEXT,
                    tools TEXT,
                    temperature FLOAT,
                    top_p FLOAT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create agent_logs table if it doesn't exist
            cur.execute("""
                CREATE TABLE IF NOT EXISTS agent_logs (
                    id SERIAL PRIMARY KEY,
                    agent_id VARCHAR(255),
                    user_token VARCHAR(255),
                    query TEXT,
                    response TEXT,
                    execution_time_ms INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    error TEXT
                )
            """)
            
            conn.commit()
            logger.info("Database tables initialized successfully")
            
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise
    finally:
        db_client.release_conn(conn)


