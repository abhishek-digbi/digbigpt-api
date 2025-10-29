import io
import json


def make_file():
    return {"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")}


def test_upload_file_success(client, mocker):
    mocker.patch.object(
        client.app.state.VECTOR_STORE_SERVICE,
        "upload_file",
        new=mocker.AsyncMock(return_value={"id": "file"}),
    )
    resp = client.post(
        "/api/vector-stores/vs_1/files",
        data={"attributes": json.dumps({"k": "v"})},
        files=make_file(),
    )
    data = resp.json()
    assert resp.status_code == 200
    assert data["message"] == "File uploaded"
    client.app.state.VECTOR_STORE_SERVICE.upload_file.assert_awaited_once()


def test_upload_file_invalid_attributes(client):
    resp = client.post(
        "/api/vector-stores/vs_1/files",
        data={"attributes": "not-json"},
        files=make_file(),
    )
    data = resp.json()
    assert resp.status_code == 400
    assert "Invalid attributes format" in data["message"]


def test_update_file_success(client, mocker):
    mocker.patch.object(
        client.app.state.VECTOR_STORE_SERVICE,
        "update_file_attributes",
        new=mocker.AsyncMock(return_value={"id": "file"}),
    )
    resp = client.put(
        "/api/vector-stores/vs_1/files/f_123",
        json={"attributes": {"a": 1}},
    )
    data = resp.json()
    assert resp.status_code == 200
    assert data["message"] == "File updated"
    client.app.state.VECTOR_STORE_SERVICE.update_file_attributes.assert_awaited_once()


def test_update_file_invalid_body(client):
    resp = client.put(
        "/api/vector-stores/vs_1/files/f_123",
        json={"attributes": "bad"},
    )
    data = resp.json()
    assert resp.status_code == 400
    assert "Invalid attributes" in data["message"]


def test_get_vector_file_success(client, mocker):
    mocker.patch.object(
        client.app.state.VECTOR_STORE_SERVICE,
        "get_vector_store_file",
        new=mocker.AsyncMock(return_value={"id": "f_123", "attributes": {"a": 1}}),
    )
    resp = client.get("/api/vector-stores/vs_1/files/f_123")
    data = resp.json()
    assert resp.status_code == 200
    assert data["message"] == "File retrieved"
    client.app.state.VECTOR_STORE_SERVICE.get_vector_store_file.assert_awaited_once()


def test_get_vector_file_attributes_success(client, mocker):
    mocker.patch.object(
        client.app.state.VECTOR_STORE_SERVICE,
        "get_vector_store_file_attributes",
        new=mocker.AsyncMock(return_value={"attributes": {"k": "v"}}),
    )
    resp = client.get("/api/vector-stores/vs_1/files/f_123/attributes")
    data = resp.json()
    assert resp.status_code == 200
    assert data["message"] == "Attributes retrieved"
    client.app.state.VECTOR_STORE_SERVICE.get_vector_store_file_attributes.assert_awaited_once()


def test_clear_vector_file_attributes_success(client, mocker):
    mocker.patch.object(
        client.app.state.VECTOR_STORE_SERVICE,
        "clear_file_attributes",
        new=mocker.AsyncMock(return_value={"id": "f_123", "attributes": {}}),
    )
    resp = client.delete("/api/vector-stores/vs_1/files/f_123/attributes")
    data = resp.json()
    assert resp.status_code == 200
    assert data["message"] == "Attributes cleared"
    client.app.state.VECTOR_STORE_SERVICE.clear_file_attributes.assert_awaited_once()
