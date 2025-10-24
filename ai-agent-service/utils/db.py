import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from psycopg2 import pool
import duckdb

load_dotenv()

DB_PARAMS = {
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
}

# Claims database parameters for DigbiGPT
CLAIMS_DB_PARAMS = {
    "database": os.getenv("CLAIMS_DB_NAME"),
    "user": os.getenv("CLAIMS_DB_USER"),
    "password": os.getenv("CLAIMS_DB_PASSWORD"),
    "host": os.getenv("CLAIMS_DB_HOST"),
    "port": os.getenv("CLAIMS_DB_PORT", "5432"),
}

# DuckDB path for claims database
CLAIMS_DUCKDB_PATH = os.getenv(
    "CLAIMS_DB_PATH", 
    str(Path(__file__).parent.parent.parent / "claims.db")
)

logger = logging.getLogger(__name__)

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
