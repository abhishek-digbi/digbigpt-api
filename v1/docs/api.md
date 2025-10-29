# DigbiGPT API Reference

## Base URL
```
http://localhost:9000/api
```

## Authentication
All API endpoints require proper authentication. Include your API key in the request headers:
```
Authorization: Bearer your-api-key
```

## Endpoints

### Health Check
```http
GET /api/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0.0"
}
```

### Ask DigbiGPT
```http
POST /api/digbigpt/ask
```

**Request Body:**
```json
{
  "question": "Which customers spent the most on rosuvastatin in 2024?",
  "user_id": "dr_smith_123",
  "context": {
    "conversation_summary": "Previous discussion about medication costs",
    "user_preferences": "Focus on cost optimization"
  }
}
```

**Response:**
```json
{
  "answer": "Based on the claims data for rosuvastatin in 2024, here are the key findings...",
  "table": {
    "columns": ["member_name", "total_spend", "fill_count", "avg_spend_per_fill"],
    "rows": [
      ["John Doe", 1500.00, 12, 125.00],
      ["Jane Smith", 1200.00, 10, 120.00]
    ]
  },
  "agent_used": "DRUG_SPEND_AGENT",
  "confidence": 0.9,
  "query_time_ms": 1250,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### List Agents
```http
GET /api/digbigpt/agents
```

**Response:**
```json
{
  "agents": [
    {
      "id": "DRUG_SPEND_AGENT",
      "name": "Drug Spend Agent",
      "description": "Answers questions about medication costs and utilization",
      "tools": ["get_top_drug_spend", "get_duplicate_medications"]
    },
    {
      "id": "CLINICAL_HISTORY_AGENT",
      "name": "Clinical History Agent",
      "description": "Answers questions about member diagnoses and clinical timelines",
      "tools": ["get_member_disease_history", "get_gi_new_starts"]
    },
    {
      "id": "COHORT_INSIGHTS_AGENT",
      "name": "Cohort Insights Agent",
      "description": "Answers questions about disease cohort metrics and population health",
      "tools": ["get_disease_cohort_summary", "get_top_drug_spend"]
    }
  ]
}
```

### List Tools
```http
GET /api/digbigpt/tools
```

**Response:**
```json
{
  "tools": [
    {
      "name": "get_top_drug_spend",
      "description": "Returns members with highest spend on a specific drug",
      "parameters": ["drug_name", "year", "limit"]
    },
    {
      "name": "get_member_disease_history",
      "description": "Returns diagnosis history for a specific member",
      "parameters": ["member_id_hash"]
    },
    {
      "name": "get_gi_new_starts",
      "description": "Returns members who started GI medications in date range",
      "parameters": ["start_date", "end_date", "limit"]
    },
    {
      "name": "get_duplicate_medications",
      "description": "Identifies members on multiple similar medications",
      "parameters": ["drug_pattern", "days_lookback", "limit"]
    },
    {
      "name": "get_disease_cohort_summary",
      "description": "Returns summary statistics for members in a disease cohort",
      "parameters": ["disease_category", "year"]
    }
  ]
}
```

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Question cannot be empty"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Failed to process query: Database connection error"
}
```

## Rate Limiting
- 100 requests per minute per user
- 1000 requests per hour per API key

## Data Privacy
- All PHI (names, DOBs, SSNs) is automatically redacted
- Member IDs are hashed and redacted
- All queries are logged for audit compliance
- No data is permanently stored

## Example Queries

### Drug Spend Analysis
```bash
curl -X POST "http://localhost:9000/api/digbigpt/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Which customers spent the most on metformin in 2023?",
    "user_id": "pharmacist_001"
  }'
```

### Disease Cohort Analysis
```bash
curl -X POST "http://localhost:9000/api/digbigpt/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show me the diabetes cohort summary for 2024",
    "user_id": "analyst_002"
  }'
```

### Clinical History
```bash
curl -X POST "http://localhost:9000/api/digbigpt/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How many members started GI medications in Q1 2024?",
    "user_id": "clinician_003"
  }'
```


