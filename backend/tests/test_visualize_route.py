"""POST /api/visualize over HTTP: the contract the frontend depends on."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.execution import TraceUnsupported
from app.routes import visualize as route
from app.services.llm import TraceServiceError
from tests.conftest import FIXTURES, load

http = TestClient(app)
ORIGIN = "http://localhost:3000"


def post(code: str = "class A {}"):
    return http.post("/api/visualize", json={"language": "java", "code": code})


def test_ok_response_is_exactly_the_fixture_json_the_frontend_already_renders(monkeypatch):
    source, trace = load("array_aliasing")
    monkeypatch.setattr(route, "generate_trace", lambda code: trace)

    response = post(source)

    assert response.status_code == 200
    expected = json.loads((FIXTURES / "array_aliasing.json").read_text())["trace"]
    assert response.json() == expected  # including `changed: null` on the println step


def test_unsupported_is_a_normal_200(monkeypatch):
    unsupported = TraceUnsupported(status="unsupported", message="Nope.", unsupportedFeatures=["generics"])
    monkeypatch.setattr(route, "generate_trace", lambda code: unsupported)

    response = post()

    assert response.status_code == 200
    assert response.json() == {"status": "unsupported", "message": "Nope.", "unsupportedFeatures": ["generics"]}


def test_a_service_failure_is_a_503_with_a_readable_detail(monkeypatch):
    def fail(code):
        raise TraceServiceError("The service is busy right now.")

    monkeypatch.setattr(route, "generate_trace", fail)

    response = post()

    assert response.status_code == 503
    assert response.json() == {"detail": "The service is busy right now."}


def test_a_bare_snippet_is_answered_end_to_end_without_any_model_call():
    """Real generate_trace, no monkeypatching: the precheck answers before the API is touched."""
    response = post("int x = 5;")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unsupported"
    assert "bare snippet" in body["unsupportedFeatures"][0]


@pytest.mark.parametrize(
    "payload",
    [
        {"language": "java"},  # no code
        {"language": "python", "code": "print(1)"},  # only java exists
        {"language": "java", "code": "x", "extra": 1},  # the schema forbids extra keys
    ],
)
def test_malformed_requests_are_422(payload):
    assert http.post("/api/visualize", json=payload).status_code == 422


def test_health():
    assert http.get("/api/health").json() == {"status": "ok"}


# --- CORS: without this the browser blocks the frontend's calls -------------


def preflight(origin: str):
    return http.options(
        "/api/visualize",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )


def test_the_frontend_dev_server_is_allowed():
    response = preflight(ORIGIN)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN


def test_other_origins_are_not():
    assert "access-control-allow-origin" not in preflight("https://evil.example").headers
