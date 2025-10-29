# **AI Agent Service** 🤖
### **Modular AI Agent Framework with Extensible Architecture**
This project is a **FastAPI-based Agentic AI Framework** that provides a flexible foundation for building and orchestrating AI agents. While it currently includes specific health and nutrition features, the framework is designed to be **domain-agnostic** and extensible for various AI agent applications.

> **Note:** Some domain-specific features (e.g., health and nutrition analysis) are planned to be moved to dedicated services in the near future, while this service will focus on providing core agent orchestration capabilities.

---

## **📌 Core Capabilities**

### **Framework Features**
✅ **Agent Orchestration** – Coordinate and manage multiple AI agents  
✅ **Modular Architecture** – Easily extendable with custom agents and tools  
✅ **Async Processing** – Built for high-concurrency AI operations  
✅ **Monitoring & Observability** – Built-in metrics and logging  

### **Current Implementation (To be Refactored)**
⚠️ **Vision Analysis** – Identifies food in images  
⚠️ **Nutrition Insights** – Evaluates meals & provides nutrition scores  
⚠️ **Q&A System** – Domain-specific question answering

---

## **📂 Project Structure**
```
food-rating-service/
├── agent_core/            # Core agent services
│   ├── services/         # Core service implementations
│   └── adapters/        # External service adapters
├── tools/               # Tool registry and data access layer
├── orchestrator/         # Orchestrator layer for AI agents
│   ├── api/             # API controllers and endpoints
│   ├── orchestrators/   # AI agent orchestrators
│   ├── services/        # Orchestrator-specific services
│   └── config/          # Configuration files
├── app/                 # Main application components
├── docs/                # Documents for workflows
├── utils/              # General utility functions
├── tests/              # Test files and configurations
├── .env                # Environment variables
├── requirements.txt    # Project dependencies
├── app.py              # Main application entry point
└── deploy.sh           # Deployment script
```

## **🛠️ Development Quick Start**

1. **Clone and Install**
   ```bash
   git clone <repository-url>
   cd food-rating-service
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your local settings
   ```

3. **Start Development Server**
   ```bash
   python app.py
   ```
   The interactive Swagger UI will be available at `http://localhost:9000/docs`.

4. **Run Tests**
   ```bash
   pytest tests/
   ```

## **📊 Monitoring & Logs**
- Logs stored in `logs/`:
  - **`app.log`** → API activity
