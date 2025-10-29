"""Claims database tools for DigbiGPT agents.

These tools provide pre-vetted SQL queries against the claims DuckDB database.
All queries are read-only and designed for healthcare analytics.
"""

from typing import Dict, Any, List
import duckdb
from pathlib import Path
import os

from tools.registry import tool

# Determine the correct path to claims database
# Use sample database by default (smaller, suitable for deployment)
# Set CLAIMS_DB_PATH environment variable to use full database
CLAIMS_DB_PATH = os.getenv(
    "CLAIMS_DB_PATH",
    str(Path(__file__).parent.parent.parent.parent / "data" / "claims_sample.db")
)


def get_claims_connection():
    """Get a read-only connection to the claims database."""
    if not Path(CLAIMS_DB_PATH).exists():
        raise FileNotFoundError(f"Claims database not found at: {CLAIMS_DB_PATH}")
    return duckdb.connect(CLAIMS_DB_PATH, read_only=True)


@tool(
    name="get_top_drug_spend",
    description=(
        "Returns members with highest spend on a specific drug. "
        "Useful for analyzing medication costs and utilization patterns. "
        "Parameters: drug_name (str), year (int, default 2023), limit (int, default 10)"
    )
)
async def get_top_drug_spend(
    drug_name: str,
    year: int = 2023,
    limit: int = 10
) -> Dict[str, Any]:
    """Get top spenders on a specific drug.
    
    Args:
        drug_name: Name of the drug/medication to analyze
        year: Year to filter claims (default: 2023)
        limit: Maximum number of results to return (default: 10)
        
    Returns:
        Dictionary with 'columns' and 'rows' containing member spend data
    """
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
    
    conn = get_claims_connection()
    try:
        result = conn.execute(query, [f"%{drug_name}%", year, limit]).fetchall()
        return {
            "columns": [
                "member_first_name", "member_last_name", "fill_count",
                "total_spend", "avg_spend_per_fill", "first_fill", "last_fill"
            ],
            "rows": [list(row) for row in result]
        }
    finally:
        conn.close()


@tool(
    name="get_gi_new_starts",
    description=(
        "Returns members who started GI medications in a date range. "
        "Useful for tracking medication initiation and clinical timelines. "
        "Parameters: start_date (str, YYYY-MM-DD), end_date (str, YYYY-MM-DD), limit (int, default 50)"
    )
)
async def get_gi_new_starts(
    start_date: str,
    end_date: str,
    limit: int = 50
) -> Dict[str, Any]:
    """Get members who started GI medications in date range.
    
    Args:
        start_date: Start date for filtering (YYYY-MM-DD format)
        end_date: End date for filtering (YYYY-MM-DD format)
        limit: Maximum number of results to return (default: 50)
        
    Returns:
        Dictionary with 'columns' and 'rows' containing GI medication starts
    """
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
    
    conn = get_claims_connection()
    try:
        result = conn.execute(query, [start_date, end_date, limit]).fetchall()
        return {
            "columns": [
                "member_first_name", "member_last_name",
                "product_service_name", "date_of_service"
            ],
            "rows": [list(row) for row in result]
        }
    finally:
        conn.close()


@tool(
    name="get_disease_cohort_summary",
    description=(
        "Returns summary statistics for members in a disease cohort. "
        "Useful for population health metrics and cohort analysis. "
        "Parameters: disease_category (str), year (int, default 2023)"
    )
)
async def get_disease_cohort_summary(
    disease_category: str,
    year: int = 2023
) -> Dict[str, Any]:
    """Get summary statistics for a disease cohort.
    
    Args:
        disease_category: Disease category to analyze (e.g., 'hypertension', 'diabetes')
        year: Year to filter claims (default: 2023)
        
    Returns:
        Dictionary with 'columns' and 'rows' containing cohort metrics
    """
    query = """
        SELECT 
            COUNT(DISTINCT m.member_id_hash) as member_count,
            COUNT(ce.claim_entry_id) as total_claims,
            SUM(ce.client_amount_due) as total_spend,
            AVG(ce.client_amount_due) as avg_claim_cost,
            COUNT(DISTINCT cd.product_service_name) as unique_drugs
        FROM members m
        JOIN claims_entries ce ON m.member_id_hash = ce.member_id_hash
        JOIN claims_diagnoses cdg ON ce.claim_entry_id = cdg.claim_entry_id
        LEFT JOIN claims_drugs cd ON ce.claim_entry_id = cd.claim_entry_id
        WHERE UPPER(cdg.icd_code) LIKE UPPER(?)
        AND YEAR(ce.date_of_service) = ?
    """
    
    conn = get_claims_connection()
    try:
        result = conn.execute(query, [f"%{disease_category}%", year]).fetchone()
        return {
            "columns": [
                "member_count", "total_claims", "total_spend",
                "avg_claim_cost", "unique_drugs"
            ],
            "rows": [list(result)] if result else [[0, 0, 0.0, 0.0, 0]]
        }
    finally:
        conn.close()


