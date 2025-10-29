"""DigbiGPT Claims Database Tools - MCP Client Wrappers

This module provides tools that wrap MCP server calls for claims database queries.
All tools are pre-vetted SQL queries executed via the MCP server for security and auditability.
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional

import httpx
from tools import tool

logger = logging.getLogger(__name__)


class ClaimsServerClient:
    """Client for communicating with claims server."""
    
    def __init__(self, url: str = "http://localhost:8811"):
        self.url = url
        
    async def call_tool(
        self,
        tool_name: str,
        args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call a claims server tool and return result."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.url}/tools/call",
                    json={"name": tool_name, "arguments": args},
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                
                if result.get("is_error"):
                    return {
                        "error": result["content"][0].get("error", "Unknown error"),
                        "columns": [],
                        "rows": []
                    }
                
                return result["content"][0]
        except Exception as e:
            logger.error(f"Claims server tool call failed for {tool_name}: {e}")
            return {
                "error": f"Failed to call {tool_name}",
                "details": str(e),
                "columns": [],
                "rows": []
            }


# Singleton instance
claims_client = ClaimsServerClient()


@tool
async def get_top_drug_spend(
    drug_name: str,
    year: int,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Returns employers with highest spend on a specific drug.
    
    This tool queries the claims database to find which employers have the highest
    total spending on a particular medication, including member counts and utilization metrics.
    
    Args:
        drug_name: Name of the drug (e.g., "rosuvastatin", "metformin")
        year: Year of claims to analyze (e.g., 2024)
        limit: Maximum number of results to return (default: 10)
        
    Returns:
        Dict containing:
        - columns: List of column names
        - rows: List of data rows
        - table: Formatted table string (if available)
        
    Example:
        result = await get_top_drug_spend("rosuvastatin", 2024, 5)
        # Returns top 5 employers by rosuvastatin spend in 2024
    """
    logger.info(f"Getting top drug spend for {drug_name} in {year}, limit {limit}")
    
    return await claims_client.call_tool("get_top_drug_spend", {
        "drug_name": drug_name,
        "year": year,
        "limit": limit
    })


@tool
async def get_member_disease_history(member_id_hash: str) -> Dict[str, Any]:
    """
    Returns diagnosis history for a specific member.
    
    This tool provides a chronological view of all diagnoses for a member,
    including when conditions were first and last observed, and claim frequency.
    
    Args:
        member_id_hash: Hashed identifier for the member
        
    Returns:
        Dict containing:
        - columns: List of column names
        - rows: List of data rows with diagnosis information
        - table: Formatted table string (if available)
        
    Example:
        result = await get_member_disease_history("f42b93cc52b47fe753bf84a1464c36d3...")
        # Returns diagnosis history for member
    """
    logger.info(f"Getting disease history for member {member_id_hash[:12]}...")
    
    return await claims_client.call_tool("get_member_disease_history", {
        "member_id_hash": member_id_hash
    })


@tool
async def get_gi_new_starts(
    start_date: str,
    end_date: str,
    limit: int = 50
) -> Dict[str, Any]:
    """
    Returns members who started GI medications in date range.
    
    This tool identifies members who initiated gastrointestinal medications
    within a specified time period, useful for tracking new GI therapy starts.
    
    Args:
        start_date: Start date in YYYY-MM-DD format (e.g., "2023-01-01")
        end_date: End date in YYYY-MM-DD format (e.g., "2023-12-31")
        limit: Maximum number of results (default: 50)
        
    Returns:
        Dict containing:
        - columns: List of column names
        - rows: List of data rows with member and medication information
        - table: Formatted table string (if available)
        
    Example:
        result = await get_gi_new_starts("2023-01-01", "2023-03-31", 50)
        # Returns Q1 2023 GI medication new starts
    """
    logger.info(f"Getting GI new starts from {start_date} to {end_date}, limit {limit}")
    
    return await claims_client.call_tool("get_gi_new_starts", {
        "start_date": start_date,
        "end_date": end_date,
        "limit": limit
    })


@tool
async def get_duplicate_medications(
    drug_pattern: str,
    days_lookback: int = 90,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Identifies members on multiple similar medications in recent period.
    
    This tool helps identify potential medication safety issues by finding
    members who are prescribed multiple medications matching a pattern,
    which could indicate duplicate therapy or potential drug interactions.
    
    Args:
        drug_pattern: Drug name pattern to search (e.g., "STATIN", "ZEPAM" for benzos)
        days_lookback: Number of days to look back (default: 90)
        limit: Maximum number of results (default: 20)
        
    Returns:
        Dict containing:
        - columns: List of column names
        - rows: List of data rows with duplicate medication information
        - table: Formatted table string (if available)
        
    Example:
        result = await get_duplicate_medications("STATIN")
        # Returns members on multiple statin medications in last 90 days
        result = await get_duplicate_medications("ZEPAM", 180, 10)
        # Returns top 10 members on multiple benzo medications in last 180 days
    """
    logger.info(f"Getting duplicate medications for pattern {drug_pattern}, lookback {days_lookback} days, limit {limit}")
    
    return await claims_client.call_tool("get_duplicate_medications", {
        "drug_pattern": drug_pattern,
        "days_lookback": days_lookback,
        "limit": limit
    })


@tool
async def get_disease_cohort_summary(
    disease_category: str,
    year: int
) -> Dict[str, Any]:
    """
    Returns summary statistics for members in a disease cohort.
    
    This tool provides a comprehensive summary of a disease cohort's population health
    metrics including member counts, total spend, average claims, and medication usage.
    
    Args:
        disease_category: Disease category (e.g., "hypertention", "diabetes")
        year: Year for the summary (e.g., 2023, 2024)
        
    Returns:
        Dict containing:
        - columns: List of column names
        - rows: List of data rows with cohort metrics
        - table: Formatted table string (if available)
        
    Example:
        result = await get_disease_cohort_summary("hypertention", 2024)
        # Returns comprehensive 2024 summary for hypertension cohort
    """
    logger.info(f"Getting disease cohort summary for {disease_category} in {year}")
    
    return await claims_client.call_tool("get_disease_cohort_summary", {
        "disease_category": disease_category,
        "year": year
    })


@tool
async def get_schema() -> Dict[str, Any]:
    """
    Returns database schema information for claims tables.
    
    This tool provides metadata about the claims database schema,
    useful for understanding available tables and columns.
    
    Returns:
        Dict containing schema information with table and column details
        
    Example:
        result = await get_schema()
        # Returns schema information for claims, diagnoses, members tables
    """
    logger.info("Getting database schema information")
    
    return await claims_client.call_tool("get_schema", {})


# Utility function for testing claims server connection
async def test_claims_server_connection() -> bool:
    """
    Test the connection to the claims server.
    
    Returns:
        bool: True if connection successful, False otherwise
    """
    try:
        result = await claims_client.call_tool("get_schema", {})
        return "error" not in result
    except Exception as e:
        logger.error(f"Claims server connection test failed: {e}")
        return False

