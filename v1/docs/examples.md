# DigbiGPT Usage Examples

## Overview
This document provides practical examples of how to use DigbiGPT for healthcare claims analysis.

## Basic Usage

### Starting the Service
```bash
# Start DigbiGPT
python src/app.py

# Service will be available at http://localhost:9000
# API documentation at http://localhost:9000/docs
```

### Making Your First Query
```bash
curl -X POST "http://localhost:9000/api/digbigpt/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Which customers spent the most on omeprazole in 2023?",
    "user_id": "dr_smith_123"
  }'
```

## Example Queries by Category

### Drug Spend Analysis

#### Top Medication Spenders
```bash
# Find top spenders on a specific drug
curl -X POST "http://localhost:9000/api/digbigpt/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Which customers spent the most on rosuvastatin in 2024?",
    "user_id": "pharmacist_001"
  }'
```

**Expected Response:**
```json
{
  "answer": "Based on the claims data for rosuvastatin in 2024, here are the key findings:\n\n**Top Spenders:**\n- **JOHN DOE**: $2,500 total spend (20 fills, $125 per fill)\n- **JANE SMITH**: $2,200 total spend (18 fills, $122 per fill)\n\n**Key Insights:**\n1. **JOHN DOE** had the highest total spend on rosuvastatin in 2024...",
  "table": {
    "columns": ["member_name", "total_spend", "fill_count", "avg_spend_per_fill"],
    "rows": [
      ["JOHN DOE", 2500.00, 20, 125.00],
      ["JANE SMITH", 2200.00, 18, 122.22]
    ]
  },
  "agent_used": "DRUG_SPEND_AGENT",
  "confidence": 0.9
}
```

#### Cost Analysis by Year
```bash
# Compare spending across years
curl -X POST "http://localhost:9000/api/digbigpt/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show me the top 10 spenders on metformin in 2023",
    "user_id": "analyst_002"
  }'
```

#### Duplicate Medication Detection
```bash
# Find potential safety issues
curl -X POST "http://localhost:9000/api/digbigpt/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Find members on multiple statin medications",
    "user_id": "clinician_003"
  }'
```

### Disease Cohort Analysis

#### Hypertension Cohort Summary
```bash
# Get population health metrics
curl -X POST "http://localhost:9000/api/digbigpt/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show me the hypertension cohort summary for 2023",
    "user_id": "population_health_001"
  }'
```

**Expected Response:**
```json
{
  "answer": "## Hypertension Cohort Analysis - 2023\n\n**Population Health Metrics:**\n- **Total Members**: 1,809 individuals with hypertension\n- **Total Claims**: 72,579 claims processed\n- **Total Spend**: $24.2M in healthcare costs\n- **Average Claim**: $333.41 per claim\n- **Unique Medications**: 773 different drugs used\n\n**Key Insights:**\n1. The hypertension cohort represents a significant portion of healthcare spend...",
  "table": {
    "columns": ["disease_category", "year", "member_count", "total_claims", "total_spend", "avg_claim_cost", "unique_drugs"],
    "rows": [
      ["hypertention", 2023, 1809, 72579, 24198245.01, 333.41, 773]
    ]
  },
  "agent_used": "COHORT_INSIGHTS_AGENT",
  "confidence": 0.9
}
```

#### Diabetes Cohort Analysis
```bash
# Analyze diabetes population
curl -X POST "http://localhost:9000/api/digbigpt/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the diabetes population health metrics for 2024?",
    "user_id": "diabetes_specialist_001"
  }'
```

### Clinical History Analysis

#### GI Medication New Starts
```bash
# Track new medication starts
curl -X POST "http://localhost:9000/api/digbigpt/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How many members started GI medications in Q1 2024?",
    "user_id": "gi_specialist_001"
  }'
```

**Expected Response:**
```json
{
  "answer": "## GI Medication New Starts - Q1 2024\n\n**New Medication Starts:**\n- **TRAVIS STOFFER**: Started OMEPRAZOLE on March 28, 2024\n- **FREDERICK MORING**: Started OMEPRAZOLE on March 28, 2024\n\n**Key Insights:**\n1. **OMEPRAZOLE** is the most common GI medication started...",
  "table": {
    "columns": ["member_first_name", "member_last_name", "drug_name", "start_date"],
    "rows": [
      ["TRAVIS", "STOFFER", "OMEPRAZOLE", "2024-03-28"],
      ["FREDERICK", "MORING", "OMEPRAZOLE", "2024-03-28"]
    ]
  },
  "agent_used": "CLINICAL_HISTORY_AGENT",
  "confidence": 0.9
}
```

#### Member Disease History
```bash
# Get specific member's diagnosis history
curl -X POST "http://localhost:9000/api/digbigpt/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show me the disease history for member with ID hash f42b93cc52b47fe753bf84a1464c36d3",
    "user_id": "case_manager_001"
  }'
```

## Advanced Usage Patterns

### Context-Aware Queries
```bash
# Include conversation context
curl -X POST "http://localhost:9000/api/digbigpt/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What about the cost trends for the same drug?",
    "user_id": "analyst_002",
    "context": {
      "conversation_summary": "Previously discussed rosuvastatin spending patterns",
      "user_preferences": "Focus on cost optimization opportunities"
    }
  }'
```

