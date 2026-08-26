from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from app.core.exception_handlers import register_exception_handlers
from app.core.exceptions import ResourceNotFoundError, SolverExecutionError


class RequestBody(BaseModel):
    value: int = Field(..., gt=0)


class FakeUniqueViolation(Exception):
    sqlstate = "23505"


def build_test_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/missing")
    def missing() -> None:
        raise ResourceNotFoundError("Room", 99)

    @app.post("/validate")
    def validate(body: RequestBody) -> RequestBody:
        return body

    @app.get("/http-error")
    def http_error() -> None:
        raise HTTPException(status_code=403, detail="Forbidden for this test.")

    @app.get("/duplicate")
    def duplicate() -> None:
        raise IntegrityError("INSERT", {}, FakeUniqueViolation())

    @app.get("/solver-error")
    def solver_error() -> None:
        raise SolverExecutionError()

    return app


client = TestClient(build_test_app(), raise_server_exceptions=False)


def test_resource_not_found_error() -> None:
    response = client.get("/missing")

    assert response.status_code == 404
    assert response.json() == {
        "code": "resource_not_found",
        "message": "Room was not found.",
        "details": {"resource": "Room", "identifier": "99"},
    }


def test_request_validation_error_is_sanitized() -> None:
    response = client.post("/validate", json={"value": -1, "secret": "hidden"})
    body = response.json()

    assert response.status_code == 422
    assert body["code"] == "request_validation_error"
    assert body["details"][0]["loc"] == ["body", "value"]
    assert "secret" not in response.text
    assert "input" not in response.text


def test_http_exception_uses_common_envelope() -> None:
    response = client.get("/http-error")

    assert response.status_code == 403
    assert response.json() == {
        "code": "http_403",
        "message": "Forbidden for this test.",
    }


def test_postgresql_unique_violation_is_conflict() -> None:
    response = client.get("/duplicate")

    assert response.status_code == 409
    assert response.json()["code"] == "duplicate_resource"
    assert "INSERT" not in response.text


def test_internal_application_error_does_not_leak_details() -> None:
    response = client.get("/solver-error")

    assert response.status_code == 500
    assert response.json() == {
        "code": "solver_execution_error",
        "message": "The timetable solver failed to complete.",
    }
