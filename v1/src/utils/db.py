import os
import logging
from pathlib import Path
from dotenv import load_dotenv
import duckdb
import sqlite3

load_dotenv()

# PostgreSQL parameters (optional)
DB_PARAMS = {
    "database": os.getenv("DB_NAME", "digbi_db"),
    "user": os.getenv("DB_USER", "digbi_user"),
    "password": os.getenv("DB_PASSWORD", "digbi_password"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
}

# Claims database parameters for DigbiGPT (PostgreSQL - optional)
CLAIMS_DB_PARAMS = {
    "database": os.getenv("CLAIMS_DB_NAME", "digbi_claims"),
    "user": os.getenv("CLAIMS_DB_USER", "digbi_user"),
    "password": os.getenv("CLAIMS_DB_PASSWORD", "digbi_password"),
    "host": os.getenv("CLAIMS_DB_HOST", "localhost"),
    "port": os.getenv("CLAIMS_DB_PORT", "5432"),
}

# DuckDB path for claims database
CLAIMS_DUCKDB_PATH = os.getenv(
    "CLAIMS_DB_PATH", 
    str(Path(__file__).parent.parent.parent / "data" / "claims.db")
)

logger = logging.getLogger(__name__)

def is_postgres_available() -> bool:
    """Check if PostgreSQL is available."""
    try:
        import psycopg2
        conn = psycopg2.connect(**DB_PARAMS, connect_timeout=3)
        conn.close()
        return True
    except Exception as e:
        logger.info(f"PostgreSQL not available: {e}")
        return False

class SQLiteDBClient:
    """Fallback database client using SQLite for agent configs."""
    
    def __init__(self, db_path: str = "data/agents.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._create_tables()
    
    def _create_tables(self):
        """Create necessary tables for agent configs."""
        cursor = self.conn.cursor()
        
        # Create agents table
        cursor.execute("""
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
        
        # Create agent_logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id VARCHAR(255),
                user_token VARCHAR(255),
                query TEXT,
                response TEXT,
                execution_time_ms INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                error TEXT
            )
        """)
        
        self.conn.commit()
    
    def get_conn(self):
        return self.conn
    
    def release_conn(self, conn):
        pass  # SQLite doesn't need connection pooling
    
    def close(self):
        if self.conn:
            self.conn.close()

def get_db_client():
    """Get database client with fallback."""
    if is_postgres_available():
        try:
            from psycopg2 import pool
            return DBClient()  # PostgreSQL
        except Exception as e:
            logger.warning(f"PostgreSQL connection failed: {e}")
    
    logger.info("Using SQLite fallback for agent configs")
    return SQLiteDBClient()

class DBClient:
    """Simple wrapper around a connection pool."""

    def __init__(self, params: dict | None = None, *, minconn: int = 1, maxconn: int = 10) -> None:
        self.pool = pool.SimpleConnectionPool(minconn=minconn, maxconn=maxconn, **(params or DB_PARAMS))

    def get_conn(self):
        return self.pool.getconn()

    def release_conn(self, conn):
        self.pool.putconn(conn)

    def close(self):
        if self.pool:
            self.pool.closeall()


class ClaimsDBClient:
    """Database client specifically for claims database operations."""

    def __init__(self, params: dict | None = None, *, minconn: int = 1, maxconn: int = 5) -> None:
        self.pool = pool.SimpleConnectionPool(minconn=minconn, maxconn=maxconn, **(params or CLAIMS_DB_PARAMS))

    def get_conn(self):
        return self.pool.getconn()

    def release_conn(self, conn):
        self.pool.putconn(conn)

    def close(self):
        if self.pool:
            self.pool.closeall()

    def test_connection(self) -> bool:
        """Test the claims database connection."""
        try:
            conn = self.get_conn()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                result = cur.fetchone()
                return result[0] == 1
        except Exception as e:
            logger.error(f"Claims database connection test failed: {e}")
            return False
        finally:
            self.release_conn(conn)


class DuckDBClient:
    """Database client for DuckDB operations (used for claims database)."""

    def __init__(self, db_path: str | None = None, read_only: bool = True) -> None:
        self.db_path = db_path or CLAIMS_DUCKDB_PATH
        self.read_only = read_only
        self._conn = None

        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"DuckDB database file not found: {self.db_path}")

    def get_conn(self):
        """Get a DuckDB connection (creates if not exists)."""
        if self._conn is None:
            self._conn = duckdb.connect(self.db_path, read_only=self.read_only)
        return self._conn

    def close(self):
        """Close the DuckDB connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def test_connection(self) -> bool:
        """Test the DuckDB connection."""
        try:
            conn = self.get_conn()
            result = conn.execute("SELECT 1").fetchone()
            return result[0] == 1
        except Exception as e:
            logger.error(f"DuckDB connection test failed: {e}")
            return False

    def execute_query(self, sql: str, params: dict | None = None):
        """Execute a SQL query and return results."""
        conn = self.get_conn()
        return conn.execute(sql, params or {}).fetchall()