### Batch Analysis
```bash
# Analyze multiple drugs
curl -X POST "http://localhost:9000/api/digbigpt/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Compare spending on statin medications: rosuvastatin, atorvastatin, and simvastatin in 2024",
    "user_id": "pharmacy_manager_001"
  }'
```

### Time-Based Analysis
```bash
# Seasonal analysis
curl -X POST "http://localhost:9000/api/digbigpt/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show me GI medication starts by month for 2024",
    "user_id": "seasonal_analyst_001"
  }'
```

## Python Integration Examples

### Basic Python Client
```python
import httpx
import asyncio

async def ask_digbigpt(question: str, user_id: str) -> dict:
    """Ask DigbiGPT a question."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:9000/api/digbigpt/ask",
            json={
                "question": question,
                "user_id": user_id
            }
        )
        return response.json()

# Usage
async def main():
    result = await ask_digbigpt(
        "Which customers spent the most on omeprazole in 2023?",
        "python_client_001"
    )
    print(f"Answer: {result['answer']}")
    print(f"Agent: {result['agent_used']}")
    print(f"Confidence: {result['confidence']}")

# Run
asyncio.run(main())
```

### Batch Processing
```python
import httpx
import asyncio
from typing import List, Dict

async def batch_analyze_drugs(drugs: List[str], year: int, user_id: str) -> List[Dict]:
    """Analyze multiple drugs in parallel."""
    async with httpx.AsyncClient() as client:
        tasks = []
        for drug in drugs:
            question = f"Which customers spent the most on {drug} in {year}?"
            task = client.post(
                "http://localhost:9000/api/digbigpt/ask",
                json={"question": question, "user_id": user_id}
            )
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        return [response.json() for response in responses]

# Usage
async def main():
    drugs = ["rosuvastatin", "atorvastatin", "simvastatin"]
    results = await batch_analyze_drugs(drugs, 2024, "batch_analyst_001")
    
    for i, result in enumerate(results):
        print(f"\n{drugs[i]} Analysis:")
        print(f"Agent: {result['agent_used']}")
        print(f"Confidence: {result['confidence']}")

asyncio.run(main())
```

## Error Handling Examples

### Handling API Errors
```python
import httpx
import asyncio

async def safe_ask_digbigpt(question: str, user_id: str) -> dict:
    """Ask DigbiGPT with error handling."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:9000/api/digbigpt/ask",
                json={"question": question, "user_id": user_id},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        print(f"HTTP error: {e.response.status_code}")
        return {"error": f"HTTP {e.response.status_code}"}
    except httpx.TimeoutException:
        print("Request timed out")
        return {"error": "Timeout"}
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {"error": str(e)}

# Usage
async def main():
    result = await safe_ask_digbigpt(
        "Which customers spent the most on omeprazole in 2023?",
        "error_handling_test"
    )
    
    if "error" in result:
        print(f"Error occurred: {result['error']}")
    else:
        print(f"Success: {result['answer'][:100]}...")

asyncio.run(main())
```

## Testing Examples

### Unit Testing
```python
import pytest
import httpx
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_digbigpt_query():
    """Test DigbiGPT query functionality."""
    # Mock the API response
    mock_response = AsyncMock()
    mock_response.json.return_value = {
        "answer": "Test answer",
        "agent_used": "DRUG_SPEND_AGENT",
        "confidence": 0.9
    }
    mock_response.status_code = 200
    
    with patch('httpx.AsyncClient.post', return_value=mock_response):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:9000/api/digbigpt/ask",
                json={"question": "test question", "user_id": "test_user"}
            )
            result = response.json()
            
            assert result["answer"] == "Test answer"
            assert result["agent_used"] == "DRUG_SPEND_AGENT"
            assert result["confidence"] == 0.9
```

## Best Practices

### Query Optimization
1. **Be Specific**: "Which customers spent the most on rosuvastatin in 2024?" vs "Show me drug spending"
2. **Include Timeframes**: Always specify years or date ranges
3. **Use Drug Names**: Use generic drug names (rosuvastatin) rather than brand names (Crestor)

### Error Handling
1. **Check Response Status**: Always verify HTTP status codes
2. **Handle Timeouts**: Set appropriate timeout values
3. **Log Errors**: Log failed requests for debugging

### Performance
1. **Use Async**: Use async/await for better performance
2. **Batch Requests**: Group related queries together
3. **Cache Results**: Cache frequently accessed data

### Security
1. **Validate Input**: Sanitize user inputs
2. **Use HTTPS**: Always use HTTPS in production
3. **Rate Limiting**: Implement rate limiting for API calls

## Troubleshooting

### Common Issues

**Empty Responses:**
- Check if the database contains data for the specified time period
- Verify drug names are spelled correctly
- Ensure the question is specific enough

**Low Confidence Scores:**
- Try rephrasing the question
- Be more specific about timeframes
- Check if the agent has the right tools

**Timeout Errors:**
- Increase timeout values
- Check network connectivity
- Verify service is running

### Debug Mode
Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

This will show detailed information about the query processing pipeline.


