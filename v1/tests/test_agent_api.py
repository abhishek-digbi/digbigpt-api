import os
from agent_core.config.schema import AgentConfig

def valid_payload():
    return {
        "id": "TEST_AGENT1",
        "name": "TEST_AGENT1",
        "provider": "openai",
        "model": "gpt-4o",
        "langfuse_prompt_key": "test_prompt",
        "tools": ["get_var"],
        "temperature": 0.3,
        "top_p": 0.9
    }


def test_create_agent_success(client, mocker):
    insert_mock = mocker.patch('orchestrator.api.controllers.agent_controller.insert_agent_config')
    resp = client.post('/api/agents', json=valid_payload())
    data = resp.json()
    assert resp.status_code == 201
    assert data['message'] == 'Agent created'
    insert_mock.assert_called_once()


def test_create_agent_missing_fields(client):
    resp = client.post('/api/agents', json={"id": "A"})
    data = resp.json()
    assert resp.status_code == 400
    assert 'Invalid input data' in data['message']


def test_update_agent_success(client, mocker):
    update_mock = mocker.patch('orchestrator.api.controllers.agent_controller.update_agent_config')
    payload = valid_payload()
    resp = client.put('/api/agents/TEST_AGENT', json=payload)
    data = resp.json()
    assert resp.status_code == 200
    assert data['message'] == 'Agent updated'
    update_mock.assert_called_once()


def test_get_agents_success(client, mocker):
    cfg = AgentConfig(**valid_payload())
    fetch_mock = mocker.patch(
        'orchestrator.api.controllers.agent_controller.AgentConfigService.fetch_all_agents',
        return_value=[cfg]
    )
    resp = client.get('/api/agents')
    data = resp.json()
    assert resp.status_code == 200
    assert data['message'] == 'Success'
    assert isinstance(data['result'], list)
    assert data['result'][0]['id'] == cfg.id
    assert data['result'][0]['tools'] == cfg.tools
    fetch_mock.assert_called_once()


def test_run_cgm_summary_report_orchestrator(client, mocker):
    agent_mock = mocker.AsyncMock()
    agent_mock.ask.return_value = {"status": "completed"}

    client.app.state.AGENTS["cgm_summary_report_agent"] = agent_mock

    payload = {
        "user_token": "user-123",
        "query_id": "query-123",
        "query": "Generate CGM report",
        "data": {"report_id": "r1", "report_code": "CGM_TEST"},
    }

    response = client.post('/api/run-orchestrator/cgm_summary_report_agent', json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["status"] == "completed"
    agent_mock.ask.assert_awaited_once()
