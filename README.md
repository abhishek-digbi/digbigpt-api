# DigbiGPT Claims Assistant

AI-powered healthcare claims analysis system with specialized agents for analyzing drug spend, clinical history, and population health metrics.

## 🎯 Features

- **Drug Spend Analysis**: Analyze medication costs and identify top spenders
- **Clinical History**: Track member diagnosis patterns and timelines  
- **Cohort Insights**: Generate population health metrics and disease cohort summaries
- **PHI Protection**: Automatic redaction of sensitive health information
- **Multi-Agent System**: Intelligent routing to specialized agents based on query intent

## 🏗️ Architecture

- **FastAPI** backend with OpenAI integration
- **3 Specialized AI Agents**:
  - `DRUG_SPEND_AGENT` - Medication cost and utilization analysis
  - `CLINICAL_HISTORY_AGENT` - Member diagnosis patterns and timelines
  - `COHORT_INSIGHTS_AGENT` - Population health metrics
- **DuckDB** for claims data storage
- **Built-in PHI redaction** and audit logging
- **OpenAI GPT-4** for natural language understanding

## 🚀 Quick Start

### Prerequisites

- Python 3.10+ (Python 3.11 recommended)
- OpenAI API key
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/abhishek-digbi/digbigpt-api.git
cd digbigpt-api

# Install dependencies
cd v1/ai-agent-service-staging
pip install -r requirements.txt

# Set up environment variables
cd ..
cp env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### Running Locally

```bash
# From the v1/ directory
cd v1

# Set Python path and start server
export PYTHONPATH="${PYTHONPATH}:$(pwd)/ai-agent-service-staging:$(pwd)"
cd ai-agent-service-staging
python3.11 app.py
```

The server will start on `http://localhost:9000`

### Testing

```bash
# Test health endpoint
curl http://localhost:9000/health

# Test with a query
curl -X POST http://localhost:9000/api/digbigpt/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show me top spenders on atorvastatin in 2023",
    "user_id": "test_user"
  }' | python3 -m json.tool
```

## 📡 API Endpoints

### POST /api/digbigpt/ask

Ask DigbiGPT a question about claims data.

**Request:**
```json
{
  "question": "Show me top spenders on atorvastatin in 2023",
  "user_id": "user123"
}
```

**Response:**
```json
{
  "answer": "Here are the top members with highest spend on Atorvastatin...",
  "table": {
    "columns": ["member_first_name", "member_last_name", "fill_count", "total_spend", ...],
    "rows": [
      ["SUSAN", "RYAN", 15, 4168.84, 277.92, "2023-01-29", "2023-12-01"],
      ...
    ]
  },
  "agent_used": "DRUG_SPEND_AGENT",
  "confidence": 0.9,
  "query_time_ms": 1234,
  "timestamp": "2025-10-28T..."
}
```

### GET /health

Health check endpoint.

## 🔐 Environment Variables

Required:
- `OPENAI_API_KEY` - Your OpenAI API key

Optional:
- `PORT` - Server port (default: 9000)
- `DATABASE_URL` - Database connection string (defaults to SQLite)
- `LANGFUSE_SECRET_KEY` - LangFuse API key (optional, for prompt management)
- `LANGFUSE_PUBLIC_KEY` - LangFuse public key (optional)

## 🧪 Example Queries

```bash
# Drug spending analysis
"Show me top spenders on atorvastatin in 2023"
"Who are the duplicate medication users?"
"What's the total spend on rosuvastatin?"

# Clinical history
"Show me diagnosis history with ICD codes"
"What are the GI medication new starts?"
"Display member clinical timelines"

# Cohort insights
"What are the population cohort metrics?"
"Show me disease cohort summary"
"Analyze the diabetes population health group"
```

## 🏥 Integration with ChatGPT Enterprise

This system can be integrated as a Custom GPT in ChatGPT Enterprise. See `v1/deployment/CustomGPT_Config.json` for the configuration.

### Quick Integration Steps:

1. Deploy this API to a public endpoint (Render, Railway, AWS Lambda, etc.)
2. Create a Custom GPT in ChatGPT
3. Import the OpenAPI spec from `deployment/CustomGPT_Config.json`
4. Update the API URL to your deployed endpoint
5. Test and share with your team

## 📁 Project Structure

```
v1/
├── ai-agent-service-staging/     # Main FastAPI application
│   ├── agent_core/                # Agent configuration and AI services
│   ├── orchestrator/              # Agent orchestrators and routing
│   ├── tools/                     # Tool definitions and services
│   ├── utils/                     # Utility functions
│   ├── app.py                     # FastAPI application entry point
│   └── requirements.txt           # Python dependencies
├── data/                          # Database files
│   ├── agents.db                  # Agent configurations
│   └── claims.db                  # Claims data (DuckDB)
├── deployment/                    # Deployment configurations
│   └── CustomGPT_Config.json      # ChatGPT integration config
└── docs/                          # Documentation
```

## 🛡️ Security & Compliance

- **PHI Redaction**: Automatic redaction of names, dates, and sensitive information
- **Audit Logging**: All queries logged with user ID and timestamp
- **Pre-vetted Queries**: Only approved, safe SQL queries are executed
- **No Direct SQL Access**: Users cannot execute arbitrary SQL
- **API Key Authentication**: Optional API key protection for production

## 🚢 Deployment

### Deploy to Render.com (Free Tier)

1. Push code to GitHub
2. Sign up at [render.com](https://render.com)
3. Create new Web Service
4. Connect your GitHub repository
5. Set environment variables (OPENAI_API_KEY, etc.)
6. Deploy!

### Deploy to Railway

```bash
npm install -g @railway/cli
railway login
cd v1
railway init
railway up
```

### Deploy to AWS Lambda

See AWS Lambda deployment guide in `docs/deployment.md`

## 📊 Monitoring & Observability

- **LangFuse Integration**: Optional prompt management and tracing
- **Built-in Metrics**: Query time, agent usage, confidence scores
- **Health Checks**: `/health` endpoint for monitoring
- **Structured Logging**: JSON logs for easy parsing

## 🤝 Contributing

This is a private repository for internal use. For questions or issues, contact the development team.

## 📄 License

Proprietary - All rights reserved

## 🆘 Support

For issues or questions:
- Check the documentation in `v1/docs/`
- Review the agent configuration in `v1/ai-agent-service-staging/agent_core/agents_seed.yaml`
- Contact the development team

---

**Built with ❤️ for better healthcare data analysis**

