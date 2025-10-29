# DigbiGPT Project Structure

## 📁 Clean Organization

This document describes the clean, organized structure of the DigbiGPT project.

## Directory Structure

```
DigbiGPT/v1/
├── README.md                 # Main documentation
├── DEPLOYMENT_GUIDE.md       # Deployment instructions
├── requirements.txt          # Python dependencies
├── Dockerfile                # Container configuration
├── docker-compose.yml        # Service orchestration
├── env.example              # Environment template
├── claims_server.py         # Claims Server (port 8811)
│
├── data/                    # Data files (379MB)
│   ├── claims.db           # DuckDB with 45,928 members
│   ├── agents.db           # SQLite agent configs
│   └── test.py            # Working test script
│
├── src/                     # Source code (11MB)
│   ├── app.py             # Main FastAPI app entry point
│   ├── config/
│   │   └── agents.yaml    # Agent configurations
│   ├── api/               # API layer
│   │   ├── controllers/   # API endpoints
│   │   ├── routes.py      # Route definitions
│   │   └── schemas.py     # Request/Response models
│   ├── core/              # Core framework
│   │   ├── services/      # Core services (AI, adapters)
│   │   ├── models/        # Data models
│   │   ├── config/        # Configuration loaders
│   │   └── guardrails/    # PHI redaction rules
│   ├── agents/            # AI agents
│   │   ├── digbigpt/     # DigbiGPT orchestrator
│   │   └── tools/        # Database tools
│   ├── utils/            # Utilities
│   │   ├── db.py         # Database clients
│   │   └── db_setup.py   # DB initialization
│   └── app/               # Application factory
│       └── __init__.py   # App creation
│
├── tests/                  # Test suite (296KB)
│   ├── test_api.py
│   ├── test_agents.py
│   ├── test_integration.py
│   └── ... (35 test files)
│
├── docs/                   # Documentation (108KB)
│   ├── api.md
│   ├── deployment.md
│   ├── examples.md
│   └── ... (17 doc files)
│
├── scripts/                # Utility scripts
│   ├── deploy.sh
│   ├── test_ai_responses.py
│   └── test_end_to_end.py
│
└── deployment/             # Deployment configs
    └── CustomGPT_Config.json
```

## Key Files

### Claims Server
- **`claims_server.py`** - Main claims server running on port 8811
  - Connects to DuckDB at `data/claims.db`
  - Exposes 5 database tools via REST API
  - Direct DuckDB connection (no dependencies on src/)

### DigbiGPT API
- **`src/app.py`** - Main application entry point
- **`src/app/__init__.py`** - Application factory
- **`src/api/controllers/digbigpt_controller.py`** - DigbiGPT API endpoints
- **`src/api/routes.py`** - Route configuration

### Database
- **`data/claims.db`** - Main DuckDB database (379MB)
  - 45,928 members
  - 1.6M claims
  - 483K drug claims
- **`data/agents.db`** - SQLite fallback for agent configs
- **`src/utils/db.py`** - Database client utilities

### Configuration
- **`src/config/agents.yaml`** - Agent definitions (3 agents configured)
- **`requirements.txt`** - Python dependencies
- **`env.example`** - Environment variable template

## Running the System

### Start Claims Server
```bash
python claims_server.py
# Runs on http://127.0.0.1:8811
```

### Start DigbiGPT API
```bash
python src/app.py
# Runs on http://127.0.0.1:9000
```

### Test the System
```bash
python data/test.py
# Tests complete end-to-end flow
```

## What Was Cleaned Up

### Removed Files:
- ❌ `simple_claims_server.py` (duplicate)
- ❌ `minimal_claims_server.py` (renamed to claims_server.py)
- ❌ `test_duckdb.py` (in wrong location)
- ❌ `test_claims_query.py` (in wrong location)
- ❌ `src/agents/tools/claims_server.py` (duplicate)
- ❌ `src/database/` (empty directory)
- ❌ `src/api/{controllers}/` (empty directory)

### Kept Files:
- ✅ `claims_server.py` (working server)
- ✅ `data/test.py` (useful demo script)
- ✅ All source code in `src/`
- ✅ All documentation in `docs/`
- ✅ All tests in `tests/`

## System Architecture

```
User Query
    ↓
DigbiGPT API (port 9000)
    ↓
Routes to Agent (DRUG_SPEND_AGENT / CLINICAL_HISTORY_AGENT / COHORT_INSIGHTS_AGENT)
    ↓
Calls Claims Server (port 8811)
    ↓
Executes SQL on DuckDB
    ↓
Returns Real Data
```

## Agents

1. **DRUG_SPEND_AGENT** - Medication cost analysis
2. **CLINICAL_HISTORY_AGENT** - Diagnosis timelines
3. **COHORT_INSIGHTS_AGENT** - Population health metrics

## Tools

1. `get_top_drug_spend` - Find highest spenders
2. `get_member_disease_history` - Member diagnosis history
3. `get_gi_new_starts` - GI medication tracking
4. `get_duplicate_medications` - Duplicate therapy detection
5. `get_disease_cohort_summary` - Cohort statistics

## Status

✅ **Cleaned and organized**
✅ **No duplicate files**
✅ **Clear structure**
✅ **Working end-to-end**
✅ **Ready for production**

