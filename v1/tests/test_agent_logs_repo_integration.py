"""
Integration test for AgentLogsRepository.

This script demonstrates how to use the repository with a real database.
It reads the database configuration from the .env file.
"""
import sys
import os
import time
import logging
import pytest
from pathlib import Path
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent.parent))

# Load environment variables from .env file
load_dotenv()

# Skip this test unless explicitly requested
pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="requires database",
)

from utils.db import DBClient
from orchestrator.repositories.agent_logs_repository import AgentLogsRepository

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cleanup_test_data(db_client, context_ids, user_tokens):
    """Clean up test data from the database."""
    if not context_ids and not user_tokens:
        return
    
    conn = None
    try:
        conn = db_client.get_conn()
        if conn is None:
            print("! Could not get database connection")
            return
            
        with conn.cursor() as c:
            # Delete test logs by context_id
            for context_id in context_ids:
                try:
                    c.execute("DELETE FROM agent_logs WHERE context_id = %s", (context_id,))
                    print(f"✓ Cleaned up logs for context: {context_id}")
                except Exception as e:
                    print(f"! Error cleaning up context {context_id}: {e}")
            # Delete test logs by user_token
            for token in user_tokens:
                try:
                    c.execute("DELETE FROM agent_logs WHERE user_token = %s", (token,))
                    print(f"✓ Cleaned up logs for user: {token}")
                except Exception as e:
                    print(f"! Error cleaning up user {token}: {e}")
        conn.commit()
    except Exception as e:
        print(f"! Error during cleanup: {e}")
        if conn is not None:
            conn.rollback()
    finally:
        if conn is not None:
            db_client.release_conn(conn)

def test_integration():
    """Test the repository with a real database."""
    # Initialize database client with values from .env
    db_config = {
        'params': {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 5432)),
            'database': os.getenv('DB_NAME', 'postgres'),
            'user': os.getenv('DB_USER', 'ai_agents'),
            'password': os.getenv('DB_PASSWORD', ''),
            'connect_timeout': 5
        },
        'minconn': 1,
        'maxconn': 5
    }
    
    print("\n=== Database Configuration ===")
    print(f"Host: {db_config['params']['host']}")
    print(f"Port: {db_config['params']['port']}")
    print(f"Database: {db_config['params']['database']}")
    print(f"User: {db_config['params']['user']}")
    print("Password: [redacted]" if db_config['params']['password'] else "Password: (empty)")
    
    try:
        print("\n=== Initializing DB Client ===")
        db_client = DBClient(**db_config)
        print("✓ DB Client initialized successfully")
        
        # Test the connection
        print("\n=== Testing Database Connection ===")
        conn = db_client.get_conn()
        if conn is None:
            raise Exception("Failed to get database connection")
            
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            result = cur.fetchone()
            if result and result[0] == 1:
                print("✓ Database connection test successful")
            else:
                raise Exception("Unexpected result from database")
        db_client.release_conn(conn)
        
        print("\n=== Initializing AgentLogsRepository ===")
        repo = AgentLogsRepository(db_client)
        print("✓ AgentLogsRepository initialized successfully")
        
    except Exception as e:
        print(f"\n! Error during initialization: {e}")
        print("\nTroubleshooting steps:")
        print("1. Make sure the database server is running")
        print("2. Verify the database credentials in your .env file")
        print("3. Check if the database exists and the user has proper permissions")
        print("4. Ensure the database host is accessible from your machine")
        print("5. Check if the database port is correct and not blocked by a firewall")
        raise
    
    # Test data
    context_id = f"test-context-{int(time.time())}"
    user_token = f"test-user-{int(time.time())}"  # Make user token unique too
    test_contexts = [context_id]  # Track test contexts for cleanup
    test_users = [user_token]     # Track test users for cleanup
    
    try:
        # Test 1: Log a new interaction
        print("\n=== Testing log_ai_agent ===")
        test_timestamp = time.time()
        repo.log_ai_agent(
            agent_id="test_agent",
            prompt="What's for dinner?",
            response_json={"response": "How about pizza?"},
            context_id=context_id,
            user_token=user_token,
            timestamp=test_timestamp
        )
        print(f"✓ Logged interaction at timestamp: {test_timestamp}")
        print("✓ Successfully logged interaction")
        
        # Test 2: Get logs by context
        print("\n=== Testing get_logs_by_context ===")
        logs = repo.get_logs_by_context(context_id)
        print(f"Found {len(logs)} log(s) for context {context_id}")
        for i, log in enumerate(logs, 1):
            print(f"\nLog {i}:")
            print(f"  Agent: {log['agent_id']}")
            print(f"  Prompt: {log['prompt']}")
            print(f"  Response: {log['response']}")
            print(f"  Timestamp: {log.get('timestamp', 'N/A')} (Type: {type(log.get('timestamp')).__name__})")
        
        # Test 3: Test pagination
        print("\n=== Testing get_paginated_logs_by_context ===")
        logs, pagination = repo.get_paginated_logs_by_context(
            context_id=context_id,
            page=1,
            per_page=10
        )
        print(f"Found {len(logs)} logs (page {pagination['current_page']} of {pagination['pages']})")
        print(f"Total logs: {pagination['total']}")
        
        # Test 4: Log another interaction with the same context
        print("\n=== Testing multiple logs with same context ===")
        repo.log_ai_agent(
            agent_id="test_agent",
            prompt="What about breakfast?",
            response_json={"response": "How about oatmeal with fruits?"},
            context_id=context_id,
            user_token=user_token
        )
        print("✓ Logged second interaction")
        
        # Verify we now have 2 logs for this context
        logs = repo.get_logs_by_context(context_id)
        print(f"Found {len(logs)} logs for context after second insert")
        assert len(logs) == 2, f"Expected 2 logs, got {len(logs)}"
        
        # Test 5: Get logs by context (similar to getting by user)
        print("\n=== Testing get_logs_by_context ===")
        context_logs = repo.get_logs_by_context(context_id)
        print(f"Found {len(context_logs)} logs for context {context_id}")
        for i, log in enumerate(context_logs, 1):
            print(f"\nLog {i}:")
            print(f"  Agent: {log['agent_id']}")
            print(f"  Prompt: {log['prompt']}")
            print(f"  Response: {log['response']}")
            print(f"  Context ID: {log['context_id']}")
            print(f"  User Token: {log['user_token']}")
        
        # Test 6: Test pagination with multiple logs
        print("\n=== Testing pagination with multiple logs ===")
        logs, pagination = repo.get_paginated_logs_by_context(
            context_id=context_id,
            page=1,
            per_page=1
        )
        print(f"Page 1: {len(logs)} logs")
        print(f"Total pages: {pagination['pages']}")
        print(f"Has next: {pagination['has_next']}")
        
        if pagination['has_next']:
            logs, _ = repo.get_paginated_logs_by_context(
                context_id=context_id,
                page=2,
                per_page=1
            )
            print(f"Page 2: {len(logs)} logs")
        
        print("\n✓ All tests completed successfully!")
        
    except Exception as e:
        print(f"! Test failed: {e}")
        raise
    finally:
        # Clean up test data
        print("\n=== Cleaning up test data ===")
        cleanup_test_data(db_client, test_contexts, test_users)
        db_client.close()

if __name__ == "__main__":
    try:
        test_integration()
    except Exception as e:
        print(f"! Error: {e}")
        sys.exit(1)
