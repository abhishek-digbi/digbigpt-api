import os
import logging
from dotenv import load_dotenv
from psycopg2 import pool

load_dotenv()

DB_PARAMS = {
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
}

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
