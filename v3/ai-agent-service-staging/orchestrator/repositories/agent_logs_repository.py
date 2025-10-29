from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime, timezone
from utils.db import DBClient
import json
import logging

logger = logging.getLogger(__name__)


class AgentLogsRepository:
    """Repository class for managing Ask Digbi agent interaction logs in the database.
    
    This class provides methods to log and manage AI agent interactions, including
    creating the necessary database table, inserting log entries, and querying logs.
    """

    def __init__(self, db_client: DBClient):
        """Initialize the repository with a database client.
        
        Args:
            db_client (DBClient): An instance of DBClient for database operations.
        """
        self.db_client = db_client

    # Table creation has been moved to db_setup.py

    def _to_serializable(self, obj: Any) -> Any:
        """Convert an object to a JSON-serializable format, falling back to string if needed."""
        if obj is None or isinstance(obj, (str, int, float, bool)):
            return obj
        try:
            if hasattr(obj, 'to_dict') and callable(getattr(obj, 'to_dict', None)):
                return obj.to_dict()
            if hasattr(obj, '__dict__'):
                return {k: self._to_serializable(v) for k, v in obj.__dict__.items()}
            if isinstance(obj, dict):
                return {k: self._to_serializable(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple, set)):
                return [self._to_serializable(item) for item in obj]
            return str(obj)
        except Exception as e:
            logger.warning(f"Could not serialize object of type {type(obj).__name__}, using string representation: {e}")
            return str(obj)

    def log_ai_agent(
            self,
            agent_id: str,
            prompt: str,
            response_json: Any,
            context_id: str,
            user_token: str,
            model_context: Any = None,
            metadata: Any = None,
            timestamp: Optional[Union[datetime, float]] = None,
            duration: Optional[float] = None,
    ) -> None:
        """Log an AI agent interaction to the database.
        
        Args:
            agent_id: ID of the AI agent handling the interaction
            prompt: The prompt text sent to the agent
            response_json: The response data received from the agent (can be any type)
            context_id: Unique identifier for the conversation context
            user_token: Identifier for the user initiating the interaction
            model_context: Optional context about the model used (can be any type)
            metadata: Optional additional metadata (can be any type)
            timestamp: Optional timestamp (datetime or Unix timestamp). If None, uses current time.
            duration: Time taken to execute the agent in seconds
        """
        sql = '''
        INSERT INTO agent_logs
        (agent_id, response, timestamp, context_id, user_token, model_context, metadata, duration)
        VALUES (%s, %s, %s::timestamp with time zone, %s, %s, %s, %s, %s)
        '''

        # Handle timestamp conversion
        if timestamp is None:
            timestamp = datetime.utcnow()
        elif isinstance(timestamp, (int, float)):
            timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        elif hasattr(timestamp, 'timestamp') and not isinstance(timestamp, datetime):
            timestamp = datetime.fromtimestamp(timestamp.timestamp(), tz=timezone.utc)
        elif isinstance(timestamp, datetime) and timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        # Convert objects to serializable format
        serialized_response = self._to_serializable(response_json)
        serialized_model_context = self._to_serializable(model_context)
        serialized_metadata = self._to_serializable(metadata)

        conn = self.db_client.get_conn()
        try:
            with conn.cursor() as c:
                c.execute(
                    sql,
                    (
                        agent_id,
                        json.dumps(serialized_response)
                        if not isinstance(serialized_response, str)
                        else serialized_response,
                        timestamp,
                        context_id,
                        user_token,
                        json.dumps(serialized_model_context)
                        if serialized_model_context is not None
                        else None,
                        json.dumps(serialized_metadata)
                        if serialized_metadata is not None
                        else None,
                        duration,
                    ),
                )
            conn.commit()
        except Exception as e:
            logger.error(f"Error logging AI agent interaction: {e}")
            conn.rollback()
            raise
        finally:
            self.db_client.release_conn(conn)

    def get_logs_by_context(self, context_id: str) -> List[Dict[str, Any]]:
        """Retrieve all logs for a specific context_id.
        
        Args:
            context_id: The context_id to filter logs by
            
        Returns:
            List of log entries with parsed JSON fields
        """
        sql = '''
        SELECT id, agent_id, prompt, response, timestamp, context_id, user_token, model_context, metadata, duration, created_at
        FROM agent_logs
        WHERE context_id = %s
        ORDER BY timestamp ASC
        '''
        return self._execute_log_query(sql, (context_id,))

    def get_paginated_logs_by_context(
            self,
            context_id: str,
            page: int = 1,
            per_page: int = 10
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Retrieve paginated logs for a specific context_id.
        
        Args:
            context_id: The context_id to filter logs by
            page: Page number (1-based)
            per_page: Number of items per page
            
        Returns:
            Tuple of (logs, pagination_metadata)
        """
        offset = (page - 1) * per_page

        # Get total count
        count_sql = 'SELECT COUNT(*) FROM agent_logs WHERE context_id = %s'

        # Get paginated results
        data_sql = '''
        SELECT id, agent_id, prompt, response, timestamp, context_id, user_token, model_context, metadata, duration, created_at
        FROM agent_logs
        WHERE context_id = %s
        ORDER BY timestamp ASC
        LIMIT %s OFFSET %s
        '''

        conn = self.db_client.get_conn()
        try:
            with conn.cursor() as c:
                # Get total count
                c.execute(count_sql, (context_id,))
                total = c.fetchone()[0]

                # Get paginated results
                c.execute(data_sql, (context_id, per_page, offset))
                logs = self._convert_rows_to_dicts(c)

                # Calculate pagination metadata
                pages = (total + per_page - 1) // per_page if total > 0 else 1

                pagination = {
                    'total': total,
                    'pages': pages,
                    'current_page': page,
                    'per_page': per_page,
                    'has_next': page < pages,
                    'has_previous': page > 1
                }

                return logs, pagination

        except Exception as e:
            logger.error(f"Error fetching paginated logs: {e}")
            raise
        finally:
            self.db_client.release_conn(conn)

    def _execute_log_query(self, sql: str, params: tuple) -> List[Dict[str, Any]]:
        """Execute a query and return results with parsed JSON fields.
        
        Args:
            sql: SQL query to execute
            params: Query parameters
            
        Returns:
            List of log entries with parsed JSON fields
        """
        conn = self.db_client.get_conn()
        try:
            with conn.cursor() as c:
                c.execute(sql, params)
                return self._convert_rows_to_dicts(c)
        except Exception as e:
            logger.error(f"Error executing log query: {e}")
            raise
        finally:
            self.db_client.release_conn(conn)

    def _format_timestamp(self, timestamp: Any) -> str:
        """Format timestamp to a human-readable string.
        
        Args:
            timestamp: Timestamp to format (datetime, float, or str)
            
        Returns:
            Formatted timestamp string or empty string if None
        """
        if timestamp is None:
            return ""
        if isinstance(timestamp, (int, float)):
            return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S %Z')
        if isinstance(timestamp, datetime):
            return timestamp.strftime('%Y-%m-%d %H:%M:%S %Z')
        return str(timestamp)

    def _convert_rows_to_dicts(self, cursor) -> List[Dict[str, Any]]:
        """Convert database rows to a list of dictionaries with parsed JSON fields.
        
        Args:
            cursor: Database cursor with executed query
            
        Returns:
            List of log entries with parsed JSON and formatted timestamps
        """
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

        logs = []
        for row in rows:
            log = dict(zip(columns, row))

            # Handle the prompt field (previously input)
            if 'input' in log and 'prompt' not in log:
                log['prompt'] = log.pop('input')

            # Handle the response field (previously output)
            if 'output' in log and 'response' not in log:
                log['response'] = log.pop('output')

            # Handle response field - parse JSON if possible, otherwise keep as is
            if 'response' in log and isinstance(log['response'], str):
                try:
                    log['response'] = json.loads(log['response'])
                except json.JSONDecodeError:
                    # If it's not valid JSON, keep the original string
                    pass

            # Format timestamp if it exists
            if 'timestamp' in log:
                log['timestamp'] = self._format_timestamp(log['timestamp'])

            logs.append(log)

        return logs