@tool(
    name="get_member_disease_history",
    description=(
        "Returns diagnosis history for a specific member. "
        "Useful for clinical timeline analysis. "
        "Parameters: member_id_hash (str)"
    )
)
async def get_member_disease_history(
    member_id_hash: str
) -> Dict[str, Any]:
    """Get diagnosis history for a specific member.
    
    Args:
        member_id_hash: Hashed member identifier
        
    Returns:
        Dictionary with 'columns' and 'rows' containing diagnosis history
    """
    query = """
        SELECT 
            ce.date_of_service,
            cdg.icd_code,
            cdg.diagnosis_description,
            ce.client_amount_due
        FROM claims_entries ce
        JOIN claims_diagnoses cdg ON ce.claim_entry_id = cdg.claim_entry_id
        WHERE ce.member_id_hash = ?
        ORDER BY ce.date_of_service DESC
        LIMIT 100
    """
    
    conn = get_claims_connection()
    try:
        result = conn.execute(query, [member_id_hash]).fetchall()
        return {
            "columns": [
                "date_of_service", "icd_code",
                "diagnosis_description", "claim_cost"
            ],
            "rows": [list(row) for row in result]
        }
    finally:
        conn.close()


@tool(
    name="get_duplicate_medications",
    description=(
        "Identifies members on multiple similar medications (duplicate therapy). "
        "Useful for medication optimization and safety analysis. "
        "Parameters: drug_pattern (str), days_lookback (int, default 90), limit (int, default 50)"
    )
)
async def get_duplicate_medications(
    drug_pattern: str,
    days_lookback: int = 90,
    limit: int = 50
) -> Dict[str, Any]:
    """Identify members on multiple similar medications.
    
    Args:
        drug_pattern: Drug name pattern to search for (e.g., 'statin', 'benzo')
        days_lookback: Number of days to look back (default: 90)
        limit: Maximum number of results to return (default: 50)
        
    Returns:
        Dictionary with 'columns' and 'rows' containing duplicate therapy cases
    """
    query = """
        SELECT 
            m.member_first_name,
            m.member_last_name,
            COUNT(DISTINCT cd.product_service_name) as unique_drug_count,
            STRING_AGG(DISTINCT cd.product_service_name, ', ') as drugs,
            SUM(ce.client_amount_due) as total_spend
        FROM members m
        JOIN claims_entries ce ON m.member_id_hash = ce.member_id_hash
        JOIN claims_drugs cd ON ce.claim_entry_id = cd.claim_entry_id
        WHERE UPPER(cd.product_service_name) LIKE UPPER(?)
        AND ce.date_of_service >= CURRENT_DATE - INTERVAL ? DAY
        GROUP BY m.member_first_name, m.member_last_name
        HAVING COUNT(DISTINCT cd.product_service_name) > 1
        ORDER BY unique_drug_count DESC, total_spend DESC
        LIMIT ?
    """
    
    conn = get_claims_connection()
    try:
        result = conn.execute(query, [f"%{drug_pattern}%", days_lookback, limit]).fetchall()
        return {
            "columns": [
                "member_first_name", "member_last_name",
                "unique_drug_count", "drugs", "total_spend"
            ],
            "rows": [list(row) for row in result]
        }
    finally:
        conn.close()

