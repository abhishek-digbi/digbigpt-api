"""Application factory using FastAPI."""

from fastapi import FastAPI
from dotenv import load_dotenv
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title="DigbiGPT API Service",
        description="AI assistant for analyzing healthcare claims data",
        version="1.0.0",
    )
    
    logger.info("DigbiGPT server is starting...")

    # Load environment variables
    load_dotenv()

    # Try to get database client (with fallback)
    try:
        from src.utils.db import get_db_client
        db_client = get_db_client()
        app.state.DB_CLIENT = db_client
        logger.info(f"Database client initialized: {type(db_client).__name__}")
    except Exception as e:
        logger.warning(f"Running without agent config database: {e}")
        app.state.DB_CLIENT = None

    # Include API routes
    from src.api.routes import router as api_router
    app.include_router(api_router)

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "message": "DigbiGPT API Service",
            "version": "1.0.0",
            "status": "running"
        }

    @app.get("/api/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "service": "DigbiGPT API",
            "version": "1.0.0",
            "timestamp": "2024-01-15T10:30:00Z"
        }

    logger.info("DigbiGPT server started successfully!")
    return app