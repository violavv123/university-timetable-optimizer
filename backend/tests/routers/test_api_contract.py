from app.core.security import require_admin
from app.main import app
from app.routers.dependencies import get_timetable_solver
from app.routers.timetable import _queue_generation
from app.scheduling.solver_factory import DatabaseConfiguredTimetableSolver
from app.schemas.auth import CurrentUserRead
from fastapi.testclient import TestClient

client = TestClient(app, raise_server_exceptions=False)
app.dependency_overrides[require_admin] = lambda: CurrentUserRead(username="test-admin")


def test_health_endpoint_is_available() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_openapi_contains_the_critical_project_routes() -> None:
    paths = app.openapi()["paths"]
    expected_paths = {
        "/api/v1/academic/faculties",
        "/api/v1/academic/study-programs/{resource_id}",
        "/api/v1/academic/study-programs/{study_program_id}/curriculum-validation",
        "/api/v1/resources/staff-members",
        "/api/v1/resources/student-groups",
        "/api/v1/resources/rooms",
        "/api/v1/scheduling-input/course-offerings",
        "/api/v1/scheduling-input/course-sessions",
        "/api/v1/scheduling-input/course-session-groups/{course_session_id}/{student_group_id}",
        "/api/v1/scheduling-input/course-session-staff/{course_session_id}/{staff_member_id}",
        "/api/v1/scheduling-input/time-slots",
        "/api/v1/timetables/runs/{timetable_run_id}/generate",
        "/api/v1/timetables/runs/{timetable_run_id}/validation",
        "/api/v1/timetables/runs/{timetable_run_id}/publish",
        "/api/v1/timetables/entries/{timetable_entry_id}/lock",
    }

    assert expected_paths <= set(paths)


def test_every_operation_id_is_unique() -> None:
    operation_ids = [
        operation["operationId"]
        for path in app.openapi()["paths"].values()
        for method, operation in path.items()
        if method in {"get", "post", "patch", "put", "delete"}
    ]

    assert len(operation_ids) == len(set(operation_ids))


def test_router_rejects_invalid_pagination_before_calling_a_service() -> None:
    response = client.get("/api/v1/academic/faculties?page=0")

    assert response.status_code == 422
    assert response.json()["code"] == "request_validation_error"


def test_router_rejects_invalid_request_body_before_calling_a_service() -> None:
    response = client.post(
        "/api/v1/resources/rooms",
        json={
            "faculty_id": 1,
            "code": "R-1",
            "name": "Room 1",
            "capacity": 0,
            "room_type": "GENERAL_ROOM",
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "request_validation_error"


def test_generation_endpoint_uses_configured_solver_dependency() -> None:
    solver = get_timetable_solver()

    assert isinstance(solver, DatabaseConfiguredTimetableSolver)


def test_generation_is_queued_instead_of_run_in_the_request() -> None:
    queued: list[tuple[object, tuple[object, ...]]] = []

    class FakeBackgroundTasks:
        def add_task(self, function: object, *args: object) -> None:
            queued.append((function, args))

    background_tasks = FakeBackgroundTasks()
    _queue_generation(background_tasks, 42)  # type: ignore[arg-type]

    assert queued[0][1] == (42,)