- Metrics are exported via **Grafana Alloy** using OpenTelemetry.
- Agent workflows are traced using [openai-agents](https://github.com/openai/openai-agents-python). Ensure `OPENAI_API_KEY` is set to export traces to the OpenAI dashboard.

---

## **🛠 Tech Stack**

### **Core Framework**
✅ **FastAPI** – High-performance API framework  
✅ **Pydantic** – Data validation and settings management  
✅ **Asyncio** – Asynchronous task processing  

### **AI**
✅ **OpenAI** – LLM integration  
✅ **LangFuse** – Prompt management and observability  

### **Infrastructure**
✅ **Redis** – Caching and message broker  
✅ **PostgreSQL** – Persistent storage  
✅ **Gunicorn** – Production server  
✅ **Grafana Alloy** – Metrics pipeline

---

## **Architecture**

### Core Framework Components
- `agent_core/`: Core framework components
  - `services/`: Core agent services and abstractions
  - `adapters/`: External service integrations
  - `utils/`: Framework utilities
  - `models/`: Data models and schemas
- `tools/`: Tool registry and data aggregation services

### Agent Orchestration
- `orchestrator/`: Agent orchestration layer
  - `api/`: REST API endpoints
  - `orchestrators/`: Agent coordination logic
  - `services/`: Orchestration services
  - `config/`: Agent configurations

### Application Layer
- `app/`: Application entry points
- `utils/`: Application utilities
- `config/`: Application configuration

### Supporting Files
- `requirements.txt`: Python package dependencies
- `.env`: Environment configuration
- `deploy.sh`: Deployment script
- `tests/`: Test suite directory
- `logs/`: Application log files

## **API Reference**

### 2️⃣ Tools API
- See `docs/tools_api.md` for endpoints to:
  - List tools: `GET /api/tools`
  - Execute tools: `POST /api/tools/execute/{tool_name}`
  - Resolve variables: `POST /api/tools/variables`

### 1️⃣ Agent Management API
#### **🔹 POST `/api/meal-rating`**
**Description:** Processes meal ratings with AI analysis (asynchronous)

✅ **Request Body:**
```json
{
  "meal_info": {
    "image_id": "123",
    "image_url": "https://example.com/meal.jpg",
    "meal_description": "Grilled chicken salad with mixed greens"
  },
  "meta_data": {
    "feature_tag": "DIGBI"
  },
  "user_info": {
    "user_token": "user_001"
  },
  "meal_info": {
    "cgm_meal_context": {
      "meal_time": "lunch"
    }
  }
}
```

✅ **Response (202 Accepted):**
```json
{
  "message": "Request accepted",
  "status": 202
}
```

#### **🔹 GET `/api/meal-rating/logs`**
**Description:** Retrieves filtered meal rating logs

✅ **Query Parameters:**
- `image_id`: Required - ID of the meal image

✅ **Response (200 OK):**
```json
{
  "message": "Success",
  "status": 200,
  "logs": [
    {
      "image_id": "123",
      "analysis_result": "Grilled chicken, mixed greens, avocado",
      "timestamp": "2025-05-20T14:13:45+05:30"
    }
  ]
}
```

#### **🔹 GET `/api/meal-rating/user-logs`**
**Description:** Retrieves `generate_feedback` entries for all meals of a user.

✅ **Headers:**
- `user-id`: **Required** – User token

✅ **Query Parameters (all required):**
- `startDate`: Start date in `YYYY-MM-DD` format
- `endDate`: End date in `YYYY-MM-DD` format
- `maxMeals`: Maximum number of meals to fetch

✅ **Response (200 OK):**
```json
{
  "message": "Success",
  "status": 200,
  "result": [
    {
      "image_id": "123",
      "generate_feedback": "Great choice!"
    }
  ]
}
```

### 4️⃣ Ask Digbi API
#### **🔹 POST `/api/ask-digbi`**
**Description:** Sends health-related questions to Digbi AI

✅ **Request Body:**
```json
{
  "query": "What are the best exercises for diabetes?",
  "query_id": "12345",
  "context": {
    "conversation_summary": "User is interested in fitness",
    "user_type": "DIGBI"
  },
  "user_token": "user_001"
}
```

✅ **Response (202 Accepted):**
```json
{
  "message": "Request accepted",
  "status": 202
}
```

✅ **Callback Response:**
```json
{
  "query_id": "12345",
  "response": "Regular walking, swimming, and resistance training can help.",
  "conversation_summary": "Discussed diabetes-friendly exercises"
}
```

### 5️⃣ Health Check API
#### **🔹 GET `/api/health`**
**Description:** Basic health check endpoint

✅ **Response (200 OK):**
```json
{
  "status": "healthy",
  "timestamp": "2025-05-20T14:13:45+05:30",
  "version": "1.0.0"
}
```

### Error Handling
All endpoints follow consistent error handling patterns:

❌ **400 Bad Request:**
```json
{
  "message": "Invalid request payload",
  "status": 400,
  "error": "Missing required field: meal_info"
}
```

❌ **500 Internal Server Error:**
```json
{
  "message": "Internal server error",
  "status": 500,
  "error": "Failed to process image analysis"
}
```

### API Best Practices
1. All requests should include proper authentication tokens
2. Use appropriate content-type headers (application/json)
3. Handle asynchronous responses appropriately
4. Implement proper error handling in client code
5. Use rate limiting and caching where appropriate
6. Validate input data before sending requests

## **Agent System Architecture**

The project uses a modular agent system with clear separation of concerns:

### Core Components
1. **AiCoreService** (in `agent_core/services/ai_core_service.py`)
   - Central orchestrator for AI workflows
   - Handles configuration validation, prompt management, and adapter dispatch
   - Provides error handling and observability

2. **Agents** (in `orchestrator/orchestrators/`)
   - Specialized AI agents for different tasks
   - Each agent implements specific functionality
   - Current agents:
     - `NutritionAgent`: Handles nutritional analysis
     - `AskDigbiAgent`: Q&A functionality
     - `SensitivityAgent`: Sensitivity analysis
     - `PersonalizationAgent`: Personalization tasks

## **🚀 Setup & Deployment**

### **Local Development**

1. **Start Required Services**
   Ensure PostgreSQL and Redis are running (see [Local Development Requirements](#local-development-requirements)).

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set Up Database**
   ```bash
   # Apply database migrations
   alembic upgrade head
   
   ```

4. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run Development Server**
   ```bash
   python app.py
   ```
   The API will be available at `http://localhost:5001`

6. **Run Tests**
   ```bash
   # Run all tests
   pytest tests/
   
   # Run specific test file
   pytest tests/test_agents.py -v
   ```

### **Production Deployment**

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Production Environment**
   - Set `ENV=production` and `DEBUG=False` in `.env`
   - Configure production database and cache settings
   - Set up SSL certificates if needed

3. **Run with Gunicorn**
   ```bash
   gunicorn --workers 4 \
            --worker-class uvicorn.workers.UvicornWorker \
            --bind 0.0.0.0:9000 \
            --timeout 120 \
            --log-level info \
            --access-logfile - \
            --error-logfile - \
            "app:create_app()"
   ```

4. **Using Systemd (Recommended)**
   Create a systemd service file at `/etc/systemd/system/agentic-ai.service`:
   ```ini
   [Unit]
   Description=Agentic AI Framework
   After=network.target

   [Service]
   User=your_user
   WorkingDirectory=/path/to/project
   EnvironmentFile=/path/to/.env
   ExecStart=/path/to/venv/bin/gunicorn \
       --workers 4 \
       --worker-class uvicorn.workers.UvicornWorker \
       --bind 0.0.0.0:9000 \
       --timeout 120 \
       "app:create_app()"
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

   Then enable and start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable agentic-ai
   sudo systemctl start agentic-ai
   ```

## **Agent Configuration**

Agent configurations are stored in the PostgreSQL database table `agents`. The `agent_core/agents.yaml` file serves as an initial seed for the agents table during the first run or when explicitly seeded.

### **Seeding Agents**

1. **Automatic Seeding**: On application startup, if the agents table is empty, the system will automatically seed it with the agents defined in `agent_core/agents.yaml`.

### **Environment Configuration**
The `AGENT_CONFIG_PATH` environment variable can be set to specify a custom YAML file for agent configurations. If not set, it defaults to `agent_core/agents.yaml`.

Example `.env` setting:
```
AGENT_CONFIG_PATH=agent_core/agents.production.yaml
```

### **Local Development Requirements**
Before starting the application, ensure these services are running:

1. **PostgreSQL**
   ```bash
   # Using Homebrew (macOS)
   brew install postgresql
   brew services start postgresql
   
   # Create database and user (if not exists)
   createdb digbi_db
   createuser -s digbi_user
   ```

2. **Redis**
   ```bash
   # Using Homebrew (macOS)
   brew install redis
   brew services start redis
   ```

3. **Environment Variables**
   Update your `.env` file with the correct database and Redis configurations:
   ```
   # Database
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=digbi_db
   DB_USER=digbi_user
   
   # Redis
   REDIS_HOST=localhost
   REDIS_PORT=6379
   ```

## **Development**

The project follows a modular architecture with clear separation of concerns:
- Core services in `agent_core/` handle fundamental AI operations
- Orchestrators in `orchestrator/` manage complex workflows
- API controllers expose endpoints for external interaction
- Utilities provide common functionality across components

Each component is designed to be independent yet work together seamlessly through well-defined interfaces.

### Function Tools

Agent workflows can leverage **function tools**. Any Python function can be converted into a reusable tool by decorating it with `@tool` from the `tools` package. Decorated tools are automatically added to a global registry so they can be referenced by name in an agent's configuration. Tools may also be provided directly when calling `AiCoreService.run_agent`. All custom tools are merged with those defined in the configuration and the built-ins exposed by `ToolService` before execution.

Both synchronous and asynchronous functions are supported when defining tools.

The `ToolService` exposes built-in tools for fetching API variables (e.g. `get_gut_report_data`). See the [Tools Overview](docs/tools_overview.md) and [Example Agent with Tools](docs/example_function_tools_agent.md) for more details.

## Documentation

Additional documentation for core workflows is available in the [docs](docs/) directory:

- [Ask Digbi Workflow](docs/ask_digbi_workflow.md)
- [Meal Rating Workflow](docs/meal_rating_workflow.md)
- [Project Overview](docs/overview.md)
- [Agent Management API](docs/agent_management_api.md)
- [Example Agent with Tools](docs/example_function_tools_agent.md)
- [Understanding Agents](docs/agent_basics.md)
- [Vector Store API](docs/vector_store_api.md)
- [Tools Overview](docs/tools_overview.md)
- [Hooks Integration](docs/hooks_integration.md)
- [OpenAI Service Message Inputs](docs/openai_service_message_inputs.md)
- [Guardrails Integration](docs/guardrails.md)
- [Knowledge Base Usage Tracking](docs/knowledge_base_usage.md)
- [Retry With Run Input List](docs/retry_patterns/retry_with_run_input_list.md)
- [Retry With Run Output](docs/retry_patterns/retry_with_run_output.md)
