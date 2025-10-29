# mcp_redshift_server.py
# FastMCP 2.x server over HTTP(SSE).

import os
import time
from typing import Dict, Any, Optional, List

import boto3
from fastmcp import FastMCP
from tabulate import tabulate  # <- pretty output

REGION = os.environ.get("AWS_REGION", "us-east-1")
DATABASE = os.environ.get("REDSHIFT_DATABASE")
WORKGROUP = os.environ.get("REDSHIFT_WORKGROUP")
SECRET_ARN = os.environ.get("REDSHIFT_SECRET_ARN")

if not all([DATABASE, WORKGROUP, SECRET_ARN]):
    raise SystemExit(
        "Missing env vars. Set REDSHIFT_DATABASE, REDSHIFT_WORKGROUP, REDSHIFT_SECRET_ARN"
    )

client = boto3.client("redshift-data", region_name=REGION)

def _execute_sql(sql: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    print(f"[Executing SQL]\n{sql}\nParams: {params}\n", flush=True)
    args: Dict[str, Any] = dict(
        Database=DATABASE,
        WorkgroupName=WORKGROUP,
        SecretArn=SECRET_ARN,
        Sql=sql,
    )
    if params:
        args["Parameters"] = [{"name": k, "value": str(v)} for k, v in params.items()]

    resp = client.execute_statement(**args)
    qid = resp["Id"]

    while True:
        d = client.describe_statement(Id=qid)
        st = d["Status"]
        if st in ("FINISHED", "FAILED", "ABORTED"):
            if st != "FINISHED":
                raise RuntimeError(f"SQL failed: {d.get('Error')}")
            break
        time.sleep(0.3)

    out = {"columns": [], "rows": []}
    if d.get("HasResultSet"):
        page = client.get_statement_result(Id=qid)
        cols = page.get("ColumnMetadata", [])
        out["columns"] = [c["name"] for c in cols]
        for rec in page.get("Records", []):
            row = []
            for cell in rec:
                row.append(next(iter(cell.values())))
            out["rows"].append(row)

    # Pretty print with tabulate (log + include in return)
    if out["columns"]:
        pretty = tabulate(out["rows"], headers=out["columns"], tablefmt="github")
    else:
        pretty = "(no rows)"
    print(f"[SQL Pretty]\n{pretty}\n", flush=True)
    out["table"] = pretty

    return out

def _expand_in_params(param_base: str, values: List[str], params: Dict[str, Any]) -> str:
    if not values:
        raise ValueError("Employers list cannot be empty.")
    placeholders = []
    for i, v in enumerate(values):
        key = f"{param_base}_{i}"
        params[key] = v
        placeholders.append(f":{key}")
    return ", ".join(placeholders)

mcp = FastMCP("RedshiftClaimsDemo")

# ---------------------
# Resources (use VALID URIs — they must include a scheme://)
# ---------------------
@mcp.resource("redshift://claims/schema", description="Schema for claims_demo.claims", mime_type="application/json")
def claims_schema_resource() -> Dict[str, Any]:
    sql = """
    SELECT table_schema, table_name, column_name, data_type, ordinal_position
    FROM information_schema.columns
    WHERE table_schema = 'claims_demo' AND table_name = 'claims'
    ORDER BY ordinal_position;
    """
    return _execute_sql(sql)

# Use ROW_NUMBER() instead of LIMIT param (portable & bind-friendly)
@mcp.resource("redshift://claims/preview/{n}", description="Preview N rows from claims_demo.claims", mime_type="application/json")
def claims_preview_resource(n: int = 10) -> Dict[str, Any]:
    sql = """
    WITH ordered AS (
      SELECT employer_name, employee_name, disease_category, year_of_claim, claim_amount,
             ROW_NUMBER() OVER (ORDER BY year_of_claim DESC, claim_amount DESC) AS rn
      FROM claims_demo.claims
    )
    SELECT employer_name, employee_name, disease_category, year_of_claim, claim_amount
    FROM ordered
    WHERE rn <= :n
    ORDER BY rn;
    """
    return _execute_sql(sql, {"n": n})

# ---------------------
# Tools
# ---------------------
@mcp.tool()
def get_schema() -> Dict[str, Any]:
    """Return table/column names for schema claims_demo.claims."""
    sql = """
    SELECT table_schema, table_name, column_name, data_type, ordinal_position
    FROM information_schema.columns
    WHERE table_schema = 'claims_demo' AND table_name = 'claims'
    ORDER BY ordinal_position;
    """
    return _execute_sql(sql)

@mcp.tool()
def run_sql(sql: str) -> Dict[str, Any]:
    """
    Run READ-ONLY SQL. Only SELECT allowed. Auto-LIMIT 500 for non-aggregates.
    """
    s = sql.strip().rstrip(";")
    low = s.lower()
    if not low.startswith("select"):
        raise ValueError("Read-only server: only SELECT statements are allowed.")
    needs_limit = (
        " limit " not in low
        and "count(" not in low
        and "avg(" not in low
        and "sum(" not in low
        and "max(" not in low
        and "min(" not in low
        and "group by" not in low
    )
    if needs_limit:
        s = f"{s} LIMIT 500"
    return _execute_sql(s + ";")

@mcp.tool()
def employer_with_highest_claimers() -> Dict[str, Any]:
    """Employer with most distinct employees who filed claims."""
    sql = """
    SELECT employer_name, COUNT(DISTINCT employee_name) AS claimant_count
    FROM claims_demo.claims
    GROUP BY employer_name
    ORDER BY claimant_count DESC, employer_name ASC
    LIMIT 1;
    """
    return _execute_sql(sql)

@mcp.tool()
def top_employee_for_employer(employer: str) -> Dict[str, Any]:
    """Employee with highest total claim_amount for a given employer."""
    sql = """
    SELECT employee_name, SUM(claim_amount) AS total_claim_amount
    FROM claims_demo.claims
    WHERE employer_name = :employer
    GROUP BY employee_name
    ORDER BY total_claim_amount DESC, employee_name ASC
    LIMIT 1;
    """
    return _execute_sql(sql, {"employer": employer})

@mcp.tool()
def average_claim_for_employer(employer: str) -> Dict[str, Any]:
    """Average claim_amount for a given employer."""
    sql = """
    SELECT AVG(claim_amount) AS avg_claim
    FROM claims_demo.claims
    WHERE employer_name = :employer;
    """
    return _execute_sql(sql, {"employer": employer})

# ---- New multi-employer tools you wanted ----
@mcp.tool()
def top_disease_categories_multi(employers: List[str], limit: int = 3) -> Dict[str, Any]:
    """
    For each employer, return the top-N disease categories by total claim_amount.
    Columns: employer_name, disease_category, total_claim_amount, claim_count.
    """
    params: Dict[str, Any] = {"limit": limit}
    in_list = _expand_in_params("emp", employers, params)
    sql = f"""
    WITH agg AS (
      SELECT employer_name,
             disease_category,
             SUM(claim_amount)   AS total_claim_amount,
             COUNT(*)            AS claim_count
      FROM claims_demo.claims
      WHERE employer_name IN ({in_list})
      GROUP BY employer_name, disease_category
    ),
    ranked AS (
      SELECT *,
             ROW_NUMBER() OVER (
               PARTITION BY employer_name
               ORDER BY total_claim_amount DESC, disease_category ASC
             ) AS rn
      FROM agg
    )
    SELECT employer_name, disease_category, total_claim_amount, claim_count
    FROM ranked
    WHERE rn <= :limit
    ORDER BY employer_name ASC, total_claim_amount DESC, disease_category ASC;
    """
    return _execute_sql(sql, params)

@mcp.tool()
def top_category_employee_stats(employers: List[str], limit: int = 3) -> Dict[str, Any]:
    """
    1) Derive each employer's top-N categories.
    2) Restrict to the UNION of those categories across employers.
    3) Return per-category distinct employee count + avg claim, plus an _ALL_ row.
    """
    params: Dict[str, Any] = {"limit": limit}
    in_list = _expand_in_params("emp", employers, params)
    sql = f"""
    WITH agg AS (
      SELECT employer_name,
             disease_category,
             SUM(claim_amount) AS total_claim_amount
      FROM claims_demo.claims
      WHERE employer_name IN ({in_list})
      GROUP BY employer_name, disease_category
    ),
    ranked AS (
      SELECT employer_name,
             disease_category,
             total_claim_amount,
             ROW_NUMBER() OVER (
               PARTITION BY employer_name
               ORDER BY total_claim_amount DESC, disease_category ASC
             ) AS rn
      FROM agg
    ),
    selected_cats AS (
      SELECT DISTINCT disease_category
      FROM ranked
      WHERE rn <= :limit
    ),
    filtered AS (
      SELECT c.employer_name,
             c.employee_name,
             c.disease_category,
             c.claim_amount
      FROM claims_demo.claims c
      JOIN selected_cats s
        ON c.disease_category = s.disease_category
      WHERE c.employer_name IN ({in_list})
    )
    SELECT disease_category,
           COUNT(DISTINCT employee_name) AS distinct_employees,
           AVG(claim_amount)             AS avg_claim_amount
    FROM filtered
    GROUP BY disease_category

    UNION ALL

    SELECT '_ALL_' AS disease_category,
           COUNT(DISTINCT employee_name) AS distinct_employees,
           AVG(claim_amount)             AS avg_claim_amount
    FROM filtered

    ORDER BY (CASE WHEN disease_category = '_ALL_' THEN 1 ELSE 0 END),
             disease_category ASC;
    """
    return _execute_sql(sql, params)

if __name__ == "__main__":
    print("[SERVER] SSE listening at http://127.0.0.1:8811/sse", flush=True)
    mcp.run(transport="http", host="127.0.0.1", port=8811)
