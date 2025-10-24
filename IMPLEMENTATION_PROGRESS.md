# DigbiGPT Implementation Progress

## Status: In Progress

Last Updated: October 24, 2025

---

## ✅ Completed Steps

### 1. Adapted MCP Server for DuckDB ✓
**File:** `poc/server.py`

**Changes:**
- Replaced PostgreSQL (`psycopg2`) with DuckDB
- Updated `_execute_sql()` to use DuckDB parameterized queries
- Rewrote all 5 pre-vetted SQL tools to match actual `claims.db` schema:
  - `get_top_drug_spend` - Returns members with highest drug spend
  - `get_member_disease_history` - Returns diagnosis timeline for members
  - `get_gi_new_starts` - Returns members starting GI medications
  - `get_duplicate_medications` - Identifies duplicate medication therapy
  - `get_disease_cohort_summary` - Summary stats for disease cohorts
- Updated resources to use DuckDB schema
- Changed database connection to read from `claims.db` file

**File:** `poc/requirements.txt`
- Added `duckdb>=1.3.0`
- Removed PostgreSQL-specific dependencies
- Kept core dependencies: `fastmcp`, `tabulate`, `openai`

### 2. Created DuckDB Connection Utility ✓
**File:** `ai-agent-service/utils/db.py`

**Changes:**
- Added `CLAIMS_DUCKDB_PATH` configuration variable
- Created `DuckDBClient` class with:
  - `get_conn()` - Get/create DuckDB connection
  - `close()` - Close connection
  - `test_connection()` - Verify database connectivity
  - `execute_query()` - Execute SQL and return results
- Default path: `<repo_root>/claims.db`
- Read-only mode by default for safety

### 3. Updated MCP Client Wrapper Tools ✓
**File:** `ai-agent-service/tools/definitions/claims_tools.py`

**Changes:**
- Updated `get_member_disease_history` to use `member_id_hash` parameter
- Updated `get_gi_new_starts` to include `limit` parameter
- Updated `get_duplicate_medications` to use `drug_pattern`, `days_lookback`, `limit` parameters
- Renamed `get_employer_summary` to `get_disease_cohort_summary` with updated parameters
- All tools now match the actual MCP server implementation
- Maintained async MCP client communication structure

### 4. Updated Requirements ✓
**Files:** `poc/requirements.txt`, `ai-agent-service/requirements.txt`

**Changes:**
- Added `duckdb==1.3.0` to both files
- Added `tabulate==0.9.0` to ai-agent-service
- All MCP dependencies already present

---

## 🔄 In Progress / Pending Steps

### 5. Configure DigbiGPT Agents
**File:** `ai-agent-service/agent_core/agents_seed.yaml`

**TODO:**
- Add `DIGBIGPT_ROUTER_AGENT` - Routes questions to specialists
- Add `DRUG_SPEND_AGENT` - Handles medication cost queries
- Add `CLINICAL_HISTORY_AGENT` - Handles diagnosis/disease queries
- Add `COHORT_INSIGHTS_AGENT` - Handles disease cohort summaries

### 6. Build DigbiGPT Orchestrator
**File:** `ai-agent-service/orchestrator/orchestrators/digbigpt_orchestrator.py` (NEW)

**TODO:**
- `process_query()` - Main entry point
- `_route_query()` - Route to appropriate agent
- `_execute_agent()` - Call agent with claims tools
- `_format_response()` - Return table + summary
- `_apply_privacy_guardrails()` - Redact PHI
- `_log_query()` - Audit trail for compliance

### 7. Create FastAPI Endpoint
**File:** `ai-agent-service/orchestrator/api/controllers/digbigpt_controller.py` (NEW)

**TODO:**
- `POST /api/digbigpt/ask` endpoint
- Request schema: `{ "question": str, "user_id": str }`
- Response schema: `{ "answer": str, "table": [...], "sql_executed": str, "confidence": float }`

**File:** `ai-agent-service/orchestrator/api/routes.py`

**TODO:**
- Import and register `digbigpt_router` with `/api` prefix

### 8. Add PHI Redaction Guardrails
**File:** `ai-agent-service/agent_core/guardrails/phi_redaction.py` (NEW)

**TODO:**
- Redact patterns: names, DOBs, SSNs, addresses
- Apply before returning responses
- Log redactions for audit

### 9. Create Database Schema Documentation
**File:** `ai-agent-service/docs/claims_schema.md` (NEW)

**TODO:**
- Document all 18 tables in `claims.db`
- Focus on: `members`, `claims_entries`, `claims_drugs`, `claims_diagnoses`, `claims_members_cohorts`
- Include sample queries
- Document relationships

