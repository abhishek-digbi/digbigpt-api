# duckdb_server.py
# FastAPI server for DigbiGPT Claims Database (MCP-compatible endpoints).

import os
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime

import duckdb
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from tabulate import tabulate

# DuckDB connection configuration
DB_PATH = os.environ.get("CLAIMS_DB_PATH", str(Path(__file__).parent.parent / "claims.db"))

if not os.path.exists(DB_PATH):
    raise SystemExit(f"DuckDB file not found: {DB_PATH}")

# Create FastAPI app
app = FastAPI(
    title="DigbiGPT Claims Server",
    description="MCP-compatible API server for claims database queries",
    version="1.0.0"
)

def get_db_connection():
    """Create and return a database connection."""
    return duckdb.connect(DB_PATH, read_only=True)

def _execute_sql(sql: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Execute a SQL query and return formatted results.
    
    Returns:
        Dict with keys: columns, rows, table (formatted)
    """
    print(f"[Executing SQL]\n{sql}\nParams: {params}\n", flush=True)
    
    conn = get_db_connection()
    try:
        # DuckDB uses $param_name for parameterized queries
        # Convert %(param)s style to $param style
        if params:
            for key, value in params.items():
                sql = sql.replace(f"%({key})s", f"${key}")
        
        # Execute query
        result = conn.execute(sql, params or {})
        
        # Fetch results
        rows = result.fetchall()
        if not rows:
            return {"columns": [], "rows": [], "table": "(no rows)"}
        
        # Extract column names
        columns = [desc[0] for desc in result.description]
        
        # Convert rows to list of lists
        data_rows = [list(row) for row in rows]
        
        # Format as table
        table_str = tabulate(data_rows, headers=columns, tablefmt="github")
        print(f"[SQL Pretty]\n{table_str}\n", flush=True)
        
        return {
            "columns": columns,
            "rows": data_rows,
            "table": table_str
        }
    except Exception as e:
        print(f"[SQL Error]\n{e}\n", flush=True)
        raise RuntimeError(f"SQL execution failed: {e}")
    finally:
        conn.close()

# Pydantic models for request/response
class ToolRequest(BaseModel):
    """Request model for tool calls."""
    name: str
    arguments: Dict[str, Any]

class ToolResponse(BaseModel):
    """Response model for tool calls."""
    content: List[Dict[str, Any]]
    is_error: bool = False

# ---------------------
# FastAPI Endpoints - MCP-compatible API
# ---------------------

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "DigbiGPT Claims Server", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        conn = get_db_connection()
        result = conn.execute("SELECT 1").fetchone()
        conn.close()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.get("/tools")
async def list_tools():
    """List available tools."""
    return {
        "tools": [
            {"name": "get_schema", "description": "Return database schema information"},
            {"name": "get_top_drug_spend", "description": "Returns members with highest spend on a specific drug"},
            {"name": "get_member_disease_history", "description": "Returns diagnosis history for a specific member"},
            {"name": "get_gi_new_starts", "description": "Returns members who started GI medications in date range"},
            {"name": "get_duplicate_medications", "description": "Identifies members on multiple similar medications"},
            {"name": "get_disease_cohort_summary", "description": "Returns summary statistics for members in a disease cohort"}
        ]
    }

@app.post("/tools/call", response_model=ToolResponse)
async def call_tool(request: ToolRequest):
    """Call a tool by name with arguments."""
    try:
        if request.name == "get_schema":
            result = get_schema()
        elif request.name == "get_top_drug_spend":
            result = get_top_drug_spend(
                request.arguments["drug_name"],
                request.arguments["year"],
                request.arguments.get("limit", 10)
            )
        elif request.name == "get_member_disease_history":
            result = get_member_disease_history(request.arguments["member_id_hash"])
        elif request.name == "get_gi_new_starts":
            result = get_gi_new_starts(
                request.arguments["start_date"],
                request.arguments["end_date"],
                request.arguments.get("limit", 50)
            )
        elif request.name == "get_duplicate_medications":
            result = get_duplicate_medications(
                request.arguments["drug_pattern"],
                request.arguments.get("days_lookback", 90),
                request.arguments.get("limit", 20)
            )
        elif request.name == "get_disease_cohort_summary":
            result = get_disease_cohort_summary(
                request.arguments["disease_category"],
                request.arguments["year"]
            )
        else:
            raise HTTPException(status_code=404, detail=f"Tool '{request.name}' not found")
        
        return ToolResponse(content=[result])
    except Exception as e:
        return ToolResponse(content=[{"error": str(e)}], is_error=True)

# ---------------------
# Tool Functions - Pre-vetted SQL queries
# ---------------------

def get_schema() -> Dict[str, Any]:
    """Return database schema information for claims tables."""
    sql = """
    SELECT 
        table_name,
        column_name,
        data_type
    FROM information_schema.columns
    WHERE table_schema = 'main'
      AND table_name IN ('members', 'claims_entries', 'claims_drugs', 'claims_diagnoses', 
                         'icd10_codes', 'drug_ndc_info')
    ORDER BY table_name, ordinal_position
    """
    return _execute_sql(sql)

def get_top_drug_spend(
    drug_name: str,
    year: int,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Returns members with highest spend on a specific drug.
    
    Args:
        drug_name: Name of the drug (e.g., "SERTRALINE", "OMEPRAZOLE")
        year: Year of claims (e.g., 2023, 2024)
        limit: Maximum number of results (default: 10)
    """
    sql = """
        SELECT 
            m.member_first_name,
            m.member_last_name,
            COUNT(*) as fill_count,
            SUM(ce.client_amount_due) as total_spend,
            ROUND(AVG(ce.client_amount_due), 2) as avg_spend_per_fill,
            MIN(ce.date_of_service) as first_fill_date,
            MAX(ce.date_of_service) as last_fill_date
        FROM claims_entries ce
        JOIN claims_drugs cd ON ce.claim_entry_id = cd.claim_entry_id
        JOIN members m ON ce.member_id_hash = m.member_id_hash
        WHERE UPPER(cd.product_service_name) LIKE '%' || UPPER(%(drug_name)s) || '%'
          AND EXTRACT(YEAR FROM ce.date_of_service) = %(year)s
        GROUP BY m.member_id_hash, m.member_first_name, m.member_last_name
        ORDER BY total_spend DESC
        LIMIT %(limit)s
    """
    return _execute_sql(sql, {
        "drug_name": drug_name,
        "year": year,
        "limit": limit
    })

def get_member_disease_history(member_id_hash: str) -> Dict[str, Any]:
    """
    Returns diagnosis history for a specific member.
    
    Args:
        member_id_hash: Hashed member identifier
    """
    sql = """
        SELECT 
            cd.icd_code,
            ic.description as diagnosis_description,
            MIN(ce.date_of_service) as first_seen,
            MAX(ce.date_of_service) as last_seen,
            COUNT(*) as claim_count,
            CASE WHEN cd.is_primary THEN 'Yes' ELSE 'No' END as primary_diagnosis
        FROM claims_entries ce
        JOIN claims_diagnoses cd ON ce.claim_entry_id = cd.claim_entry_id
        LEFT JOIN icd10_codes ic ON cd.icd_code = ic.code
        WHERE ce.member_id_hash = %(member_id_hash)s
        GROUP BY cd.icd_code, ic.description, cd.is_primary
        ORDER BY first_seen DESC
    """
    return _execute_sql(sql, {"member_id_hash": member_id_hash})

def get_gi_new_starts(start_date: str, end_date: str, limit: int = 50) -> Dict[str, Any]:
    """
    Returns members who started GI medications in date range.
    
    Args:
        start_date: Start date in YYYY-MM-DD format (e.g., "2023-01-01")
        end_date: End date in YYYY-MM-DD format (e.g., "2023-12-31")
        limit: Maximum number of results (default: 50)
    """
    sql = """
        WITH gi_drugs AS (
            SELECT DISTINCT product_service_name
            FROM claims_drugs
            WHERE UPPER(product_service_name) IN (
                'OMEPRAZOLE', 'PANTOPRAZOLE', 'ESOMEPRAZOLE', 
                'LANSOPRAZOLE', 'RABEPRAZOLE', 'FAMOTIDINE'
            )
        ),
        first_fills AS (
            SELECT 
                ce.member_id_hash,
                cd.product_service_name,
                MIN(ce.date_of_service) as first_fill_date
            FROM claims_entries ce
            JOIN claims_drugs cd ON ce.claim_entry_id = cd.claim_entry_id
            WHERE cd.product_service_name IN (SELECT product_service_name FROM gi_drugs)
            GROUP BY ce.member_id_hash, cd.product_service_name
        )
        SELECT 
            m.member_first_name,
            m.member_last_name,
            ff.product_service_name as drug_name,
            ff.first_fill_date
        FROM first_fills ff
        JOIN members m ON ff.member_id_hash = m.member_id_hash
        WHERE ff.first_fill_date BETWEEN %(start_date)s AND %(end_date)s
        ORDER BY ff.first_fill_date DESC
        LIMIT %(limit)s
    """
    return _execute_sql(sql, {
        "start_date": start_date,
        "end_date": end_date,
        "limit": limit
    })

def get_duplicate_medications(
    drug_pattern: str,
    days_lookback: int = 90,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Identifies members on multiple similar medications in recent period.
    
    Args:
        drug_pattern: Drug name pattern to search (e.g., "STATIN", "ZEPAM" for benzos)
        days_lookback: Number of days to look back (default: 90)
        limit: Maximum number of results (default: 20)
    """
    sql = """
        WITH recent_drugs AS (
            SELECT 
                ce.member_id_hash,
                cd.product_service_name,
                ce.date_of_service
            FROM claims_entries ce
            JOIN claims_drugs cd ON ce.claim_entry_id = cd.claim_entry_id
            WHERE UPPER(cd.product_service_name) LIKE '%' || UPPER(%(drug_pattern)s) || '%'
              AND ce.date_of_service >= CURRENT_DATE - INTERVAL %(days_lookback)s DAYS
        ),
        member_drugs AS (
            SELECT 
                rd.member_id_hash,
                COUNT(DISTINCT rd.product_service_name) as drug_count,
                STRING_AGG(DISTINCT rd.product_service_name, ', ') as drugs,
                MIN(rd.date_of_service) as first_date,
                MAX(rd.date_of_service) as last_date
            FROM recent_drugs rd
            GROUP BY rd.member_id_hash
            HAVING COUNT(DISTINCT rd.product_service_name) > 1
        )
        SELECT 
            m.member_first_name,
            m.member_last_name,
            md.drug_count,
            md.drugs,
            md.first_date,
            md.last_date
        FROM member_drugs md
        JOIN members m ON md.member_id_hash = m.member_id_hash
        ORDER BY md.drug_count DESC, md.last_date DESC
        LIMIT %(limit)s
    """
    return _execute_sql(sql, {
        "drug_pattern": drug_pattern,
        "days_lookback": days_lookback,
        "limit": limit
    })

def get_disease_cohort_summary(disease_category: str, year: int) -> Dict[str, Any]:
    """
    Returns summary statistics for members in a disease cohort.
    
    Args:
        disease_category: Disease category (e.g., "hypertention", "diabetes")
        year: Year for the summary (e.g., 2023, 2024)
    """
    sql = """
        WITH cohort_members AS (
            SELECT DISTINCT member_id_hash
            FROM claims_members_cohorts
            WHERE disease_category = %(disease_category)s
              AND year_of_service = %(year)s
        )
        SELECT 
            %(disease_category)s as disease_category,
            %(year)s as year,
            COUNT(DISTINCT cm.member_id_hash) as total_members,
            COUNT(DISTINCT ce.claim_entry_id) as total_claims,
            SUM(ce.client_amount_due) as total_spend,
            ROUND(AVG(ce.client_amount_due), 2) as avg_claim_amount,
            COUNT(DISTINCT cd.product_service_name) as unique_drugs_used
        FROM cohort_members cm
        LEFT JOIN claims_entries ce ON cm.member_id_hash = ce.member_id_hash
            AND EXTRACT(YEAR FROM ce.date_of_service) = %(year)s
        LEFT JOIN claims_drugs cd ON ce.claim_entry_id = cd.claim_entry_id
    """
    return _execute_sql(sql, {
        "disease_category": disease_category,
        "year": year
    })

if __name__ == "__main__":
    import uvicorn
    print("[CLAIMS SERVER] Starting DigbiGPT Claims Server on http://127.0.0.1:8811")
    print(f"[CLAIMS SERVER] Database: {DB_PATH}")
    uvicorn.run(app, host="127.0.0.1", port=8811)
