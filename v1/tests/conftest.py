import os
import pytest
from unittest.mock import Mock
from digbi_fastapi.testclient import TestClient

"""
Ensure OpenAI Agents tracing is disabled during tests.

The `openai-agents` package registers a default tracing processor that attempts
to export traces over the network and logs during interpreter shutdown. In
offline or sandboxed environments this can generate noisy logging errors after
pytest finishes. Setting this env var early prevents registration/teardown side
effects.
"""
os.environ.setdefault("OPENAI_AGENTS_DISABLE_TRACING", "true")


@pytest.fixture
def app(mocker):
    class DummyPool:
        class DummyConn:
            class DummyCursor:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    pass

                def execute(self, *args, **kwargs):
                    pass

                def fetchone(self):
                    return None

                @property
                def description(self):
                    return []

                @property
                def rowcount(self):
                    return 0

            def cursor(self):
                return self.DummyCursor()

            def commit(self):
                pass

            def rollback(self):
                pass

        def getconn(self):
            return self.DummyConn()
        def putconn(self, conn):
            pass
        def closeall(self):
            pass

    mocker.patch('psycopg2.pool.SimpleConnectionPool', return_value=DummyPool())
    mocker.patch('redis.StrictRedis', return_value=Mock())
    # Provide dummy keys so service initialization succeeds
    mocker.patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "DIGBI_REPORT_METADATA_ASSISTANT_ID": "asst_test",
        "MEAL_RATING_ASSISTANT_ID": "asst_test",
        "ASK_DIGBI_ASSISTANT_ID": "asst_test",
        "DIGBI_URL": "http://test",
        "ASK_DIGBI_RESPONSE_PATH": "/ask",
        "MEAL_RATING_RESPONSE_PATH": "/meal",
    })
    from app import create_app
    application = create_app()
    return application

@pytest.fixture
def client(app):
    return TestClient(app)