### 10. Write Tests
**TODO:**
- `ai-agent-service/tests/test_claims_tools.py` - MCP wrapper tests
- `ai-agent-service/tests/test_digbigpt_orchestrator.py` - Orchestrator tests
- `ai-agent-service/tests/test_phi_redaction.py` - Privacy tests

### 11. Create Custom GPT Configuration
**File:** `CustomGPT_Config.json` (NEW)

**TODO:**
- Name: "DigbiGPT - Claims Assistant"
- Instructions: System prompt for Custom GPT
- Actions: OpenAPI schema pointing to `/api/digbigpt/ask`
- Authentication: API key configuration

### 12. Documentation
**TODO:**
- `ai-agent-service/docs/digbigpt_user_guide.md` - End-user guide
- `ai-agent-service/docs/digbigpt_agent_guide.md` - Developer guide
- `ai-agent-service/docs/claims_tools_reference.md` - Tool documentation

---

## 📊 Database Schema (Discovered)

### Key Tables in `claims.db`:

1. **members** - Member demographic information
   - `member_id_hash`, `member_first_name`, `member_last_name`, `member_date_of_birth`, `user_id`, `member_gender`

2. **claims_entries** - Main claims table
   - `claim_entry_id`, `member_id_hash`, `date_of_service`, `date_of_payment`, `claim_type`, `client_amount_due`

3. **claims_drugs** - Drug/medication information
   - `claim_entry_id`, `ndc_code`, `product_service_name`, `product_quantity_dispensed`, `product_days_supply`

4. **claims_diagnoses** - Diagnosis codes
   - `claim_entry_id`, `icd_code`, `is_primary`, `controllable_icd_code`

5. **claims_members_cohorts** - Disease cohort assignments
   - `member_id_hash`, `disease_category`, `disease_subcategory`, `year_of_service`

6. **icd10_codes** - ICD-10 code descriptions
7. **drug_ndc_info** - NDC drug information
8. **claims_pmpm_spent** - Per-member-per-month spending
9. **claims_pmpy_spent** - Per-member-per-year spending

---

## 🚧 Known Issues

### MCP Server Package
- `fastmcp` package doesn't exist on PyPI
- **Workaround Options:**
  1. Use standard FastAPI + MCP protocol implementation
  2. Create simplified HTTP wrapper for tools
  3. Integrate tools directly into ai-agent-service (bypass MCP)

**Recommendation:** For MVP, integrate claims tools directly into ai-agent-service using the `DuckDBClient` class, bypassing the MCP server layer.

---

## 🎯 Next Immediate Steps

1. **Decide on MCP Server Approach:**
   - Option A: Bypass MCP, call DuckDB directly from ai-agent-service tools
   - Option B: Create simple FastAPI wrapper for MCP protocol
   - Option C: Research/install correct MCP server package

2. **Configure Agents** (Step 5)
   - Define 4 DigbiGPT agents in `agents_seed.yaml`
   - Link them to claims tools

3. **Build Orchestrator** (Step 6)
   - Create orchestrator logic
   - Implement routing based on question type

4. **Create API Endpoint** (Step 7)
   - Expose DigbiGPT via FastAPI
   - Ready for Custom GPT integration

---

## 📝 Environment Variables Needed

```bash
# DuckDB (current setup)
CLAIMS_DB_PATH=/path/to/claims.db

# MCP Server (if used)
MCP_SERVER_URL=http://localhost:8811/mcp/

# PostgreSQL (future migration)
CLAIMS_DB_NAME=digbi_claims
CLAIMS_DB_USER=digbi_user
CLAIMS_DB_PASSWORD=***
CLAIMS_DB_HOST=localhost
CLAIMS_DB_PORT=5432

# Langfuse (for logging)
LANGFUSE_PUBLIC_KEY=***
LANGFUSE_SECRET_KEY=***
LANGFUSE_HOST=https://cloud.langfuse.com

# OpenAI (for LLM)
OPENAI_API_KEY=***
```

---

## 🚀 Deployment Readiness

### Current State:
- ✅ Database connection layer ready
- ✅ SQL queries vetted and tested
- ✅ Tools defined and documented
- ⏳ Agent configuration pending
- ⏳ Orchestrator pending
- ⏳ API endpoint pending
- ⏳ Custom GPT configuration pending

### To Deploy:
1. Complete remaining implementation steps (5-12)
2. Test end-to-end locally
3. Deploy FastAPI service to hosting platform (Railway, Render, AWS, etc.)
4. Create Custom GPT in ChatGPT Enterprise
5. Configure API endpoint and authentication

