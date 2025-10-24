from app import create_app
from utils.db import DBClient
import atexit

# Create a shared database client and application instance
_db_client = DBClient()
app = create_app(db_client=_db_client)

if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 9000))
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)


@atexit.register
def close_pool():
    _db_client.close()
