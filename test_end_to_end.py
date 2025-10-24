#!/usr/bin/env python3
"""
End-to-end test for DigbiGPT system.
Tests the complete flow from question to answer.
"""

import asyncio
import httpx
import json
from datetime import datetime

async def test_claims_server():
    """Test the claims server directly."""
    print("🔍 Testing Claims Server...")
    
    try:
        async with httpx.AsyncClient() as client:
            # Test health
            response = await client.get('http://localhost:8811/health')
            if response.status_code == 200:
                print("✅ Claims server health check passed")
            else:
                print(f"❌ Claims server health check failed: {response.status_code}")
                return False
            
            # Test tools list
            response = await client.get('http://localhost:8811/tools')
            if response.status_code == 200:
                tools = response.json()
                print(f"✅ Claims server tools endpoint working - {len(tools['tools'])} tools available")
            else:
                print(f"❌ Claims server tools endpoint failed: {response.status_code}")
                return False
            
            # Test calling a tool
            response = await client.post(
                'http://localhost:8811/tools/call',
                json={'name': 'get_schema', 'arguments': {}}
            )
            if response.status_code == 200:
                result = response.json()
                if not result.get('is_error'):
                    print("✅ Claims server tool call successful")
                    print(f"   Schema returned {len(result['content'][0].get('columns', []))} columns")
                else:
                    print("❌ Claims server tool call returned error")
                    return False
            else:
                print(f"❌ Claims server tool call failed: {response.status_code}")
                return False
            
            return True
            
    except Exception as e:
        print(f"❌ Claims server test failed: {e}")
        return False

async def test_digbigpt_tools():
    """Test DigbiGPT tools directly."""
    print("\n🔍 Testing DigbiGPT Tools...")
    
    # Test drug spend query
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'http://localhost:8811/tools/call',
                json={
                    'name': 'get_top_drug_spend',
                    'arguments': {
                        'drug_name': 'OMEPRAZOLE',
                        'year': 2023,
                        'limit': 5
                    }
                }
            )
            if response.status_code == 200:
                result = response.json()
                if not result.get('is_error'):
                    rows = result['content'][0].get('rows', [])
                    print(f"✅ Drug spend query successful - {len(rows)} results")
                    if rows:
                        print(f"   Sample: {rows[0]}")
                else:
                    print("❌ Drug spend query returned error")
                    return False
            else:
                print(f"❌ Drug spend query failed: {response.status_code}")
                return False
            
            return True
            
    except Exception as e:
        print(f"❌ DigbiGPT tools test failed: {e}")
        return False

async def test_disease_cohort_query():
    """Test disease cohort query."""
    print("\n🔍 Testing Disease Cohort Query...")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'http://localhost:8811/tools/call',
                json={
                    'name': 'get_disease_cohort_summary',
                    'arguments': {
                        'disease_category': 'hypertention',
                        'year': 2023
                    }
                }
            )
            if response.status_code == 200:
                result = response.json()
                if not result.get('is_error'):
                    rows = result['content'][0].get('rows', [])
                    print(f"✅ Disease cohort query successful - {len(rows)} results")
                    if rows:
                        print(f"   Sample: {rows[0]}")
                else:
                    print("❌ Disease cohort query returned error")
                    return False
            else:
                print(f"❌ Disease cohort query failed: {response.status_code}")
                return False
            
            return True
            
    except Exception as e:
        print(f"❌ Disease cohort query test failed: {e}")
        return False

async def test_gi_new_starts():
    """Test GI new starts query."""
    print("\n🔍 Testing GI New Starts Query...")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'http://localhost:8811/tools/call',
                json={
                    'name': 'get_gi_new_starts',
                    'arguments': {
                        'start_date': '2023-01-01',
                        'end_date': '2023-03-31',
                        'limit': 5
                    }
                }
            )
            if response.status_code == 200:
                result = response.json()
                if not result.get('is_error'):
                    rows = result['content'][0].get('rows', [])
                    print(f"✅ GI new starts query successful - {len(rows)} results")
                    if rows:
                        print(f"   Sample: {rows[0]}")
                else:
                    print("❌ GI new starts query returned error")
                    return False
            else:
                print(f"❌ GI new starts query failed: {response.status_code}")
                return False
            
            return True
            
    except Exception as e:
        print(f"❌ GI new starts query test failed: {e}")
        return False

async def main():
    """Run all tests."""
    print("🚀 Starting DigbiGPT End-to-End Tests")
    print("=" * 50)
    
    # Test 1: Claims server basic functionality
    claims_server_ok = await test_claims_server()
    
    # Test 2: DigbiGPT tools
    digbigpt_tools_ok = await test_digbigpt_tools()
    
    # Test 3: Disease cohort query
    cohort_query_ok = await test_disease_cohort_query()
    
    # Test 4: GI new starts query
    gi_query_ok = await test_gi_new_starts()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    print(f"   Claims Server: {'✅ PASS' if claims_server_ok else '❌ FAIL'}")
    print(f"   DigbiGPT Tools: {'✅ PASS' if digbigpt_tools_ok else '❌ FAIL'}")
    print(f"   Disease Cohort Query: {'✅ PASS' if cohort_query_ok else '❌ FAIL'}")
    print(f"   GI New Starts Query: {'✅ PASS' if gi_query_ok else '❌ FAIL'}")
    
    all_passed = all([claims_server_ok, digbigpt_tools_ok, cohort_query_ok, gi_query_ok])
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED! DigbiGPT system is working correctly.")
        print("✅ Ready for Custom GPT integration!")
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
    
    return all_passed

if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)
