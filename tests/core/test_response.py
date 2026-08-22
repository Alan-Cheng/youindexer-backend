from fastapi.testclient import TestClient

from app.core.response import APIResponse
from app.main import app

client = TestClient(app)


def test_ok_builds_success_envelope() -> None:
    response = APIResponse.ok({"foo": "bar"})
    assert response.success is True
    assert response.code == 200
    assert response.message == "OK"
    assert response.data == {"foo": "bar"}
    assert response.errors is None


def test_fail_builds_error_envelope() -> None:
    response = APIResponse.fail(code=502, message="upstream failed")
    assert response.success is False
    assert response.code == 502
    assert response.message == "upstream failed"
    assert response.data is None


def test_unknown_route_returns_envelope_shaped_404() -> None:
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["code"] == 404
    assert body["data"] is None


def test_validation_error_returns_envelope_shaped_422() -> None:
    response = client.post("/api/v1/instagram/crawl", json={"mode": "keyword", "keyword": ""})
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["code"] == 422
    assert isinstance(body["errors"], list)
    assert body["errors"]
