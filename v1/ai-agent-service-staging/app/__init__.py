"""Application factory using FastAPI."""

from fastapi import FastAPI
from dotenv import load_dotenv
import os
# from agents import enable_verbose_stdout_logging  # Commented out - package not available
from agent_core.services.adapters.adapter_registry import AdapterRegistry
from agent_core.services.ai_core_service import AiCoreService
from tools import ToolService
# Import services and agents
from agent_core.services.prompt_management.langfuse_service import LangFuseService
from agent_core.services.adapters.openai_service import OpenAIService
from openai import AsyncOpenAI
from orchestrator.services.vector_store_service import VectorStoreService
from orchestrator.orchestrators.edutainment_agent_gus import EdutainmentAgentGus
from orchestrator.orchestrators.recipe_agent import RecipeAgent
from orchestrator.orchestrators.recipe_agent_enhanced import RecipeAgentEnhanced
from orchestrator.orchestrators.vision_agent import VisionAgent
from orchestrator.orchestrators.sensitivity_agent import SensitivityAgent
from orchestrator.orchestrators.nutrition_agent import NutritionAgent
from orchestrator.orchestrators.health_insights_agent import HealthInsightsAgent
from orchestrator.orchestrators.personalization_agent import PersonalizationAgent
from orchestrator.orchestrators.ask_digbi_agent import AskDigbiAgent
from orchestrator.orchestrators.support_agent import SupportAgent
from orchestrator.orchestrators.unified_support_agent import UnifiedSupportAgent
from orchestrator.orchestrators.summarizer_agent import SummarizerAgent
from orchestrator.orchestrators.renewal_agent import RenewalAgent
from orchestrator.orchestrators.cgm_summary_report_agent import CGMSummaryReportAgent
from orchestrator.orchestrators.digbigpt_orchestrator import DigbiGPTOrchestrator
from orchestrator.services.database_agent_logger import DatabaseAgentLogger
import redis

from agent_core.config.logging_config import logger
from orchestrator.repositories.agent_logs_repository import AgentLogsRepository
from utils.db import DBClient
from utils.db_setup import initialize_database

def create_app(db_client: DBClient | None = None):
    # enable_verbose_stdout_logging()
    app = FastAPI(
        title="Agentic AI Framework Service",
        description="API service orchestrating Digbi AI agents",
        version="0.1.0",
    )
    logger.info("Server is starting...")

    from orchestrator.api.routes import router as api_router
    app.include_router(api_router)

    @app.get("/")
    async def health_check():
        return {"message": "Server is running!", "status": 200}


    load_dotenv()
    if db_client is None:
        try:
            db_client = DBClient()
            logger.info("Connected to PostgreSQL for agent logs")
        except Exception as e:
            logger.warning(f"Could not connect to PostgreSQL for agent logs (using SQLite): {e}")
            db_client = None
    app.state.DB_CLIENT = db_client

    # Ensure required tables exist and seed default agents if necessary
    try:
        initialize_database(db_client)
    except Exception as e:
        logger.error("Database initialization failed: %s", e)

    env = os.getenv("ENV")

    redisClient = redis.StrictRedis(
        host='localhost', port=6379, db=0, decode_responses=True
    )

    from utils.cache import set_cache
    set_cache(redisClient)

    # Initialize services
    langfuse = LangFuseService(
        env=env,
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        host=os.getenv("LANGFUSE_HOST"),
    )

    # Initialize services
    openai_service = OpenAIService(api_key=os.getenv("OPENAI_API_KEY"))
    openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    vector_store_service = VectorStoreService(openai_client)
    adapter_registry = AdapterRegistry(openai_service)
    data_core = ToolService(db_client)
    
    # Initialize logging components
    agent_logs_repo = AgentLogsRepository(db_client)
    agent_logger = DatabaseAgentLogger(agent_logs_repo)
    
    # Initialize AI Core Service with the logger
    ai_core_service = AiCoreService(
        langfuse=langfuse,
        registry=adapter_registry,
        data_core=data_core,
        agent_logger=agent_logger
    )

    # Initialize agents
    edutainment_agent_gus = EdutainmentAgentGus(ai_core_service)
    vision_agent = VisionAgent(ai_core_service, langfuse)
    sensitivity_agent = SensitivityAgent(ai_core_service)
    user_profile_agent = PersonalizationAgent(ai_core_service)
    health_insights_agent = HealthInsightsAgent(ai_core_service)
    renewal_agent = RenewalAgent(ai_core_service)
    nutrition_agent = NutritionAgent(
        ai_core_service,
        langfuse,
        sensitivity_agent,
        user_profile_agent,
        data_core,
        db_client,
    )
    recipe_agent_enhanced = RecipeAgentEnhanced(
        langfuse, ai_core_service, data_core, nutrition_agent, sensitivity_agent
    )
    recipe_agent = RecipeAgent(
        langfuse,
        ai_core_service,
        data_core,
        nutrition_agent,
        sensitivity_agent,
        recipe_agent_enhanced=recipe_agent_enhanced,
    )
    support_agent = SupportAgent(ai_core_service)
    unified_support_agent = UnifiedSupportAgent(ai_core_service)
    cgm_summary_report_agent = CGMSummaryReportAgent(ai_core_service)
    summarizer_agent = SummarizerAgent(ai_core_service)
    terminal_agents_config = os.getenv("ASK_DIGBI_TERMINAL_AGENTS")
    terminal_agents = (
        [agent.strip() for agent in terminal_agents_config.split(",") if agent.strip()]
        if terminal_agents_config
        else []
    )
    ask_digbi_agent = AskDigbiAgent(
        ai_core_service,
        health_insights_agent,
        nutrition_agent,
        user_profile_agent,
        support_agent,
        summarizer_agent,
        recipe_agent,
        terminal_agents=terminal_agents,
    )
    
    # Initialize DigbiGPT orchestrator for claims analysis
    digbigpt_orchestrator = DigbiGPTOrchestrator(ai_core_service)

    # Store agents globally in the app context
    app.state.AGENTS = {
        "vision_agent": vision_agent,
        "sensitivity_agent": sensitivity_agent,
        "nutrition_agent": nutrition_agent,
        "health_insights_agent": health_insights_agent,
        "ask_digbi_agent": ask_digbi_agent,
        "User Profile Agent": user_profile_agent,
        "support_agent": support_agent,
        "renewal_agent": renewal_agent,
        "recipe_agent": recipe_agent,
        recipe_agent_enhanced.agent_id: recipe_agent_enhanced,
        "cgm_summary_report_agent": cgm_summary_report_agent,
        "summarizer_agent": summarizer_agent,
        edutainment_agent_gus.agent_id: edutainment_agent_gus,
        unified_support_agent.agent_id: unified_support_agent,
        "digbigpt_orchestrator": digbigpt_orchestrator
    }

    app.state.AI_CORE_SERVICE = ai_core_service
    app.state.VECTOR_STORE_SERVICE = vector_store_service

    app.state.ASK_DIGBI_CALLBACK_URL = os.getenv('DIGBI_URL') + os.getenv('ASK_DIGBI_RESPONSE_PATH')
    app.state.MEAL_RATING_CALLBACK_URL = os.getenv('DIGBI_URL') + os.getenv('MEAL_RATING_RESPONSE_PATH')
    app.state.DIGBI_USER_AUTH_TOKEN = os.getenv('DIGBI_USER_AUTH_TOKEN')

    # Store repositories in the app state
    app.state.repositories = {
        "agent_logs_repo": agent_logs_repo
    }
    logger.info("Server started successfully!")
    return app
