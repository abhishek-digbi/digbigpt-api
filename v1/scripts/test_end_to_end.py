#!/usr/bin/env python3
"""
DigbiGPT End-to-End Integration Test
Tests the complete flow from question to answer.
"""

import asyncio
import httpx
import json
from datetime import datetime

async def test_digbigpt_api():
    """Test the DigbiGPT API directly."""
    print("🔍 Testing DigbiGPT API...")
    
    try:
        async with httpx.AsyncClient() as client:
            # Test health endpoint
            response = await client.get('http://localhost:9000/api/health')
            if response.status_code == 200:
                print("✅ DigbiGPT API health check passed")
            else:
                print(f"❌ DigbiGPT API health check failed: {response.status_code}")
                return False
            
            # Test agents endpoint
            response = await client.get('http://localhost:9000/api/digbigpt/agents')
            if response.status_code == 200:
                agents = response.json()
                print(f"✅ DigbiGPT agents endpoint working - {len(agents['agents'])} agents available")
            else:
                print(f"❌ DigbiGPT agents endpoint failed: {response.status_code}")
                return False
            
            # Test tools endpoint
            response = await client.get('http://localhost:9000/api/digbigpt/tools')
            if response.status_code == 200:
                tools = response.json()
                print(f"✅ DigbiGPT tools endpoint working - {len(tools['tools'])} tools available")
            else:
                print(f"❌ DigbiGPT tools endpoint failed: {response.status_code}")
                return False
            
            return True
            
    except Exception as e:
        print(f"❌ DigbiGPT API test failed: {e}")
        return False

async def test_digbigpt_query():
    """Test a DigbiGPT query."""
    print("\n🔍 Testing DigbiGPT Query...")
    
    try:
        async with httpx.AsyncClient() as client:
            # Test drug spend query
            response = await client.post(
                'http://localhost:9000/api/digbigpt/ask',
                json={
                    'question': 'Which customers spent the most on omeprazole in 2023?',
                    'user_id': 'test_user_123'
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ DigbiGPT query successful")
                print(f"   Agent used: {result.get('agent_used', 'Unknown')}")
                print(f"   Confidence: {result.get('confidence', 0)}")
                print(f"   Answer preview: {result.get('answer', '')[:100]}...")
                return True
            else:
                print(f"❌ DigbiGPT query failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
            
    except Exception as e:
        print(f"❌ DigbiGPT query test failed: {e}")
        return False

async def test_disease_cohort_query():
    """Test disease cohort query."""
    print("\n🔍 Testing Disease Cohort Query...")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'http://localhost:9000/api/digbigpt/ask',
                json={
                    'question': 'Show me the hypertension cohort summary for 2023',
                    'user_id': 'test_user_123'
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Disease cohort query successful")
                print(f"   Agent used: {result.get('agent_used', 'Unknown')}")
                print(f"   Confidence: {result.get('confidence', 0)}")
                return True
            else:
                print(f"❌ Disease cohort query failed: {response.status_code}")
                return False
            
    except Exception as e:
        print(f"❌ Disease cohort query test failed: {e}")
        return False

async def test_gi_new_starts_query():
    """Test GI new starts query."""
    print("\n🔍 Testing GI New Starts Query...")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'http://localhost:9000/api/digbigpt/ask',
                json={
                    'question': 'How many members started GI medications in Q1 2023?',
                    'user_id': 'test_user_123'
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ GI new starts query successful")
                print(f"   Agent used: {result.get('agent_used', 'Unknown')}")
                print(f"   Confidence: {result.get('confidence', 0)}")
                return True
            else:
                print(f"❌ GI new starts query failed: {response.status_code}")
                return False
            
    except Exception as e:
        print(f"❌ GI new starts query test failed: {e}")
        return False

async def main():
    """Run all tests."""
    print("🚀 Starting DigbiGPT End-to-End Tests")
    print("=" * 50)
    
    # Test 1: API basic functionality
    api_ok = await test_digbigpt_api()
    
    # Test 2: Basic query
    query_ok = await test_digbigpt_query()
    
    # Test 3: Disease cohort query
    cohort_query_ok = await test_disease_cohort_query()
    
    # Test 4: GI new starts query
    gi_query_ok = await test_gi_new_starts_query()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    print(f"   DigbiGPT API: {'✅ PASS' if api_ok else '❌ FAIL'}")
    print(f"   Basic Query: {'✅ PASS' if query_ok else '❌ FAIL'}")
    print(f"   Disease Cohort Query: {'✅ PASS' if cohort_query_ok else '❌ FAIL'}")
    print(f"   GI New Starts Query: {'✅ PASS' if gi_query_ok else '❌ FAIL'}")
    
    all_passed = all([api_ok, query_ok, cohort_query_ok, gi_query_ok])
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED! DigbiGPT system is working correctly.")
        print("✅ Ready for production deployment!")
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
        print("💡 Make sure the DigbiGPT service is running on http://localhost:9000")
    
    return all_passed

if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)


