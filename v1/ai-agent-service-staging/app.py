from app import create_app
from utils.db import DBClient
import atexit
import logging

logger = logging.getLogger(__name__)

# Create a shared database client and application instance
# PostgreSQL is optional - app works with SQLite databases for agents and claims
try:
    _db_client = DBClient()
    logger.info("Connected to PostgreSQL database")
except Exception as e:
    logger.warning(f"Could not connect to PostgreSQL (this is OK, using SQLite): {e}")
    _db_client = None

app = create_app(db_client=_db_client)

if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 9000))
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)


@atexit.register
def close_pool():
    if _db_client:
        _db_client.close()
