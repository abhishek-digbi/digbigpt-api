import unittest
import time
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from orchestrator.repositories.agent_logs_repository import AgentLogsRepository


class TestAgentLogsRepository(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock DB client
        self.mock_db = MagicMock()
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()

        # Set up the mock
        self.mock_db.get_conn.return_value = self.mock_conn
        self.mock_conn.cursor.return_value.__enter__.return_value = self.mock_cursor

        # Initialize the repository with the mock db
        self.repo = AgentLogsRepository(self.mock_db)

        # Sample test data
        self.test_context_id = "test-context-123"
        self.test_user_token = "user-456"
        self.test_input = {"query": "What's for dinner?"}
        self.test_output = {"response": "How about pizza?"}
        self.test_agent = "test_agent"

    @patch('orchestrator.repositories.agent_logs_repository.datetime')
    def test_log_ai_agent(self, mock_datetime):
        """Test logging an AI agent interaction."""
        # Setup mock datetime
        test_time = time.time()
        mock_now = datetime.fromtimestamp(test_time, tz=timezone.utc)
        mock_datetime.utcnow.return_value = mock_now
        
        # Call the method
        self.repo.log_ai_agent(
            agent_id=self.test_agent,
            prompt=json.dumps(self.test_input),
            response_json=self.test_output,
            context_id=self.test_context_id,
            user_token=self.test_user_token,
            duration=None,
        )

        # Verify the SQL was executed with the correct parameters
        # There should be one call for the insert (table/index creation is handled in db_setup.py)
        self.assertEqual(self.mock_cursor.execute.call_count, 1)

        # Get the first (and only) call which should be the insert
        call_args = self.mock_cursor.execute.call_args_list[0][0]
        self.assertIn("INSERT INTO agent_logs", call_args[0])
        self.assertEqual(call_args[1][0], self.test_agent)  # agent_id
        self.assertEqual(json.loads(call_args[1][1]), self.test_output)  # response
        # Check that timestamp is a datetime object with timezone
        self.assertIsInstance(call_args[1][2], datetime)
        self.assertIsNotNone(call_args[1][2].tzinfo)  # Should be timezone-aware
        self.assertEqual(call_args[1][3], self.test_context_id)
        self.assertEqual(call_args[1][4], self.test_user_token)
        self.assertIsNone(call_args[1][5])  # model_context
        self.assertIsNone(call_args[1][6])  # metadata
        self.assertIsNone(call_args[1][7])  # duration

    def test_get_logs_by_context(self):
        """Test retrieving logs by context ID."""
        # Setup mock return value
        test_time = time.time()
        test_datetime = datetime.fromtimestamp(test_time, tz=timezone.utc)
        
        self.mock_cursor.description = [
            ('id',), ('agent_id',), ('prompt',), ('response',),
            ('timestamp',), ('context_id',), ('user_token',),
            ('model_context',), ('metadata',), ('duration',), ('created_at',)
        ]
        self.mock_cursor.fetchall.return_value = [
            (
                1,  # id
                self.test_agent,
                json.dumps(self.test_input),  # prompt
                json.dumps(self.test_output),  # response
                test_datetime,  # timestamp
                self.test_context_id,
                self.test_user_token,
                None,  # model_context
                None,  # metadata
                1.23,  # duration
                test_datetime  # created_at
            )
        ]

        # Call the method
        logs = self.repo.get_logs_by_context(self.test_context_id)

        # Verify the result
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]['agent_id'], self.test_agent)
        self.assertEqual(json.loads(logs[0]['prompt']), self.test_input)
        self.assertEqual(logs[0]['response'], self.test_output)
        self.assertEqual(logs[0]['context_id'], self.test_context_id)
        self.assertEqual(logs[0]['user_token'], self.test_user_token)
        self.assertEqual(logs[0]['duration'], 1.23)
        # Check that timestamp is formatted as a string
        self.assertIsInstance(logs[0]['timestamp'], str)
        self.assertIn(':', logs[0]['timestamp'])  # Simple check for time format

    def test_get_paginated_logs_by_context(self):
        """Test retrieving paginated logs by context ID."""
        # Setup mock return values
        test_time = time.time()
        
        self.mock_cursor.description = [
            ('id',), ('agent_id',), ('prompt',), ('response',),
            ('timestamp',), ('context_id',), ('user_token',),
            ('model_context',), ('metadata',), ('duration',), ('created_at',)
        ]

        # First call (count query)
        def execute_side_effect(query, params):
            if "COUNT" in query:
                self.mock_cursor.fetchone.return_value = (5,)  # Total 5 records

        self.mock_cursor.execute.side_effect = execute_side_effect

        # Second call (data query)
        self.mock_cursor.fetchall.return_value = [
            (
                i + 1,  # id
                f"{self.test_agent}-{i}",  # agent_id
                json.dumps({"query": f"query-{i}"}),  # prompt
                json.dumps({"response": f"response-{i}"}),  # response
                datetime.fromtimestamp(test_time + i, tz=timezone.utc),  # timestamp
                self.test_context_id,
                f"{self.test_user_token}-{i}",
                None,  # model_context
                None,  # metadata
                1.5 + i,  # duration
                datetime.fromtimestamp(test_time + i, tz=timezone.utc)  # created_at
            ) for i in range(3)  # Return 3 records for page 1
        ]

        # Call the method
        logs, pagination = self.repo.get_paginated_logs_by_context(
            context_id=self.test_context_id,
            page=1,
            per_page=3
        )

        # Verify the result
        self.assertEqual(len(logs), 3)
        self.assertEqual(pagination['total'], 5)
        self.assertEqual(pagination['pages'], 2)  # ceil(5/3) = 2 pages
        self.assertEqual(pagination['current_page'], 1)
        self.assertTrue(pagination['has_next'])
        self.assertFalse(pagination['has_previous'])
        
        # Verify timestamps are formatted and duration value
        for idx, log in enumerate(logs):
            self.assertIsInstance(log['timestamp'], str)
            self.assertEqual(log['duration'], 1.5 + idx)


if __name__ == '__main__':
    unittest.main()
