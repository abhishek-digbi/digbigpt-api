"""Minimal Claims Server Test."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
import duckdb
import os

app = FastAPI()

# Test connection at startup
print("Testing DuckDB connection...")
try:
    db_path = "/Users/abhisheksutaria/Cursor Projects/DigbiGPT/v1/data/claims.db"
    print(f"Connecting to: {db_path}")
    print(f"File exists: {os.path.exists(db_path)}")
    
    conn = duckdb.connect(db_path, read_only=True)
    result = conn.execute("SELECT COUNT(*) FROM members").fetchone()
    print(f"✅ Connection successful: {result[0]:,} members")
    
    # Store connection globally
    app.state.db_conn = conn
    
except Exception as e:
    print(f"❌ Connection failed: {e}")
    app.state.db_conn = None

class ToolCallRequest(BaseModel):
    name: str
    arguments: Dict[str, Any]

class ToolCallResponse(BaseModel):
    is_error: bool
    content: List[Dict[str, Any]]

@app.get("/health")
async def health():
    if app.state.db_conn is None:
        return {"status": "unhealthy", "error": "No database connection"}
    
    try:
        result = app.state.db_conn.execute("SELECT COUNT(*) FROM members").fetchone()
        return {
            "status": "healthy",
            "members": result[0],
            "message": "Database connection working"
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.post("/tools/call", response_model=ToolCallResponse)
async def call_tool(request: ToolCallRequest):
    """Call a database tool with arguments."""
    if app.state.db_conn is None:
        return ToolCallResponse(
            is_error=True,
            content=[{"error": "DuckDB connection not available"}]
        )
    
    try:
        print(f"Tool call: {request.name} with args: {request.arguments}")
        
        if request.name == "get_top_drug_spend":
            result = await get_top_drug_spend(**request.arguments)
        elif request.name == "get_gi_new_starts":
            result = await get_gi_new_starts(**request.arguments)
        elif request.name == "get_disease_cohort_summary":
            result = await get_disease_cohort_summary(**request.arguments)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown tool: {request.name}")
        
        return ToolCallResponse(is_error=False, content=[result])
        
    except Exception as e:
        print(f"Tool call failed: {e}")
        return ToolCallResponse(
            is_error=True,
            content=[{"error": str(e)}]
        )

async def get_top_drug_spend(drug_name: str, year: int = 2023, limit: int = 10) -> Dict[str, Any]:
    """Get top spenders on a specific drug."""
    query = """
        SELECT 
            m.member_first_name,
            m.member_last_name,
            COUNT(*) as fill_count,
            SUM(ce.client_amount_due) as total_spend,
            AVG(ce.client_amount_due) as avg_spend_per_fill,
            MIN(ce.date_of_service) as first_fill,
            MAX(ce.date_of_service) as last_fill
        FROM members m
        JOIN claims_entries ce ON m.member_id_hash = ce.member_id_hash
        JOIN claims_drugs cd ON ce.claim_entry_id = cd.claim_entry_id
        WHERE UPPER(cd.product_service_name) LIKE UPPER(?)
        AND YEAR(ce.date_of_service) = ?
        GROUP BY m.member_first_name, m.member_last_name
        ORDER BY total_spend DESC
        LIMIT ?
    """
    
    result = app.state.db_conn.execute(query, [f"%{drug_name}%", year, limit]).fetchall()
    
    return {
        "columns": ["member_first_name", "member_last_name", "fill_count", "total_spend", "avg_spend_per_fill", "first_fill", "last_fill"],
        "rows": [list(row) for row in result]
    }

async def get_gi_new_starts(start_date: str, end_date: str, limit: int = 50) -> Dict[str, Any]:
    """Get members who started GI medications in date range."""
    query = """
        SELECT DISTINCT
            m.member_first_name,
            m.member_last_name,
            cd.product_service_name,
            ce.date_of_service
        FROM members m
        JOIN claims_entries ce ON m.member_id_hash = ce.member_id_hash
        JOIN claims_drugs cd ON ce.claim_entry_id = cd.claim_entry_id
        WHERE UPPER(cd.product_service_name) IN (
            'OMEPRAZOLE', 'FAMOTIDINE', 'RANITIDINE', 'PANTOPRAZOLE', 
            'ESOMEPRAZOLE', 'LANSOPRAZOLE', 'SUCRALFATE', 'MISOPROSTOL'
        )
        AND ce.date_of_service BETWEEN ? AND ?
        ORDER BY ce.date_of_service DESC
        LIMIT ?
    """
    
    result = app.state.db_conn.execute(query, [start_date, end_date, limit]).fetchall()
    
    return {
        "columns": ["member_first_name", "member_last_name", "product_service_name", "date_of_service"],
        "rows": [list(row) for row in result]
    }

async def get_disease_cohort_summary(disease_category: str, year: int = 2023) -> Dict[str, Any]:
    """Get summary statistics for a disease cohort."""
    query = """
        SELECT 
            COUNT(DISTINCT m.member_id_hash) as member_count,
            COUNT(ce.claim_entry_id) as total_claims,
            SUM(ce.client_amount_due) as total_spend,
            AVG(ce.client_amount_due) as avg_claim_cost,
            COUNT(DISTINCT cd.product_service_name) as unique_drugs
        FROM members m
        JOIN claims_entries ce ON m.member_id_hash = ce.member_id_hash
        JOIN claims_drugs cd ON ce.claim_entry_id = cd.claim_entry_id
        WHERE UPPER(ce.diagnosis_description) LIKE UPPER(?)
        AND YEAR(ce.date_of_service) = ?
    """
    
    result = app.state.db_conn.execute(query, [f"%{disease_category}%", year]).fetchone()
    
    return {
        "columns": ["member_count", "total_claims", "total_spend", "avg_claim_cost", "unique_drugs"],
        "rows": [list(result)] if result else [[]]
    }

@app.get("/test")
async def test_query():
    if app.state.db_conn is None:
        return {"error": "No database connection"}
    
    try:
        result = app.state.db_conn.execute("""
            SELECT 
                m.member_first_name,
                m.member_last_name,
                COUNT(*) as fill_count,
                SUM(ce.client_amount_due) as total_spend
            FROM members m
            JOIN claims_entries ce ON m.member_id_hash = ce.member_id_hash
            JOIN claims_drugs cd ON ce.claim_entry_id = cd.claim_entry_id
            WHERE UPPER(cd.product_service_name) LIKE '%OMEPRAZOLE%'
            AND YEAR(ce.date_of_service) = 2023
            GROUP BY m.member_first_name, m.member_last_name
            ORDER BY total_spend DESC
            LIMIT 3
        """).fetchall()
        
        return {
            "query": "Top 3 Omeprazole Spenders 2023",
            "results": [
                {
                    "name": f"{row[0]} {row[1]}",
                    "fills": row[2],
                    "total_spend": row[3]
                }
                for row in result
            ]
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8811)
