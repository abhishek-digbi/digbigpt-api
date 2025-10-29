#!/usr/bin/env python3
"""
DigbiGPT AI Response Demo
Demonstrates AI-powered responses for healthcare claims analysis.
"""

import asyncio
import json

# Sample data from DigbiGPT system
sample_drug_spend_data = [
    ["HANNAH", "SMITH", 15, 6152.91, 410.19, "2023-01-18", "2023-11-29"],
    ["BOBBY", "HAWKINS", 15, 6133.23, 408.88, "2023-01-17", "2023-12-21"],
    ["TROY", "RELIFORD", 4, 5265.74, 1316.43, "2023-02-07", "2023-11-04"],
    ["RONALD", "NORRIS", 13, 5123.04, 394.08, "2023-01-28", "2023-12-16"],
    ["JAMES", "MCDERMOTT", 7, 4607.51, 658.22, "2023-01-09", "2023-12-13"]
]

sample_cohort_data = [
    ["hypertention", 2023, 1809, 72579, 24198245.01, 333.41, 773]
]

sample_gi_data = [
    ["TRAVIS", "STOFFER", "OMEPRAZOLE", "2023-03-28"],
    ["FREDERICK", "MORING", "OMEPRAZOLE", "2023-03-28"],
    ["JAMES", "MARINE", "OMEPRAZOLE", "2023-03-26"],
    ["GRAYSON", "ZINT", "FAMOTIDINE", "2023-03-23"],
    ["ANGELA", "BOLESCRAFT", "OMEPRAZOLE", "2023-03-23"]
]

def generate_demo_ai_summary(question, data, agent_type):
    """Generate demo AI summaries to show what the system would produce."""
    
    if agent_type == "DRUG_SPEND_AGENT":
        return f"""
## Drug Spend Analysis Results

Based on the claims data for omeprazole in 2023, here are the key findings:

**Top Spenders:**
- **HANNAH SMITH**: $6,153 total spend (15 fills, $410 per fill)
- **BOBBY HAWKINS**: $6,133 total spend (15 fills, $409 per fill)  
- **TROY RELIFORD**: $5,266 total spend (4 fills, $1,316 per fill)

**Key Insights:**
1. **HANNAH SMITH** had the highest total spend on omeprazole in 2023, with consistent monthly fills averaging $410 per prescription.
2. **TROY RELIFORD** shows the highest per-fill cost ($1,316), suggesting either higher dosage or premium formulation.
3. The data shows consistent medication adherence patterns, with most members having 13-17 fills throughout the year.

**Recommendations:**
- Review TROY RELIFORD's prescription for potential cost optimization opportunities
- Consider medication therapy management for high-spend members
- Monitor adherence patterns for clinical outcomes assessment
"""

    elif agent_type == "COHORT_INSIGHTS_AGENT":
        return f"""
## Hypertension Cohort Analysis - 2023

**Population Health Metrics:**
- **Total Members**: 1,809 individuals with hypertension
- **Total Claims**: 72,579 claims processed
- **Total Spend**: $24.2M in healthcare costs
- **Average Claim**: $333.41 per claim
- **Unique Medications**: 773 different drugs used

**Key Insights:**
1. The hypertension cohort represents a significant portion of healthcare spend at $24.2M annually.
2. With 72,579 claims across 1,809 members, the average member has approximately 40 claims per year.
3. The high medication diversity (773 unique drugs) suggests complex treatment regimens for this population.

**Recommendations:**
- Focus on medication adherence programs for this high-cost cohort
- Consider care management interventions to reduce claim frequency
- Review polypharmacy patterns to optimize treatment regimens
"""

    elif agent_type == "CLINICAL_HISTORY_AGENT":
        return f"""
## GI Medication New Starts - Q1 2023

**New Medication Starts:**
- **TRAVIS STOFFER**: Started OMEPRAZOLE on March 28, 2023
- **FREDERICK MORING**: Started OMEPRAZOLE on March 28, 2023
- **JAMES MARINE**: Started OMEPRAZOLE on March 26, 2023
- **GRAYSON ZINT**: Started FAMOTIDINE on March 23, 2023
- **ANGELA BOLESCRAFT**: Started OMEPRAZOLE on March 23, 2023

**Key Insights:**
1. **OMEPRAZOLE** is the most common GI medication started, with 4 out of 5 new starts.
2. The new starts are concentrated in late March 2023, suggesting potential seasonal patterns or clinical guideline updates.
3. **FAMOTIDINE** represents an alternative treatment option for patients who may not tolerate omeprazole.

**Recommendations:**
- Monitor medication adherence and effectiveness for these new starts
- Consider patient education programs for proper medication use
- Track clinical outcomes to assess treatment success rates
"""

    else:
        return f"Found {len(data)} records matching your query. Please review the detailed data in the table below."

def main():
    """Demonstrate AI-powered responses."""
    
    print("🤖 DigbiGPT AI-Powered Response Demo")
    print("=" * 50)
    
    # Test 1: Drug Spend Query
    print("\n📊 Test 1: Drug Spend Analysis")
    print("Question: Which customers spent the most on omeprazole in 2023?")
    print("Response:")
    print(generate_demo_ai_summary(
        "Which customers spent the most on omeprazole in 2023?",
        sample_drug_spend_data,
        "DRUG_SPEND_AGENT"
    ))
    
    # Test 2: Disease Cohort Query
    print("\n📊 Test 2: Disease Cohort Analysis")
    print("Question: Show me the hypertension cohort summary for 2023")
    print("Response:")
    print(generate_demo_ai_summary(
        "Show me the hypertension cohort summary for 2023",
        sample_cohort_data,
        "COHORT_INSIGHTS_AGENT"
    ))
    
    # Test 3: GI New Starts Query
    print("\n📊 Test 3: GI New Starts Analysis")
    print("Question: How many members started GI medications in Q1 2023?")
    print("Response:")
    print(generate_demo_ai_summary(
        "How many members started GI medications in Q1 2023?",
        sample_gi_data,
        "CLINICAL_HISTORY_AGENT"
    ))
    
    print("\n🎉 This demonstrates what your DigbiGPT system will produce with AI-powered responses!")
    print("The AI provides:")
    print("✅ Clear summaries of the data")
    print("✅ Key insights and patterns")
    print("✅ Actionable recommendations")
    print("✅ Clinical and business context")

if __name__ == "__main__":
    main()


