from src.app import create_app
import atexit

# Create application instance
app = create_app()

if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 9000))
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)
